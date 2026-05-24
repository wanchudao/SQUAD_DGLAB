# Known Issues — SQUAD × DG-LAB v1.0.0

本文档记录 v1.0.0 已知的问题、限制和注意事项。

按风险等级分为四档：

- 🔴 **高风险**：可能导致设备异常或安全问题，必须了解
- 🟠 **中风险**：影响功能可用性，启动前请先确认
- 🟡 **低风险**：不影响主要功能，但用户体验可能受影响
- 🔵 **限制说明**：当前版本不支持的场景

---

## 🔴 高风险问题

### H1. suppression 检测为 EXPERIMENTAL，默认关闭

**问题描述**

vision 层的压制效果检测（v1 blur / v2 vignette）尚未经过完整真机验证。已知载具场景下两种检测器都存在盲区——例如开车进入隧道、弹道扬尘、烟雾等情况可能误触发或漏触发。

**影响**

- 误触发 → 设备意外通电，可能造成不适
- 漏触发 → 实际被压制时设备不响应

**应对**

- 默认 `SQUAD_SUPPRESSION_MODE=off`，不要主动开启
- 如需测试 suppression，请先用 Mock 模式跑完整流程
- 真机测试时务必从 APP 端最低强度开始

**修复计划**

v1.x 版本计划重做 suppression v3，加入载具场景检测。

---

### H2. ACTION_PROFILES 默认强度为保守估算

**问题描述**

`config.ini` 中 weak/strong/death 三档默认强度（10 / 20 / 40）是协议层估算值，不同设备的实际感受差异很大。

**影响**

- 强度过低 → 触发了但感受不明显
- 强度过高 → 第一次触发就远超预期

**应对**

- 第一次真机使用，请把所有强度先调到默认值的一半
- 在 DG-LAB APP 端**强制设置通道上限**作为最后一道保护
- 用 `tests/send_bleeding.py` 等脚本做单次触发，确认强度感受合适后再实战

---

### H3. WS 断线后 timer 残留风险

**问题描述**

如果在 safe stop timer 还没到期时 WebSocket 突然断开（如 Wi-Fi 切换、APP 闪退），timer 到期时 send 会失败。当前策略只打日志、不重试。

**影响**

理论上 APP 心跳超时（约 60 秒）会兜底归零，但极端情况下可能出现：断线时强度未归零、APP 心跳又恰好失效，导致设备短期保持触发强度。

**应对**

- 实战时保持手机在 APP 前台，不要切到后台或锁屏
- 出现异常时**立刻物理断开设备**（拔电源 / 拆电池），不依赖软件归零
- 定期检查 APP 端是否还显示连接状态

**修复计划**

v1.x 计划增加 timer 重试机制和断线时主动归零兜底。

---

## 🟠 中风险问题

### M1. A 卡 / Intel 集显 Windows 用户只能用 Mock 模式

**问题描述**

本项目依赖 NVIDIA CUDA 跑 YOLO 实时识别。Windows 下 PyTorch 的 ROCm（AMD）和 IPEX（Intel）支持极差，CPU 版 PyTorch 跑 YOLO 只能到 2~3 FPS。

**影响**

- A 卡用户、Intel 集显用户**实战不可用**
- install.bat 检测不到 nvidia-smi 时会弹三选一菜单，默认建议退出

**应对**

- 仅做开发调试或 Mock 模式联调，可选择装 CPU 版 PyTorch
- 想实战需要换装 N 卡（推荐 RTX 30 系列以上）

---

### M2. 老 N 卡（GTX 10 系列以下）算力可能不足

**问题描述**

GTX 1060/1070/1080 等显卡算力为 6.1，新版 PyTorch 已逐步停止对算力 < 7.0 的支持。即使 install.bat 装好了 cu126 版本，运行时也可能报 `no kernel image is available for execution on the device`。

**影响**

PyTorch 装上了，`torch.cuda.is_available()` 返回 True，但 YOLO 推理时崩溃。

**应对**

- check_deps.py 在 PyTorch 检查节会实际跑一个 GPU tensor 运算，如失败会报错引导
- 如出现该错误，建议改装 cu118（旧版 PyTorch 对老算力支持更好）：

  ```bat
  python -m pip uninstall torch torchvision torchaudio -y
  python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
  ```

---

### M3. nvidia-smi 不在 PATH 时被误判为非 N 卡

**问题描述**

某些笔记本驱动安装后，nvidia-smi 只在 `C:\Program Files\NVIDIA Corporation\NVSMI\` 等子目录里，没加进系统 PATH。install.bat 调用 `nvidia-smi` 会失败，进而走"非 N 卡"分支。

**影响**

实际有 N 卡但被误判，弹三选一菜单，用户可能误选装 CPU 版。

**应对**

- 手动把 NVIDIA 目录加进 PATH 后重启 cmd 再跑 install.bat
- 或者重装 NVIDIA 驱动，**勾选"完整安装"​**而不是"自定义安装"
- 可在 cmd 里跑 `where nvidia-smi` 确认 PATH 是否生效

**修复计划**

v1.x 考虑在 install.bat 里加备用路径搜索。

---

### M4. 端口 18000 / 9999 占用冲突

**问题描述**

部分 dev server（如某些 IDE 自带的预览服务器、其他 WebSocket 工具）默认占用 9999 或 18000。

**影响**

- 9999 被占 → 后端起不来
- 18000 被占 → trigger 服务起不来

**应对**

- 启动前先用 `netstat -ano | findstr 9999` 和 `netstat -ano | findstr 18000` 确认
- 如需改端口：
  - 后端：编辑 `official_v2\socket\v2\backend\.env` 中的 `PORT`
  - Trigger：修改 `start_all.bat` 中的 `--port 18000`
- **改端口后两侧必须保持一致**

---

### M5. CUDA 解析格式异常

**问题描述**

某些非常老或非常新的 NVIDIA 驱动，nvidia-smi 输出格式与主流不同，install.bat 用 `tokens=9` 解析可能拿到非数字。

**影响**

install.bat 的 CUDA 解析校验会兜底装 cu121，但可能不是用户硬件的最优版本。

**应对**

- 看 install.bat 输出中的 `[DEBUG] CUDA_MAJOR=... CUDA_MINOR=...`，如不是数字
- 参考 `PYTORCH_INSTALL.md` 手动安装对应 CUDA 版本

---

## 🟡 低风险问题

### L1. vision 层 ROI 已回退到全屏检测

**问题描述**

早期版本曾使用 ROI 裁剪加速识别，但发现会破坏 incap 识别。v0.2 起回退到全屏检测（`DETECT_Y_START_RATIO = 0.00`）。

**影响**

GPU 占用略高于裁剪版本，但精度提升明显。RTX 30 系列以上显卡完全无压力。

---

### L2. npm 国内访问慢

**问题描述**

npm install 默认源在境外，国内访问可能很慢甚至失败。

**应对**

切换 npm 国内镜像源：

```bat
npm config set registry https://registry.npmmirror.com
```

恢复官方源：

```bat
npm config set registry https://registry.npmjs.org
```

---

### L3. PyTorch 索引地址不能用国内镜像

**问题描述**

PyTorch 的 `--index-url https://download.pytorch.org/whl/cuXXX` 不能直接换成国内镜像（清华 / 阿里云镜像没有完整的 cu126 wheel）。

**应对**

- 网络慢时可挂代理
- 或去 [PyTorch 历史版本页](https://download.pytorch.org/whl/torch_stable.html) 手动下载 .whl 文件后本地安装

---

### L4. Windows Defender 可能误报 install.bat

**问题描述**

某些系统配置下，Windows Defender 或第三方杀软可能把 install.bat 标记为可疑脚本（因为里面有 `set /p`、`pushd`、调用 cmd 等行为）。

**应对**

- 把项目目录加进 Windows Defender 排除列表
- 或在杀软里手动放行 install.bat / start_all.bat

---

### L5. qrcode_latest.png 残留

**问题描述**

每次启动真实模式都会生成 `qrcode_latest.png`，覆盖旧文件，但不会自动清理。

**应对**

- 不影响运行，可手动删除
- `.gitignore` 已忽略此文件

---

## 🔵 当前版本不支持

### N1. Mac / Linux 不支持

`install.bat` 和 `start_all.bat` 都是 Windows 批处理脚本。`mss` 屏幕截图库在 Linux 也能跑，但需要重写启动脚本。Mac 还需要把 PyTorch 切到 MPS 后端。

**修复计划**

v1.x 视社区需求决定是否提供 Linux/macOS 启动脚本。

---

### N2. DGHub 插件版未包含

DGHub 插件版需要重写 `main.py` 适配层（用 trigger op 而非 `/trigger POST`），强度由 DGHub 主程序的 `manifest.config_schema` 自动 UI 管理。

**修复计划**

v1.1 作为独立 release 推出。

---

### N3. 多设备同时连接未支持

当前 `dglab_ws_client.py` 是单例设计，只能连一个 DG-LAB 设备。

**修复计划**

暂无计划，多设备需求请提 issue 讨论。

---

### N4. 自定义事件优先级未支持

事件优先级（death > incap > bleeding > suppression_heavy > suppression_light）目前在 `realtime_detect_and_trigger.py` 中硬编码。

**修复计划**

v1.x 考虑加进 config.ini。

---

## 反馈与提交 Issue

发现新问题或对上述问题有补充信息，欢迎在 GitHub 仓库提 issue：

```txt
https://github.com/wanchudao/SQUAD_DGLAB/issues
```

提 issue 时建议附上：

- `check_deps.py` 的完整输出
- 操作系统版本（Win10 / Win11）
- 显卡型号 + 驱动版本（`nvidia-smi` 输出）
- Python 版本（`python --version`）
- 复现步骤
