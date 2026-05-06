## 重要安全警告

本项目当前为 `v0.1.0-alpha` 实验版本，真实设备模式具有风险。使用前请务必完整阅读本节。

**强烈建议先使用 Mock 模式完成测试，不要一开始就连接真实设备。​**

**真实设备模式下，请务必在 DG-LAB APP 中手动设置通道强度上限。​**

**本项目不会保证在每次动作结束后自动将设备强度归零。​**

**本项目中的 `type: 3` 指令用于将通道强度设置到指定值，而不是一次性临时脉冲。​**

**如果没有正确设置强度上限、没有确认设备状态、没有保留手动断开方式，请不要运行真实设备模式。​**

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
真实设备模式前必须设置强度上限，并从低强度开始测试。
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

建议流程：

```txt
1. 先运行 Mock 模式，确认事件识别和 Trigger 流程正常。
2. 打开 DG-LAB APP，手动设置 A/B 通道强度上限。
3. 从非常低的强度开始测试。
4. 确认可以随时手动断开设备或停止程序。
5. 再切换到真实 DG-LAB 模式。
```

真实设备模式可能存在以下风险：

```txt
识别误判
重复触发
网络延迟
波形队列残留
通道强度未自动归零
设备连接异常
使用者无法及时断开
```

使用者必须自行确认设备状态、强度上限、连接状态和断开方式。因误用、滥用、配置错误、未设置强度上限、设备异常、识别误判或网络通信异常导致的任何后果，均由使用者自行承担。

```txt
不想看的全文的直接按照这些做（正式版会变成一键启动）：
SQUAD × DG-LAB 项目依赖python 3.11.9（记得安装并升级pip）和node js以及Pytorch还有CUDA，所以你必须先下载并配置好，依赖清单请查看requirements.txt这个文件，安装依赖的方式为在主目录新建bat文件并粘贴python -m pip install -r requirements.txt然后执行文件即可。并且你需要单独在这个文件夹SQUAD_DGLAB\official_v2\socket\v2\backend运行npm install.bat

python -m pip install --upgrade pip
上面是升级pip的指令

python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
并使用上面的指令安装使用GPU的PyTorch（注意，这个是用于CUDA 12.6的安装指令，如果你的CUDA是其他版本，请自行安装对应版本的Pytorch）

在SQUAD_DGLAB\python_trigger\adapters\dglab_sender这个文件更改强度（不用担心里面有注释）

然后你需要同时按照顺序启动这三个文件，一个都不能少：

1.去到SQUAD_DGLAB\official_v2\socket\v2\backend，然后直接点击start.bat，如果显示：
info: WebSocket 服务器启动，监听端口：9999
info: 服务器启动完成
那么就成功了

2.去到E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger，点击start_true.bat（千万不要点到start_mock那个是调试用的假发送器）如果显示：
E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger>uvicorn app:app --host 127.0.0.1 --port 18000
[DGLAB WS] 已启动，目标后端：ws://127.0.0.1:9999/
[APP] 当前模式：真实 DG-LAB 发送器 adapters.dglab_sender
[DGLAB WS] 已连接到后端，等待 clientId 分配...
[DGLAB WS] 收到 clientId：xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
[DGLAB WS] 二维码 URL：
           https://www.dungeon-lab.com/app-download.php#DGLAB-SOCKET#ws://192.168.1.100:9999/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
[32mINFO[0m:     Started server process [[36m12208[0m]
[32mINFO[0m:     Waiting for application startup.
[32mINFO[0m:     Application startup complete.
[32mINFO[0m:     Uvicorn running on [1mhttp://127.0.0.1:18000[0m (Press CTRL+C to quit)
[DGLAB WS] 二维码图片已保存：E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger\qrcode_latest.png
[DGLAB WS] 二维码图片已弹出，请用 DG-LAB APP 扫描
并弹出一个二维码，那么就是成功了

3.去到SQUAD_DGLAB\vision，点击realtime_detect_and_trigger.py（注意只有这一个是对的，其他文件都是调试用的，正式版会删除）
然后稍等一会会自动开始识别屏幕上的内容，如果想测试点击SQUAD_DGLAB\samples任何一个异常图标就可以测试是否成功（成功的话会电你）

！！！！！一定！一定！要先检查强度上限！由于我的郊狼还没有到，我不确定他会不会出现强度太高或者是检测到之后一直电的情况（不会自动归零），如果会，请第一时间让我知道（当然任何BUG最好都让我第一时间知道）我会立刻去改！！！！！
```


# SQUAD × DG-LAB

SQUAD × DG-LAB 是一个 Alpha 阶段的实验项目，用于将 SQUAD 游戏画面中的角色状态识别结果，通过本地 Python Trigger 服务转发到 DG-LAB SOCKET v2 通信层，实现基于视觉识别的外部设备反馈。

当前版本主要用于个人学习、实验和联调验证。

## 当前版本

```txt
v0.1.0-alpha
```

## 项目组成

本项目主要由三部分组成：

```txt
vision/             视觉识别层，负责截图、检测和状态判断
python_trigger/     本地 Trigger 服务，负责接收识别事件并映射为动作
official_v2/        DG-LAB SOCKET v2 官方相关源码与后端服务
```

其中：

```txt
model/best.pt       YOLO 识别模型
samples/            测试样本与检测输出示例
requirements.txt    Python 依赖清单
```

## 环境要求

推荐使用以下环境：

```txt
Windows 10 / Windows 11
Python 3.11.9
Node.js
NVIDIA 显卡与可用 CUDA 环境
DG-LAB APP
```

Python 标准库不需要额外安装，例如：

```txt
os
json
time
threading
uuid
collections
datetime
typing
```

## 安装 Python 依赖

请先进入项目根目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB"
```

建议先升级 pip：

```bat
python -m pip install --upgrade pip
```

### 1. 安装 GPU 版 PyTorch

PyTorch 建议单独安装 GPU 版，不要写入 `requirements.txt`，避免后续被误装为 CPU 版。

CUDA 12.6 版本可使用以下命令安装：

```bat
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126
```

### 2. 一键安装 requirements.txt 中的其余依赖

安装完 GPU 版 PyTorch 后，执行下面的命令一键安装本项目其余依赖：

```bat
python -m pip install -r requirements.txt
```

如果你只想安装 `requirements.txt` 中列出的依赖，也可以直接执行：

```bat
python -m pip install -r requirements.txt
```

## requirements.txt 依赖说明

`requirements.txt` 中主要包含以下依赖：

```txt
ultralytics          YOLOv8 推理与训练
opencv-python        图像处理与预览窗口
mss                  屏幕实时截图
numpy                数组运算
requests             vision 层向 Trigger 服务发送 HTTP 请求

fastapi              本地 Trigger 服务 Web 框架
uvicorn[standard]    ASGI 服务启动器
pydantic             请求体校验

websocket-client     DG-LAB SOCKET v2 WebSocket 客户端
qrcode[pil]          自动生成 APP 扫码二维码

Pillow               图像相关依赖
PyYAML               YOLO 数据集配置文件支持
tqdm                 进度条工具
```

## 基本运行流程

本项目通常需要同时运行：

```txt
1. DG-LAB SOCKET v2 后端
2. Python Trigger 服务
3. vision 视觉识别脚本
```

## 1. 启动 DG-LAB SOCKET v2 后端

进入官方 v2 后端目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\official_v2\socket\v2\backend"
```

安装 Node.js 依赖：

```bat
npm install
```

启动后端服务：

```bat
npm start
```

默认 WebSocket 端口为：

```txt
9999
```

## 2. 设置局域网 IP

真实设备扫码时，需要让手机访问电脑所在局域网 IP。

如果不设置环境变量，程序默认使用示例地址：

```txt
192.168.1.100
```

建议根据自己电脑的实际局域网 IP 设置 `DGLAB_LAN_IP`。

CMD 示例：

```bat
set DGLAB_LAN_IP=192.168.x.x
```

然后在同一个 CMD 窗口中继续启动 Python Trigger 服务。

## 3. 启动 Python Trigger 服务

进入 `python_trigger` 目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB\python_trigger"
```

### Mock 模式

Mock 模式用于无设备测试，不会真实发送到设备：

```bat
start_mock.bat
```

### 真实 DG-LAB 模式

真实模式会通过 DG-LAB SOCKET v2 发送动作：

```bat
start_true.bat
```

Trigger 服务默认端口为：

```txt
18000
```

## 4. 运行视觉识别脚本

回到项目根目录：

```bat
cd /d "E:\SQUAD_DGLAB\SQUAD_DGLAB"
```

运行实时识别与触发脚本：

```bat
python vision\realtime_detect_and_trigger.py
```

也可以根据需要运行其他测试脚本：

```bat
python vision\detect_image.py
python vision\batch_detect.py
python vision\sequence_trigger_test.py
python vision\realtime_detect_preview.py
```

## 测试 Trigger 接口

进入 `python_trigger` 目录后，可以运行测试脚本：

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

## 项目目录结构

```txt
SQUAD_DGLAB/
├─ model/
│  └─ best.pt
│
├─ official_v2/
│  └─ socket/
│     └─ v2/
│        ├─ backend/
│        └─ frontend/
│
├─ python_trigger/
│  ├─ adapters/
│  │  ├─ dglab_sender.py
│  │  ├─ dglab_ws_client.py
│  │  └─ mock_sender.py
│  ├─ tests/
│  ├─ app.py
│  ├─ event_mapper.py
│  ├─ state.py
│  ├─ start_mock.bat
│  └─ start_true.bat
│
├─ samples/
│  ├─ test_images/
│  ├─ sequence_images/
│  └─ output/
│
├─ vision/
│  ├─ batch_detect.py
│  ├─ config.py
│  ├─ detect_image.py
│  ├─ detect_image_and_trigger.py
│  ├─ realtime_detect_and_trigger.py
│  ├─ realtime_detect_preview.py
│  ├─ screenshot_test.py
│  ├─ sequence_trigger_test.py
│  └─ trigger_client.py
│
├─ requirements.txt
├─ README.md
└─ .gitignore
```

## 重要配置说明

### DGLAB_LAN_IP

`DGLAB_LAN_IP` 用于生成 DG-LAB APP 扫码连接的二维码地址。

如果不设置，默认使用：

```txt
192.168.1.100
```

实际使用时，请改成自己电脑的局域网 IP，例如：

```bat
set DGLAB_LAN_IP=192.168.1.23
```

### DGLAB_REAL

`DGLAB_REAL` 用于区分 Mock 模式和真实设备模式。

Mock 模式：

```bat
set DGLAB_REAL=0
```

真实模式：

```bat
set DGLAB_REAL=1
```

建议先使用 Mock 模式完成测试，再切换到真实模式。

## 安全说明

本项目涉及外部设备反馈。使用前请务必确认设备状态、连接状态、强度设置和断开方式。

请从低强度开始测试，不要直接使用高强度参数。不要在无人值守、身体状态不佳、疲劳、饮酒或无法及时断开设备的情况下运行本项目。

真实模式下，请确保使用者完全知情并同意。运行过程中应始终保留手动断开设备或停止程序的能力。

本项目当前为 Alpha 实验版本，可能存在识别误判、网络延迟、状态重复触发、设备连接异常等情况。建议优先使用 Mock 模式完成完整流程测试，再切换到真实设备模式。

## 免责声明

本项目仅用于个人学习、实验和技术验证。

使用者应自行承担运行、修改、连接外部设备以及调整强度参数所带来的风险。

作者不对因误用、滥用、错误配置、设备异常、识别误判或网络通信异常导致的任何后果负责。

## 第三方内容说明

`official_v2/` 目录中包含 DG-LAB SOCKET v2 官方相关源码与文档内容。相关文件的版权、许可和使用说明请以该目录内原始说明文件为准。

本项目中的模型文件、测试样本和脚本仅用于本项目 Alpha 阶段的实验验证。

