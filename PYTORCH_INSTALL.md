# PyTorch 安装指南

> **​⚠️ 重要**：PyTorch 必须单独安装，**不要**通过 `pip install -r requirements.txt` 装，否则会装成 CPU 版，YOLO 推理会慢 10 倍以上。

## 第 1 步：确认你有 NVIDIA 显卡

打开 cmd 输入：

```cmd
nvidia-smi
```

如果显示一张表格（GPU 型号、驱动版本、CUDA Version），说明驱动 OK，继续下一步。

如果提示 `'nvidia-smi' 不是内部或外部命令` —— 你没装 NVIDIA 驱动，或者你不是 N 卡。**N 卡用户**去 [NVIDIA 官网](https://www.nvidia.com/Download/index.aspx) 下最新驱动；**非 N 卡用户**这个项目跑不起来（YOLO 推理需要 CUDA）。

## 第 2 步：查看你的 CUDA 版本

继续看 `nvidia-smi` 输出的**右上角**，会有一行：

```
CUDA Version: 12.6
```

记住这个数字（比如 12.6、12.4、12.1、11.8），下一步要用。

> **注意**：`nvidia-smi` 显示的是**驱动支持的最高 CUDA 版本**，不是你已经安装的版本。你只需要装一个**不高于**这个数字的 PyTorch 即可。**不需要**单独去下载安装 CUDA Toolkit，PyTorch 的 wheel 自带 cudart 运行时，只要有 NVIDIA 驱动就够了。

## 第 3 步：根据 CUDA 版本选择安装命令

进入项目根目录：

```cmd
cd /d E:\SQUAD_DGLAB\SQUAD_DGLAB
```

先升级 pip：

```cmd
python -m pip install --upgrade pip
```

然后**根据你的 CUDA 版本**选择对应命令（**只跑一条**）：

| 你的 CUDA Version | 执行命令 |
|---|---|
| **12.6 及以上** | `python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu126` |
| **12.4** | `python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124` |
| **12.1** | `python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121` |
| **11.8** | `python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118` |
| **其他版本 / 不确定** | 去 [PyTorch 官网](https://pytorch.org/get-started/locally/) 选择对应版本 |

> **小提示**：如果你的 CUDA 是 12.6，那 cu124 / cu121 也能装（向下兼容），但**优先选 cu126**，性能最好。

## 第 4 步：验证是否装对了

```cmd
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

**正确输出**应该是这样：

```
PyTorch: 2.5.1+cu126
CUDA available: True
GPU: NVIDIA GeForce RTX 4070
```

**关键看**：
- `CUDA available: True` ← 必须是 True
- PyTorch 版本号后面带 `+cu126`（或 cu124 / cu121 等）← 不能是 `+cpu`

如果 `CUDA available: False` 或者版本号后面是 `+cpu`，那就是装错了，**卸载重装**：

```cmd
python -m pip uninstall torch torchvision torchaudio -y
```

然后回到第 3 步重新选命令。

## 第 5 步：安装其余依赖

确认 PyTorch 装对后，再装项目其他依赖：

```cmd
python -m pip install -r requirements.txt
```

`requirements.txt` 里**不包含** torch/torchvision/torchaudio，所以不会覆盖你刚装的 GPU 版。

## 常见问题

**Q：装完 `CUDA available: False`，怎么办？​**

A：99% 是装成了 CPU 版。原因和解决方法：

1. **没指定 `--index-url`​** → 默认 PyPI 源给的是 CPU 版，必须加 `--index-url https://download.pytorch.org/whl/cuXXX`
2. **驱动版本太低** → `nvidia-smi` 显示的 CUDA Version 比你装的 PyTorch CUDA 版本低（比如驱动只支持 CUDA 11.8，你装了 cu126）→ 改装 cu118，或者升级驱动
3. **装了多个 Python** → 你以为装到 Python 3.11，其实装到 3.10 了。用 `python --version` 确认是 3.11.9，用 `where python` 确认路径

**Q：能用 CPU 版凑合跑吗？​**

A：技术上能跑，但 YOLO 实时识别会**慢到没法用**（30 FPS 掉到 2 FPS 以下），不推荐。

**Q：我没装 CUDA Toolkit，只装了驱动，行吗？​**

A：**行**。PyTorch 自带 CUDA 运行时（cudart），你只需要 NVIDIA 驱动，**不需要单独装 CUDA Toolkit**。

**Q：能用国内镜像加速下载吗？​**

A：PyTorch 的 `--index-url` **不能**直接换成国内镜像（国内镜像没有完整的 cu126 wheel）。如果下载慢，可以挂代理，或者去 [PyTorch 历史版本页](https://download.pytorch.org/whl/torch_stable.html) 手动下载 `.whl` 文件后用 `pip install 文件路径.whl` 本地安装。
