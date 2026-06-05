# CLAUDE.md

## 项目说明

这是一个已经开发到 V1.0 的项目。项目中已有完整注释、日志、配置文件和运行脚本。任何 AI 助手在处理本项目时，必须优先保护现有结构、注释风格、日志风格和稳定性。

## 总体原则

1. 修改前必须先阅读相关代码和上下文。
2. 修改前必须先说明计划，不允许直接大范围改代码。
3. 每次只处理一个明确任务。
4. 不允许无理由重写整个文件。
5. 不允许无理由删除已有注释。
6. 不允许无理由删除已有日志。
7. 不允许修改无关文件。
8. 不允许引入新依赖，除非先说明原因并得到确认。
9. 不允许修改密钥、账号、token、证书、私有配置等敏感内容。
10. 所有修改必须能通过人工 review。

## Python 代码规则

1. 保持现有 Python 代码风格。
2. 保持现有函数命名、模块划分和目录结构。
3. 修改函数逻辑时，必须同步检查调用方。
4. 修改异常处理时，必须检查日志是否仍然足够定位问题。
5. 新增代码应尽量小而清晰，不要过度设计。
6. 不要随意改变 public API、配置字段或外部调用方式。

## JavaScript 代码规则

1. 保持现有 JavaScript 代码风格。
2. 不要随意引入新的前端框架或构建工具。
3. 如果修改前后端交互逻辑，必须说明接口字段变化。
4. 不要改动与当前任务无关的 UI、样式或脚本。

## 注释规则

1. 保留解释业务逻辑、协议逻辑、设备逻辑、异常原因的注释。
2. 如果代码行为改变，必须同步更新相关注释。
3. 不要添加无意义的显而易见注释。
4. 对复杂逻辑，应解释“为什么这样做”，而不是只解释“代码做了什么”。

## 日志规则

1. 保持现有日志格式和日志等级习惯。
2. 不要删除关键路径上的日志。
3. 修改异常处理、设备连接、网络请求、文件读写、状态切换等逻辑时，必须检查日志是否完整。
4. 不要在日志中输出密码、token、密钥、私有配置或敏感数据。
5. 新增错误处理时，应加入有助于排查问题的日志。

## Git 工作流

1. 不要直接在 main 分支上工作。
2. AI 修改应优先在 ai-setup-test 或其他 ai-* 分支上进行。
3. 每次修改后必须说明：
   - 修改了哪些文件
   - 为什么修改
   - 是否影响现有功能
   - 如何测试
4. 修改后必须建议运行对应测试或启动脚本。
5. 不允许自动提交代码，除非用户明确要求。

## AI 工作流程

每次任务必须按以下流程执行：

1. 先分析相关文件。
2. 再给出修改计划。
3. 等待用户确认。
4. 只修改计划中明确提到的文件。
5. 修改后展示变更摘要。
6. 提供测试步骤。
7. 等待用户 review。

## 禁止行为

1. 禁止大范围格式化整个项目。
2. 禁止删除历史注释和日志。
3. 禁止修改与任务无关的文件。
4. 禁止猜测配置含义后直接改配置。
5. 禁止把临时调试代码长期留在项目中。
6. 禁止把本地路径、账号、密钥写死进代码。
7. 禁止在没有说明原因的情况下改变项目结构。

## 推荐提示词

当用户要求修改代码时，AI 应优先回应：

“我会先阅读相关文件并给出计划，暂不修改代码。”

当用户要求审查代码时，AI 应优先检查：

1. 是否破坏现有注释
2. 是否破坏现有日志
3. 是否引入不必要依赖
4. 是否影响现有运行脚本
5. 是否存在异常处理遗漏
6. 是否有敏感信息泄露风险



---

# AI 工作记录

## 2026-06-01 — Portable 一键启动版构建全过程

**模型**: deepseek-v4-pro
**分支**: main（未切 ai-* 分支，用户直接要求构建）

---

### 阶段一：全项目阅读

完整阅读了以下内容：

**源代码 (12 个文件)**:
- `python_trigger/app.py` — FastAPI /trigger 接口，DGLAB_REAL 环境变量切换
- `python_trigger/event_mapper.py` — 5 事件→5 动作映射
- `python_trigger/state.py` — 通用 cooldown 管理器
- `python_trigger/config_loader.py` — config.ini 加载器（fallback+clamp）
- `python_trigger/adapters/dglab_sender.py` — 真实发送器（safe stop + per-channel token）
- `python_trigger/adapters/dglab_ws_client.py` — WebSocket 客户端（二维码+重连）
- `python_trigger/adapters/mock_sender.py` — 高保真假发送器
- `vision/realtime_detect_and_trigger.py` — YOLO 实时识别主循环（808 行）
- `vision/suppression/__init__.py` — Suppression 检测器工厂
- `vision/suppression/detector_v1_blur.py` — v1: Laplacian 模糊+色差
- `vision/suppression/detector_v2_vignette.py` — v2: 暗角+边缘检测（18/18 校准）

**配置与脚本 (6 个文件)**:
- `config.ini` — 五档强度/时长配置
- `start_all.bat` — 三选一交互式启动器
- `install.bat` — 6 步一键安装（CUDA 智能映射）
- `check_deps.py` — 5 节依赖体检
- `requirements.txt` — 13 个依赖包
- `PYTORCH_INSTALL.md`、`KNOWN_ISSUES.md`、`README.md`

**测试脚本 (4 个)**:
- `tests/send_bleeding.py`、`send_incap.py`、`send_death.py`、`send_cooldown_test.py`

**历史日志 (10 份)**:
- 2026_4_28 ~ 2026_5_24，覆盖从 SOCKET v2 联调到 v1.0.1 发布全过程
- 真机验证记录：bleeding/incap/death 核心事件 + safe stop + token 防误伤全部通过

---

### 阶段二：打包策略讨论（参考 badwordshock 经验）

**badwordshock 的关键经验**:
- --onedir 而非 --onefile
- CUDA DLL 依赖链：cublas64 → cublasLt → cudart64（缺一不可）
- Windows DLL 加载优先级：已加载模块所在目录 > System32 > PATH
- `getattr(sys, 'frozen', False)` 路径兼容
- `collect_dynamic_libs` + `collect_data_files` 自动收集

**SQUAD_DGLAB 不适合 PyInstaller 的原因**:
1. 三进程架构（Node + FastAPI + Vision），PyInstaller 只能打单个 Python 脚本
2. PyTorch CUDA 体积 ~3GB，PyInstaller dist 后 4-5GB，GitHub 限制 2GB
3. Node.js 后端无法被 PyInstaller 打包
4. 项目已有成熟的 install.bat + start_all.bat，不需要重做安装流程

**最终选择**：Portable 方案——嵌入 Python + Node.js portable，不自带 GPU PyTorch。

---

### 阶段三：一键启动器设计讨论

**三个关键决策**:
1. Mock 模式 → 取消，默认 Real（Portable 用户都是有设备的）
2. IP 选择 → 必须保留，自动列出+用户选编号
3. Suppression 模式 → 必须保留，三选一（off/blur/vignette）

---

### 阶段四：实际构建 Portable 包

**Step 1**: 创建 `dist/SQUAD_DGLAB_portable/` 目录结构

**Step 2**: 下载 Python 3.11.9 embeddable (11MB zip)
- 解压到 `dist/python/`
- 编辑 `python311._pth`: 添加 `Lib/site-packages` + 取消注释 `import site`
- 下载 get-pip.py → 安装 pip 到嵌入式 Python
- **发现 `sys.path` 包含用户 site-packages**: `C:\Users\Max\AppData\Roaming\Python\Python311\site-packages`
- 解决：`启动.bat` 中设置 `PYTHONNOUSERSITE=1`

**Step 3**: pip install 依赖
- 首次装 cu126 GPU 版 torch：2.6 GB 下载，dist 膨胀到 **4.8 GB**
- 其余依赖（ultralytics, opencv-python, fastapi, uvicorn, mss, websocket-client, qrcode, numpy, Pillow, PyYAML, tqdm 等）全部安装成功

**Step 4**: 下载 Node.js v22.20.0 portable (34MB zip)
- 解压到 `dist/node/`（含 node.exe + npm.cmd）

**Step 5**: 复制 `official_v2/` 到 dist
- `npm install` 462 个包（来自 npm 官方源）

**Step 6**: 复制源码
- `python_trigger/`、`vision/`、`model/best.pt`、`config.ini`

**Step 7**: 创建 `启动.bat`
- v1: 含 IP 选择 + Suppression 选择 + 三服务启动
- 编码：GBK/ANSI + CRLF（无 BOM），同 install.bat 规范

**⚠️ 关键转折 — CUDA 兼容性问题**:
用户指出："其他用户不一定是我这个版本的 CUDA，pytorch 也是同样的问题"

预装 cu126 GPU torch 的包只能在 CUDA 12.6+ 驱动上运行。如果用户驱动只支持 CUDA 11.8，torch 会崩溃。

**Step 8**: 改为 CPU 兜底 + 自动升级方案
- 卸载 cu126 torch (2.6 GB)
- 安装 CPU torch (123 MB)
- dist 从 **4.8 GB → 1.3 GB**（预估 zip ~450 MB）

**Step 9**: `启动.bat` 加入 Step 0 — CUDA 检测 + 自动 PyTorch GPU 升级

逻辑（复用 install.bat 的 CUDA 映射）:
```
1. python -c "torch.cuda.is_available()" → 已就绪? 跳过
2. nvidia-smi → 无? 警告但继续 (CPU 模式)
3. 解析 "CUDA Version: X.Y"
4. 映射: >=13→cu126, 12.6+→cu126, 12.4+→cu124, 12.0-12.3→cu121, 11.x→cu118
5. pip install torch torchvision torchaudio --index-url $TORCH_INDEX
6. 首次约 2.6GB 下载，后续启动秒开
```

**Step 10**: 验证 + 清理
- Python 导入验证：torch (CPU), cv2, fastapi, websocket-client 全部通过
- Node.js 启动验证：node.exe + npm 正常
- 清理 `__pycache__`、`.pyc`、下载缓存

---

### 最终产物

```
位置: E:\SQUAD_DGLAB\SQUAD_DGLAB\dist\SQUAD_DGLAB_portable\

SQUAD_DGLAB_portable/        1.3 GB (预估 zip ~450 MB)
├── 启动.bat                 ← 一键启动（含 CUDA 自动检测+GPU 升级）
├── python/                  1.2 GB（Python 3.11.9 + CPU torch + 全部依赖）
│   ├── python.exe
│   └── Lib/site-packages/   ← torch(cpu), ultralytics, cv2, fastapi...
├── node/                    99 MB（Node.js v22.20 portable）
│   ├── node.exe
│   └── npm.cmd
├── official_v2/socket/v2/backend/
│   └── node_modules/        56 MB（462 packages）
├── python_trigger/          源码
├── vision/                  源码（含 suppression/）
├── model/best.pt            22 MB
└── config.ini               默认强度配置
```

### 未创建 build_portable.bat

本应创建自动化构建脚本，但本次构建是手动逐步执行的，`build_portable.bat` 留待后续。

### 涉及的现有文件
- **未修改任何现有文件**。所有改动仅限于 `dist/` 目录下的新增文件。
- `install.bat`、`start_all.bat`、`check_deps.py` 全部原样保留，供开发者和 A 版用户使用。
