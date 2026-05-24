# SQUAD × DG-LAB

SQUAD × DG-LAB 是一个把 SQUAD 游戏画面中的角色状态识别结果，通过本地 Python Trigger 服务转发到 DG-LAB SOCKET v2 通信层，实现基于视觉识别的外部设备反馈的项目。

v1.0.0 在 v0.2.0-alpha 基础上完成了一键安装、依赖体检、配置化强度调整等封装工作，核心事件（bleeding / incap / death / safe stop）已通过真机验证，可作为正式版本对外发布。

## 当前版本

```txt
v1.0.1
```

发布形式：

- **A 版（源码 + 模型）​**：适合开发者、想魔改的用户。
- **B 版（源码 + 依赖 + 模型）​**：解压即用，含预装的 venv 和 node_modules。

DGHub 插件版将作为独立 release 在 v1.1 推出。

---

## 重要安全警告

**真实设备模式下，必须在 DG-LAB APP 中手动设置通道强度上限。APP 端的上限是最后一道硬件级保护，软件层任何 bug 都不能突破这条线。​**

**本项目中的 `type: 3` 指令用于将通道强度设置到指定值，不是一次性临时脉冲。这意味着「设置 → 不归零」会让设备一直保持该强度。v0.2 起加入了自动归零逻辑，v1.0 已通过真机验证 bleeding / incap / death 三个核心事件的完整归零流程，但请仍然保留手动断开能力。​**

**强烈建议先使用 Mock 模式完成完整链路测试，确认事件识别、Trigger 流转、WebSocket 配对都正常之后，再切换到真实设备模式。​**

**如果没有正确设置强度上限、没有确认设备状态、没有保留手动断开方式，请不要运行真实设备模式。​**

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
真实设备模式前必须设置强度上限，并从低强度开始测试。
suppression 检测仍为 EXPERIMENTAL，默认关闭，请保持警惕。
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

建议流程：

```txt
1. 先运行 Mock 模式，确认事件识别和 Trigger 流程正常。
2. 打开 DG-LAB APP，手动设置 A/B 通道强度上限（推荐 A ≤ 30 开始）。
3. 从非常低的强度开始测试。
4. 确认可以随时手动断开设备或停止程序。
5. 再切换到真实 DG-LAB 模式。
6. 第一次真机联调时，留意「动作结束后强度是否自动归零」，
   如未归零请立刻断开设备并反馈。
```

真实设备模式可能存在以下风险：

```txt
识别误判
重复触发
网络延迟
波形队列残留
通道强度未自动归零（核心事件已验证，suppression 仍未验证）
设备连接异常
使用者无法及时断开
```

使用者必须自行确认设备状态、强度上限、连接状态和断开方式。因误用、滥用、配置错误、未设置强度上限、设备异常、识别误判或网络通信异常导致的任何后果，均由使用者自行承担。

---

## v1.0.0 改动摘要

本次版本相对 v0.2.0-alpha 的主要改动：

**新功能**

```txt
新增  install.bat 一键安装脚本（自动检测 CUDA、智能映射 PyTorch 版本、Python 版本校验）
新增  check_deps.py 依赖体检脚本（5 节检查：Python / 依赖 / PyTorch+CUDA / OpenCV / 项目文件）
新增  config.ini 强度配置文件，支持自定义 weak/strong/death/suppression 五档强度
新增  start_all.bat 增加 suppression 模式三选一（off / blur / vignette）
新增  start_all.bat 自动检测局域网 IPv4 列表供选择
新增  suppression v1（blur，vanilla 适用）和 v2（vignette，modded 适用）两套检测器
新增  KNOWN_ISSUES.md 已知问题文档
```

**改进**

```txt
改进  npm install 流程并入 install.bat Step 5，自动复制 .env.example 为 .env
改进  install.bat 使用 goto-based 结构，避免嵌套 if 块在 cmd 下的解析问题
改进  ACTION_PROFILES 改为从 config.ini 读取，运行时无需改代码即可调强度
改进  README 端口占用说明明确（18000 trigger / 9999 backend）
```

**真机验证状态（v1.0.0）​**

```txt
[OK] start_all.bat 双模式 + suppression 三模式启动
[OK] Mock 模式完整回归
[OK] 真实模式 WS 连接 + 二维码 + APP 扫码配对
[OK] bleeding 单次触发完整归零（真机）
[OK] incap 单次触发完整归零（真机）
[OK] death 单次触发完整归零（真机）
[OK] 重叠事件 token 防误伤（真机）
[--] suppression v1/v2 真机验证（EXPERIMENTAL，载具场景已知盲区）
```

---

## 项目组成

```txt
vision/             视觉识别层，负责截图、检测和状态判断
python_trigger/    本地 Trigger 服务，负责接收识别事件并映射为动作
official_v2/       DG-LAB SOCKET v2 官方后端服务（仅保留 backend）
model/best.pt      YOLO 识别模型
install.bat        一键安装脚本（v1.0 新增）
check_deps.py      依赖体检脚本（v1.0 新增）
start_all.bat      一键启动脚本
config.ini         强度配置（v1.0 新增）
requirements.txt   Python 依赖清单
PYTORCH_INSTALL.md PyTorch 安装指南（GPU 版必读）
KNOWN_ISSUES.md    已知问题与限制
```

测试样本 `samples/` 不随仓库分发，请向作者单独索取。

---

## 环境要求

```txt
Windows 10 / Windows 11
Python 3.10 / 3.11 / 3.12（推荐 3.11.9）
Node.js 16 或更高（推荐 LTS）
NVIDIA 显卡（推荐 RTX 20/30/40 系列）+ 可用 CUDA 驱动
DG-LAB APP
DG-LAB 郊狼脉冲主机 3.0
```

A 卡、Intel 集显、Mac 用户的限制请见 `KNOWN_ISSUES.md`。

---

## 安装步骤

### 推荐：一键安装

在项目根目录双击：

```txt
install.bat
```

脚本会自动完成 6 个步骤：

```txt
Step 1/6  检查 Python 与 Node.js（含版本号校验）
Step 2/6  升级 pip
Step 3/6  检测 CUDA 并安装对应版本 PyTorch（cu126/cu124/cu121/cu118 智能映射）
Step 4/6  安装 requirements.txt 其余依赖
Step 5/6  安装 Node.js 后端依赖 + 自动复制 .env
Step 6/6  调用 check_deps.py 体检
```

中途如检测不到 NVIDIA 显卡，脚本会弹出三选一菜单（默认退出，不会强制装 CPU 版）。

CUDA 版本异常或解析失败时会兜底装 cu121，确保不会卡死。

### 手动安装（备用）

如果一键脚本失败，按以下顺序手动执行：

#### 1. 安装 GPU 版 PyTorch

PyTorch 必须单独安装 GPU 版，**不能**通过 `requirements.txt` 装，否则会被装成 CPU 版，YOLO 推理性能会下降 10 倍以上。

完整安装步骤、CUDA 版本对照表与验证方法请见：

```txt
PYTORCH_INSTALL.md
```

CUDA 12.6 用户可直接使用：

```bat
python -m pip install --upgrade pip
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

其他 CUDA 版本请查阅 `PYTORCH_INSTALL.md`。

#### 2. 安装其余 Python 依赖

进入项目根目录：

```bat
cd /d "项目根目录"
python -m pip install -r requirements.txt
```

`requirements.txt` 中**不包含** torch/torchvision/torchaudio，不会覆盖刚装好的 GPU 版。

主要依赖：

```txt
ultralytics          YOLOv8 推理
opencv-python        图像处理
mss                  屏幕截图
numpy                数组运算
requests             vision 层向 Trigger 服务发送 HTTP 请求
fastapi              本地 Trigger 服务 Web 框架
uvicorn[standard]    ASGI 服务启动器
pydantic             请求体校验
websocket-client     DG-LAB SOCKET v2 WebSocket 客户端
qrcode[pil]          自动生成 APP 扫码二维码
Pillow               图像相关依赖
PyYAML               YOLO 数据集配置支持
tqdm                 进度条工具
```

#### 3. Node.js 依赖

```bat
cd /d "项目根目录\official_v2\socket\v2\backend"
npm install
copy .env.example .env
```

#### 4. 验证安装

```bat
cd /d "项目根目录"
python check_deps.py
```

应看到 5 节检查全部通过：Python 版本 / 13 个依赖包 / PyTorch+CUDA / OpenCV 功能 / 项目文件完整性。

---

## 端口占用一览

```txt
9999    DG-LAB SOCKET v2 后端（WebSocket）
18000   Python Trigger 服务（FastAPI）
```

启动前请确保这两个端口未被其他程序占用。如确需修改：

```txt
- 后端端口：编辑 official_v2\socket\v2\backend\.env 中的 PORT
- Trigger 端口：修改 start_all.bat 中的 --port 参数
注意：端口改动后两侧必须保持一致，否则 trigger 连不上后端。
```

---

## 启动方式 A：一键启动（推荐）

在项目根目录双击：

```txt
start_all.bat
```

脚本会引导你完成三轮选择：

```txt
1. 发送器模式
   1 = Mock  （无设备测试）
   2 = Real  （真实 DG-LAB 设备）

2. Suppression 模式（实验性，默认关闭）
   1 = off       默认，推荐
   2 = blur      vanilla SQUAD 用，EXPERIMENTAL
   3 = vignette  modded SQUAD 用，EXPERIMENTAL

3. 局域网 IP（仅 Real 模式）
   脚本会自动列出本机所有 IPv4 地址，选一个让手机扫码访问
```

选择完成后会自动启动三个服务窗口：

```txt
- DGLAB Backend     端口 9999
- Trigger Service   端口 18000，含 DGLAB_REAL / DGLAB_LAN_IP / SQUAD_SUPPRESSION_MODE 环境变量
- Vision Detector   YOLO 实时识别
```

Real 模式启动后会自动弹出二维码，用 DG-LAB APP 扫描即可配对。

---

## 启动方式 B：手动启动（备用）

### 1. 启动 DG-LAB SOCKET v2 后端

```bat
cd /d "项目根目录\official_v2\socket\v2\backend"
npm start
```

成功后应看到：

```txt
info: WebSocket 服务器启动，监听端口：9999
info: 服务器启动完成
```

### 2. 设置局域网 IP（仅真实模式需要）

```bat
ipconfig                           查询本机 IP
set DGLAB_LAN_IP=192.168.x.x       设置环境变量
```

### 3. 启动 Python Trigger 服务

```bat
cd /d "项目根目录\python_trigger"

REM Mock 模式
set DGLAB_REAL=0
uvicorn app:app --host 127.0.0.1 --port 18000

REM 真实 DG-LAB 模式
set DGLAB_REAL=1
uvicorn app:app --host 127.0.0.1 --port 18000
```

### 4. 启动 vision 视觉识别脚本

```bat
cd /d "项目根目录\vision"
python realtime_detect_and_trigger.py
```

如需启用 suppression：

```bat
set SQUAD_SUPPRESSION_MODE=blur       vanilla 用
set SQUAD_SUPPRESSION_MODE=vignette   modded 用
```

---

## 强度调整

v1.0 起所有强度参数都集中在项目根目录的 `config.ini`，无需改代码：

```ini
[ACTION_PROFILES]
weak_pulse_strength = 10
weak_pulse_duration = 2.0

strong_pulse_strength = 20
strong_pulse_duration = 4.0

death_pulse_strength = 40
death_pulse_duration = 5.0

suppression_light_pulse_strength = 8
suppression_light_pulse_duration = 1.5

suppression_heavy_pulse_strength = 14
suppression_heavy_pulse_duration = 2.0
```

修改后**重启 trigger 服务**即可生效，无需重启后端或 vision。

---

## 测试 Trigger 接口

如果没有 SQUAD 游戏画面，可以直接用 `tests/` 目录下的脚本向 Trigger 服务发送测试事件：

```bat
cd /d "项目根目录\python_trigger"

python tests\send_bleeding.py
python tests\send_incap.py
python tests\send_death.py
python tests\send_cooldown_test.py
```

注意：

```txt
1. Mock 模式          → 永远不会真电，只在终端打印
2. 真实模式 + 未扫码  → 返回 not_bound 错误，不会触发
3. 真实模式 + 已扫码  → 真的会触发，请提前确认 APP 通道上限
```

---

## 项目目录结构

```txt
SQUAD_DGLAB/
├─ model/
│  └─ best.pt
│
├─ official_v2/
│  └─ socket/
│     └─ v2/
│        └─ backend/
│           ├─ src/
│           │  ├─ config.js
│           │  ├─ connection.js
│           │  ├─ index.js
│           │  ├─ logger.js
│           │  ├─ message.js
│           │  └─ timer.js
│           ├─ package.json
│           ├─ package-lock.json
│           ├─ .env.example
│           ├─ npm install.txt
│           └─ README.md
│
├─ python_trigger/
│  ├─ adapters/
│  │  ├─ dglab_sender.py
│  │  ├─ dglab_ws_client.py
│  │  └─ mock_sender.py
│  ├─ tests/
│  │  ├─ send_bleeding.py
│  │  ├─ send_cooldown_test.py
│  │  ├─ send_death.py
│  │  └─ send_incap.py
│  ├─ app.py
│  ├─ event_mapper.py
│  ├─ state.py
│  └─ config_loader.py
│
├─ vision/
│  ├─ realtime_detect_and_trigger.py
│  └─ suppression/
│     ├─ __init__.py
│     ├─ detector_v1_blur.py
│     └─ detector_v2_vignette.py
│
├─ install.bat              v1.0 新增
├─ check_deps.py            v1.0 新增
├─ start_all.bat
├─ config.ini               v1.0 新增
├─ requirements.txt
├─ README.md
├─ PYTORCH_INSTALL.md
├─ KNOWN_ISSUES.md          v1.0 新增
└─ .gitignore
```

---

## 重要环境变量说明

### DGLAB_LAN_IP

用于生成 DG-LAB APP 扫码连接的二维码地址。`start_all.bat` 会自动列出本机 IPv4 让你选，无需手动设置。手动启动时：

```bat
set DGLAB_LAN_IP=192.168.1.23
```

### DGLAB_REAL

区分 Mock 模式和真实设备模式。`start_all.bat` 会根据用户输入自动设置。

```bat
set DGLAB_REAL=0    Mock
set DGLAB_REAL=1    Real
```

### SQUAD_SUPPRESSION_MODE

启用压制效果检测（默认关闭）。`start_all.bat` 第二轮选择时会自动设置。

```bat
set SQUAD_SUPPRESSION_MODE=off        默认
set SQUAD_SUPPRESSION_MODE=blur       vanilla SQUAD
set SQUAD_SUPPRESSION_MODE=vignette   modded SQUAD
```

---

## 已知问题与限制

详见 `KNOWN_ISSUES.md`。简要列举：

```txt
1. suppression 检测为 EXPERIMENTAL，默认关闭，载具场景有已知盲区。

2. ACTION_PROFILES 默认强度（10/20/40）为保守估算，请通过 config.ini 调整。

3. WS 断开重连后的 timer 残留：APP 心跳超时会兜底，但未在所有断网场景验证。

4. vision 层 ROI 已回退到全屏检测（早期 ROI 裁剪会破坏 incap 识别）。

5. install.bat / start_all.bat 仅支持 Windows。

6. A 卡、Intel 集显 Windows 用户只能用 Mock 模式（PyTorch CPU 版 YOLO 推理过慢）。

7. Mac 暂不支持，需重写启动脚本和 mss 屏幕截图层。

8. nvidia-smi 不在 PATH 时会被识别为非 N 卡，需手动加 PATH 或重装驱动。
```

---

## 安全说明

本项目涉及外部设备反馈。使用前请务必确认设备状态、连接状态、强度设置和断开方式。

请从低强度开始测试，不要直接使用高强度参数。不要在无人值守、身体状态不佳、疲劳、饮酒或无法及时断开设备的情况下运行本项目。

真实模式下，请确保使用者完全知情并同意。运行过程中应始终保留手动断开设备或停止程序的能力。

虽然 v1.0 已通过核心事件真机验证，但 suppression、断网恢复等场景仍存在未覆盖的边界情况。建议优先使用 Mock 模式完成完整流程测试，再切换到真实设备模式。

---

## 免责声明

本项目仅用于个人学习、实验和技术验证。

使用者应自行承担运行、修改、连接外部设备以及调整强度参数所带来的风险。

作者不对因误用、滥用、错误配置、设备异常、识别误判或网络通信异常导致的任何后果负责。

---

## 第三方内容说明

`official_v2/` 目录中包含 DG-LAB SOCKET v2 官方后端源码。相关文件的版权、许可和使用说明请以官方仓库为准：

```txt
https://github.com/DG-LAB-OPENSOURCE/DG-LAB-OPENSOURCE
```

本项目中的模型文件、测试脚本仅用于本项目的实验验证。

---

## 后续版本规划

```txt
v1.1   DGHub 插件版（独立 release，重写 main.py 适配层，
       使用 trigger op 而非 /trigger POST，强度由主程序 UI 自动管理）
v1.x   suppression v3 优化载具场景识别
v1.x   Linux/Mac 启动脚本支持
```
