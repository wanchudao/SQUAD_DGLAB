# SQUAD × DG-LAB

SQUAD × DG-LAB 是一个 Alpha 阶段的实验项目，用于将 SQUAD 游戏画面中的角色状态识别结果，通过本地 Python Trigger 服务转发到 DG-LAB SOCKET v2 通信层，实现基于视觉识别的外部设备反馈。

当前版本主要用于个人学习、实验和联调验证。

## 当前版本

```txt
v0.2.0-alpha-safestop
```

---

## 重要安全警告

**本版本在 v0.1.0-alpha 基础上新增了「动作结束后自动归零」机制，但作者本人尚未在真实郊狼设备上完成验证。​**

请务必完整阅读本节后再启动真实设备模式。

**强烈建议先使用 Mock 模式完成完整链路测试，确认事件识别、Trigger 流转、WebSocket 配对都正常之后，再切换到真实设备模式。​**

**真实设备模式下，必须在 DG-LAB APP 中手动设置通道强度上限。APP 端的上限是最后一道硬件级保护，软件层任何 bug 都不能突破这条线。​**

**本项目中的 `type: 3` 指令用于将通道强度设置到指定值，不是一次性临时脉冲。这意味着「设置 → 不归零」会让设备一直保持该强度。v0.2 已经加入自动归零逻辑，但请仍然保留手动断开能力。​**

**如果没有正确设置强度上限、没有确认设备状态、没有保留手动断开方式，请不要运行真实设备模式。​**

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
真实设备模式前必须设置强度上限，并从低强度开始测试。
v0.2 的自动归零未经真机验证，请保持警惕。
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
通道强度未自动归零（v0.2 已修复，但未经真机验证）
设备连接异常
使用者无法及时断开
```

使用者必须自行确认设备状态、强度上限、连接状态和断开方式。因误用、滥用、配置错误、未设置强度上限、设备异常、识别误判或网络通信异常导致的任何后果，均由使用者自行承担。

---

## v0.2.0-alpha-safestop 改动摘要

本次版本相对 v0.1.0-alpha 的主要改动：

**新功能**

```txt
新增  start_all.bat 一键启动脚本（自动检测 npm install + Mock/Real 模式选择）
新增  动作结束后自动归零（_stop_channel：clear 波形队列 + strength=0）
新增  per-channel token 机制，防止旧 timer 误归零新动作
新增  发送波形失败时立刻触发兜底归零
调整  send_action 在 clientMsg 发送成功后调度 safe stop timer
```

**清理**

```txt
删除  vision/ 下所有调试脚本，仅保留 realtime_detect_and_trigger.py
删除  official_v2/ 下非 backend 内容（coyote、frontend、image、PawPrints）
删除  samples/ 测试样本（不再随仓库分发）
删除  start_mock.bat（Mock 模式已并入 start_all.bat）
```

详细改动可参考 `python_trigger/adapters/dglab_sender.py` 顶部注释。

已通过的测试：

```txt
[OK] start_all.bat 双模式启动
[OK] Mock 回归
[OK] 真实模式下未绑定 (not_bound) 路径
[OK] 真实模式 WS 连接 + 二维码生成 + APP 扫码配对
[--] 真实设备单次触发归零            （等待设备到货）
[--] 真实设备重叠事件 token 防误伤    （等待设备到货）
[--] 真实设备跨事件中断              （等待设备到货）
```

---

## 项目组成

```txt
vision/             视觉识别层，负责截图、检测和状态判断
python_trigger/    本地 Trigger 服务，负责接收识别事件并映射为动作
official_v2/       DG-LAB SOCKET v2 官方后端服务（仅保留 backend）
model/best.pt      YOLO 识别模型
start_all.bat      一键启动脚本（v0.2 新增）
requirements.txt   Python 依赖清单
PYTORCH_INSTALL.md PyTorch 安装指南（GPU 版必读）
```

测试样本 `samples/` 不随仓库分发，请向作者单独索取。

---

## 环境要求

```txt
Windows 10 / Windows 11
Python 3.11.9
Node.js（建议 LTS 版本）
NVIDIA 显卡与可用 CUDA 环境
DG-LAB APP
DG-LAB 郊狼脉冲主机 3.0
```

---

## 安装步骤

### 1. 安装 GPU 版 PyTorch

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

### 2. 安装其余 Python 依赖

进入项目根目录，安装 `requirements.txt` 中列出的依赖：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB"
python -m pip install -r requirements.txt
```

`requirements.txt` 中**不包含** torch/torchvision/torchaudio，不会覆盖刚装好的 GPU 版。

主要包含：

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

### 3. Node.js 依赖

`start_all.bat` 首次运行时会自动执行 `npm install`，无需手动操作。

如果想手动安装：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\official_v2\socket\v2\backend"
npm install
```

---

## 基本运行流程

本项目通常需要同时运行三个组件：

```txt
1. DG-LAB SOCKET v2 后端       （端口 9999）
2. Python Trigger 服务         （端口 18000）
3. vision 视觉识别脚本         （独立进程）
```

v0.2 提供两种启动方式：**推荐使用一键启动**。

---

## 启动方式 A：一键启动（推荐）

在项目根目录双击：

```txt
start_all.bat
```

脚本会自动完成：

```txt
1. 检测 Node.js 依赖，未安装时自动跑 npm install
2. 提示选择模式：
     1 = Mock 模式（无设备测试）
     2 = Real 模式（真实 DG-LAB）
3. 选择 Real 模式时显示强度上限安全警告
4. 弹出两个新 cmd 窗口：
     - DGLAB Backend   （Node.js 后端）
     - Trigger Service （Python uvicorn）
5. 真实模式下自动弹出二维码图片，用 DG-LAB APP 扫码即可配对
```

**vision 视觉识别脚本不会被一键启动**，需要确认配对成功后手动启动（见下节）。

---

## 启动方式 B：手动启动（备用）

### 1. 启动 DG-LAB SOCKET v2 后端

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\official_v2\socket\v2\backend"
npm start
```

成功后应看到：

```txt
info: WebSocket 服务器启动，监听端口：9999
info: 服务器启动完成
```

也可直接双击 `start.bat`。

### 2. 设置局域网 IP（仅真实模式需要）

真实设备扫码时，需要让手机访问电脑所在局域网 IP。

不设置时默认使用：

```txt
192.168.1.100
```

查询本机 IP：

```bat
ipconfig
```

设置环境变量：

```bat
set DGLAB_LAN_IP=192.168.x.x
```

### 3. 启动 Python Trigger 服务

进入 `python_trigger` 目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger"
```

Mock 模式：

```bat
set DGLAB_REAL=0
uvicorn app:app --host 127.0.0.1 --port 18000
```

真实 DG-LAB 模式：

```bat
set DGLAB_REAL=1
uvicorn app:app --host 127.0.0.1 --port 18000
```

真实模式启动成功后应看到类似输出（节选）：

```txt
[APP] 当前模式：真实 DG-LAB 发送器 adapters.dglab_sender
[DGLAB WS] 已连接到后端，等待 clientId 分配...
[DGLAB WS] 收到 clientId：xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
[DGLAB WS] 二维码 URL：
           https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#ws://192.168.x.x:9999/xxxxxxxx-...
INFO:     Uvicorn running on http://127.0.0.1:18000
[DGLAB WS] 二维码图片已保存：...\qrcode_latest.png
[DGLAB WS] 二维码图片已弹出，请用 DG-LAB APP 扫描
```

---

## 4. 运行视觉识别脚本

无论使用方式 A 还是方式 B，vision 都需要在 Backend + Trigger 都启动**之后**手动运行。

回到项目根目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB"
```

运行实时识别与触发脚本（**vision 层只保留这一个文件**，其他历史脚本已在 v0.2 清理）：

```bat
python vision\realtime_detect_and_trigger.py
```

脚本启动后会持续抓屏并把识别到的事件 POST 到 Trigger 服务。所有 vision 层配置项都内置在 `realtime_detect_and_trigger.py` 顶部，需要调整请直接编辑该文件。

---

## 测试 Trigger 接口

如果没有 SQUAD 游戏画面，可以直接用 `tests/` 目录下的脚本向 Trigger 服务发送测试事件，验证整条链路。

进入 `python_trigger` 目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger"
```

发送 bleeding 测试事件：

```bat
python tests\send_bleeding.py
```

发送 incap 测试事件：

```bat
python tests\send_incap.py
```

发送 death 测试事件：

```bat
python tests\send_death.py
```

发送 cooldown 测试事件：

```bat
python tests\send_cooldown_test.py
```

**注意**：这些脚本只发 HTTP，最终是否真的电到设备取决于：

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
│           ├─ README.md
│           └─ start.bat
│
├─ python_trigger/
│  ├─ adapters/
│  │  ├─ dglab_sender.py      ← v0.2 改造重点
│  │  ├─ dglab_ws_client.py
│  │  └─ mock_sender.py
│  ├─ tests/
│  │  ├─ send_bleeding.py
│  │  ├─ send_cooldown_test.py
│  │  ├─ send_death.py
│  │  └─ send_incap.py
│  ├─ app.py
│  ├─ event_mapper.py
│  └─ state.py
│
├─ vision/
│  └─ realtime_detect_and_trigger.py
│
├─ start_all.bat              ← v0.2 一键启动入口
├─ requirements.txt
├─ README.md
├─ PYTORCH_INSTALL.md
└─ .gitignore
```

---

## 重要配置说明

### DGLAB_LAN_IP

用于生成 DG-LAB APP 扫码连接的二维码地址。

不设置时默认：

```txt
192.168.1.100
```

实际使用请改为本机局域网 IP：

```bat
set DGLAB_LAN_IP=192.168.1.23
```

### DGLAB_REAL

用于区分 Mock 模式和真实设备模式。

Mock 模式：

```bat
set DGLAB_REAL=0
```

真实模式：

```bat
set DGLAB_REAL=1
```

使用 `start_all.bat` 时，这个变量会根据用户输入自动设置，无需手动配置。

建议先使用 Mock 模式完成测试，再切换到真实模式。

---

## 已知问题与限制

```txt
1. 自动归零未经真机验证
   v0.2 在 dglab_sender 中加入了 safe stop timer + per-channel token，
   逻辑层与协议层均已 review，但因作者郊狼设备未到货，
   尚未在真实硬件上验证「动作结束后强度是否真的归零」。

2. ACTION_PROFILES 强度值为保守估算
   dglab_sender.py 中 weak/strong/death 三档强度
   (10 / 20 / 40) 为协议层估算值，可能偏低或偏高，
   需要真机体验后调整。

3. WS 断开重连后的 timer 残留
   如果 WS 断开时正好有 safe stop timer 在飞，
   timer 到期时 send 会失败，当前策略是只打日志、不重试。
   理论上 APP 心跳超时会兜底，但未经真机验证。

4. vision 层 ROI 已回退到全屏检测
   早期版本曾使用 ROI 裁剪加速识别，但发现会破坏 incap 识别，
   v0.2 已回退到全屏 (DETECT_Y_START_RATIO = 0.00)。

5. start_all.bat 仅支持 Windows
   依赖 cmd 内置命令与 start 关键字，未提供 Linux/macOS 等价脚本。
```

---

## 安全说明

本项目涉及外部设备反馈。使用前请务必确认设备状态、连接状态、强度设置和断开方式。

请从低强度开始测试，不要直接使用高强度参数。不要在无人值守、身体状态不佳、疲劳、饮酒或无法及时断开设备的情况下运行本项目。

真实模式下，请确保使用者完全知情并同意。运行过程中应始终保留手动断开设备或停止程序的能力。

本项目当前为 Alpha 实验版本，可能存在识别误判、网络延迟、状态重复触发、设备连接异常等情况。建议优先使用 Mock 模式完成完整流程测试，再切换到真实设备模式。

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

本项目中的模型文件、测试脚本仅用于本项目 Alpha 阶段的实验验证。
