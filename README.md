# SQUAD DG-LAB — DGHUB 插件版

YOLO 视觉检测插件：将 SQUAD 游戏中的流血/倒地/死亡/压制事件，实时转换为 DG-LAB 设备的体感反馈。

> 本分支 (`dghub-plugin`) 是 **DGHub 插件版**。
> 不依赖 DGHub 的独立应用版（三进程架构）见 [main 分支](../../tree/main)。

**工作链路**：SQUAD 游戏画面 → YOLO 实时检测 → DGHUB WebSocket → DG-LAB 设备

## ⚠️ 重要安全警告

1. **务必先在 DG-LAB APP 中设置强度上限**。APP 端上限滑块是硬件级的最后保护，
   本插件和 DGHub 的任何配置都无法越过它。
2. **从低强度开始测试**。本插件默认 delta 值（10–50%）基于 DGHub 强度模型的
   百分比偏移，实际体感取决于你的 baseline 和 APP 上限设置。
3. 压制检测是**实验功能**，默认关闭。开启前先熟悉核心事件的反馈强度。

## 检测事件

| 事件 | 触发条件 | 默认强度 | 默认时长 |
|------|----------|----------|----------|
| 🩸 流血 | 屏幕出现流血图标 (YOLO) | +15% | 2.0s |
| 💀 倒地 | 屏幕出现倒地图标 (YOLO) | +30% | 4.0s |
| ☠️ 死亡 | 倒地后 250s 内屏幕 90% 变黑 | +50% | 5.0s |
| 🔫 轻度压制 | 视觉压制检测（实验，默认关） | +10% | 1.5s |
| 💥 重度压制 | 视觉压制检测（实验，默认关） | +20% | 2.0s |

## 安装

### 环境要求

- Windows 10/11
- [DGHub](https://www.dglab.club/)（支持 Plugin SDK v1）
- Python 3.10–3.12，**必须是系统级安装且在 PATH 中**（不要用 venv/conda）
- NVIDIA GPU + CUDA 驱动（推荐；CPU 可用但检测帧率低）

### 步骤（顺序很重要）

**1. 先安装 Python 依赖**（插件启用前必须完成，否则启用时会 10 秒超时）：

    pip install -r requirements.txt

> ⚠️ 依赖必须装进 `start.bat` 能找到的那个 Python：插件启动时按
> `PATH 中的 python` → `py -3` → `C:\Program Files\Python311` 的顺序查找。
> 如果你有多个 Python，用 `where python` 确认第一个是装了依赖的那个。

**2.（可选）GPU 加速**：默认 pip 装的是 CPU 版 torch。N 卡用户建议装 CUDA 版：

    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126

**3. 下载插件包**：从 [Releases](../../releases) 下载 `squad_dglab.zip`

**4. 导入**：DGHub → 插件中心 → 外部插件 → 导入 zip

**5. 启用**：打开插件开关，状态显示"YOLO 检测就绪"即成功

## 配置

全部配置在 DGHub 插件面板中实时调整，无需改文件：

| 设置 | 默认值 | 说明 |
|------|--------|------|
| 各事件 delta% | 15/30/50/10/20 | 相对 baseline 的强度偏移 |
| 各事件时长 | 2.0/4.0/5.0/1.5/2.0s | rollback 模式持续时间 |
| 输出通道 | 双通道 | A / B / 双通道 |
| 波形预设 | 无 | 为空时仅调强度不播波形 |
| 压制检测模式 | 关闭 | off / 模糊检测(v1) / 暗角检测(v2) |
| YOLO 置信度阈值 | 0.6 | 低于此值的检测忽略 |
| 检测间隔 | 0.5s | 两次检测之间的间隔 |
| 显示预览窗口 | 关闭 | OpenCV 实时预览（调试用） |

## 故障排查

启用失败时按顺序检查插件目录（`<DGHub安装目录>\plugins\squad_dglab\`）下的日志：

1. **`bootstrap.log`** — start.bat 的启动引导日志。没有此文件 = DGHub 没成功启动
   进程；有此文件但报 `python executable not found` = Python 不在 PATH。
2. **`plugin.log`** — 插件主日志。看最后几行：
   - `import xxx FAILED` → 对应依赖没装进正确的 Python
   - `ConnectionRefusedError` → DGHub 未运行或端口不通
   - `handshake REJECTED` → SDK 版本不匹配
3. 启用后 10 秒超时 → 99% 是依赖未安装，先跑 `pip install -r requirements.txt`

## 开发

    git clone -b dghub-plugin https://github.com/wanchudao/SQUAD_DGLAB.git
    cd SQUAD_DGLAB
    pip install -r requirements.txt
    python build_zip.py   # 重新打包插件 zip

项目结构：

    ├── main.py              # DGHUB 插件入口（6 阶段启动 + WebSocket 协议）
    ├── manifest.json        # 插件元信息 + 配置 UI schema
    ├── start.bat            # DGHUB 启动引导（必须 CRLF 换行）
    ├── build_zip.py         # 插件包构建脚本
    ├── requirements.txt     # Python 依赖
    ├── vision/              # YOLO 检测引擎 + 压制检测器
    └── model/best.pt        # YOLO 模型权重

## 版本

- **dghub-v1.0.0**（2026-07-16）— 首个 DGHUB 插件版本，核心事件真机验证通过
- 独立应用版历史见 [main 分支](../../tree/main) 与其 [Releases](../../releases)

## 许可

[AGPL-3.0](LICENSE)。本项目依赖 [ultralytics](https://github.com/ultralytics/ultralytics)（AGPL-3.0），
模型权重使用 YOLOv8 训练。
