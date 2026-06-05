# -*- coding: utf-8 -*-
"""
SQUAD x DG-LAB v1.0.0 依赖与项目完整性检查
========================================
跑法: python check_deps.py

检查内容:
    1. Python 版本
    2. 关键依赖 import
    3. PyTorch + CUDA 可用性
    4. OpenCV 功能性测试
    5. 项目关键文件完整性
    6. 端口可用性检查 (9999 / 18000)
"""

from __future__ import annotations
import sys
import importlib
from pathlib import Path

# ANSI 颜色 (Windows 10+ cmd 默认支持)
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{RESET}    {msg}")

def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{RESET}  {msg}")

def fail(msg: str) -> None:
    print(f"{RED}[FAIL]{RESET}  {msg}")

def info(msg: str) -> None:
    print(f"{CYAN}[INFO]{RESET}  {msg}")

def section(title: str) -> None:
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)

# ============================================================
# 1. Python 版本检查
# ============================================================
def check_python() -> bool:
    section("1. Python 版本")
    ver = sys.version_info
    info(f"Python {ver.major}.{ver.minor}.{ver.micro}")
    if ver.major != 3 or ver.minor < 10:
        fail(f"需要 Python 3.10 或 3.11, 当前 {ver.major}.{ver.minor}")
        return False
    if ver.minor >= 13:
        warn(f"Python {ver.major}.{ver.minor} 较新, 部分依赖 (ultralytics) 可能未适配")
    ok(f"Python 版本 OK")
    return True

# ============================================================
# 2. 依赖 import 检查
# ============================================================
REQUIRED_PKGS = [
    # (import_name, pip_name, purpose)
    ("ultralytics",       "ultralytics",       "YOLO 推理"),
    ("cv2",               "opencv-python",     "图像处理"),
    ("numpy",             "numpy",             "数组运算"),
    ("mss",               "mss",               "屏幕截图"),
    ("requests",          "requests",          "HTTP 客户端"),
    ("fastapi",           "fastapi",           "Trigger Web 框架"),
    ("uvicorn",           "uvicorn",           "ASGI 启动器"),
    ("pydantic",          "pydantic",          "请求体校验"),
    ("websocket",         "websocket-client",  "DG-LAB WS 客户端"),
    ("qrcode",            "qrcode[pil]",       "二维码生成"),
    ("PIL",               "Pillow",            "图像处理 (qrcode 依赖)"),
    ("yaml",              "PyYAML",            "ultralytics 数据集配置"),
    ("tqdm",              "tqdm",              "进度条"),
]

def check_packages() -> tuple[int, int]:
    section("2. Python 依赖")
    passed, total = 0, len(REQUIRED_PKGS)
    for imp_name, pip_name, purpose in REQUIRED_PKGS:
        try:
            mod = importlib.import_module(imp_name)
            ver = getattr(mod, "__version__", "unknown")
            ok(f"{pip_name:25s} v{ver:12s}  ({purpose})")
            passed += 1
        except ImportError:
            fail(f"{pip_name:25s} 缺失           ({purpose})")
            print(f"         安装: python -m pip install {pip_name}")
    return passed, total

# ============================================================
# 3. PyTorch + CUDA 检查
# ============================================================
def check_pytorch() -> bool:
    section("3. PyTorch + CUDA")
    try:
        import torch
    except ImportError:
        fail("PyTorch 未安装")
        print("         参考 PYTORCH_INSTALL.md 安装")
        return False

    info(f"PyTorch 版本: {torch.__version__}")

    # 是否 CUDA 版
    if "+cpu" in torch.__version__:
        warn("当前是 CPU 版 PyTorch (YOLO 推理会慢 10 倍以上)")
        warn("建议参考 PYTORCH_INSTALL.md 重装 GPU 版")
        return False

    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_count = torch.cuda.device_count()
        cuda_runtime = torch.version.cuda
        ok(f"CUDA 可用 (运行时版本 {cuda_runtime})")
        ok(f"GPU 数量: {gpu_count}")
        ok(f"主 GPU: {gpu_name}")

        # 实际跑一个 tensor 上 GPU
        try:
            x = torch.rand(3, 3).cuda()
            y = x @ x.T
            ok(f"GPU 张量运算测试通过 (shape={tuple(y.shape)})")
        except Exception as e:
            fail(f"GPU 张量运算失败: {e}")
            return False
        return True
    else:
        fail("CUDA 不可用")
        print("         可能原因:")
        print("         1. 装的是 CPU 版 PyTorch (检查版本号是否带 +cuXXX)")
        print("         2. NVIDIA 驱动太旧, 不支持你装的 CUDA 版本")
        print("         3. 不是 N 卡")
        print("         参考 PYTORCH_INSTALL.md")
        return False

# ============================================================
# 4. OpenCV 功能测试
# ============================================================
def check_opencv() -> bool:
    section("4. OpenCV 功能测试")
    try:
        import cv2
        import numpy as np
    except ImportError:
        fail("cv2 / numpy 未装, 跳过")
        return False

    info(f"OpenCV 版本: {cv2.__version__}")

    try:
        # 创建假图 + Gaussian blur (suppression v1 用)
        img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        ok("GaussianBlur 测试通过 (suppression v1 依赖)")

        # cvtColor (HSV 转换, chroma 检测)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        ok("cvtColor BGR->HSV 测试通过")

        # Laplacian (锐度检测)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        ok(f"Laplacian 测试通过 (var={lap.var():.2f})")

        return True
    except Exception as e:
        fail(f"OpenCV 功能测试失败: {e}")
        return False

# ============================================================
# 5. 项目文件完整性
# ============================================================
REQUIRED_FILES = [
    # (relative_path, description, required)
    ("model/best.pt",                                   "YOLO 模型文件",                       True),
    ("config.ini",                                      "强度配置 (缺失会用默认值)",          False),
    ("requirements.txt",                                "依赖清单",                            True),
    ("PYTORCH_INSTALL.md",                              "PyTorch 安装文档",                   False),
    ("start_all.bat",                                   "启动脚本",                            True),

    # python_trigger
    ("python_trigger/app.py",                           "Trigger 服务",                        True),
    ("python_trigger/event_mapper.py",                  "事件映射",                            True),
    ("python_trigger/state.py",                         "Cooldown 状态",                       True),
    ("python_trigger/config_loader.py",                 "Config 加载器",                       True),
    ("python_trigger/adapters/dglab_sender.py",         "真实 DG-LAB 发送器",                  True),
    ("python_trigger/adapters/mock_sender.py",          "Mock 发送器",                         True),
    ("python_trigger/adapters/dglab_ws_client.py",      "DG-LAB WS 客户端",                    True),

    # vision
    ("vision/realtime_detect_and_trigger.py",           "Vision 主循环",                       True),
    ("vision/suppression/__init__.py",                  "Suppression 工厂",                    True),
    ("vision/suppression/detector_v1_blur.py",          "Suppression v1 (vanilla)",            True),
    ("vision/suppression/detector_v2_vignette.py",      "Suppression v2 (modded)",             True),

    # 官方后端 (Mock 模式可缺)
    ("official_v2/socket/v2/backend/package.json",      "官方后端 package.json",               False),
    ("official_v2/socket/v2/backend/node_modules",      "官方后端 node_modules (跑 npm install 后生成)", False),
]

def check_files() -> tuple[int, int, int]:
    section("5. 项目文件完整性")
    root = Path(__file__).parent
    must_passed, must_total = 0, 0
    opt_passed, opt_total = 0, 0
    for rel, desc, required in REQUIRED_FILES:
        path = root / rel
        if required:
            must_total += 1
        else:
            opt_total += 1

        if path.exists():
            tag = "MUST" if required else "OPT "
            ok(f"[{tag}] {rel:55s}  ({desc})")
            if required:
                must_passed += 1
            else:
                opt_passed += 1
        else:
            if required:
                fail(f"[MUST] {rel:55s}  缺失! ({desc})")
            else:
                warn(f"[OPT ] {rel:55s}  缺失  ({desc})")
    return must_passed, must_total, opt_passed


# ============================================================
# 6. 端口可用性检查
# ============================================================
def check_ports() -> bool:
    section("6. 端口可用性检查")

    import socket

    ports = [
        (9999, "DG-LAB SOCKET v2 后端"),
        (18000, "Python Trigger 服务"),
    ]

    all_ok = True

    for port, desc in ports:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                warn(f"端口 {port} 已被占用 ({desc})")
                all_ok = False
            else:
                ok(f"端口 {port} 可用 ({desc})")
        except Exception as e:
            warn(f"端口 {port} 检测失败: {e}")
            all_ok = False
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

    if all_ok:
        ok("所有端口可用，启动不会冲突")
    else:
        warn("有端口被占用，启动前请用 netstat -ano 排查")

    return all_ok


# ============================================================
# Main
# ============================================================
def main() -> int:
    print()
    print("=" * 60)
    print("  SQUAD x DG-LAB v1.0.0 依赖检查")
    print("=" * 60)

    py_ok = check_python()
    pkg_passed, pkg_total = check_packages()
    torch_ok = check_pytorch()
    cv_ok = check_opencv()
    must_passed, must_total, opt_passed = check_files()
    ports_ok = check_ports()

    section("总结")

    all_ok = True

    if py_ok:
        ok("Python 版本 OK")
    else:
        fail("Python 版本不符")
        all_ok = False

    if pkg_passed == pkg_total:
        ok(f"Python 依赖 {pkg_passed}/{pkg_total} 全部通过")
    else:
        fail(f"Python 依赖 {pkg_passed}/{pkg_total}, 有 {pkg_total - pkg_passed} 个缺失")
        all_ok = False

    if torch_ok:
        ok("PyTorch + CUDA OK")
    else:
        fail("PyTorch / CUDA 有问题, 见上文")
        all_ok = False

    if cv_ok:
        ok("OpenCV 功能 OK")
    else:
        fail("OpenCV 功能测试失败")
        all_ok = False

    if must_passed == must_total:
        ok(f"必需文件 {must_passed}/{must_total} 全部存在")
    else:
        fail(f"必需文件 {must_passed}/{must_total}, 有 {must_total - must_passed} 个缺失")
        all_ok = False

    if ports_ok:
        ok("端口 9999 / 18000 可用")
    else:
        warn("端口 9999 / 18000 有冲突, 启动前请用 netstat -ano 排查")

    print()
    if all_ok:
        print(f"{GREEN}{'=' * 60}{RESET}")
        print(f"{GREEN}  全部检查通过! 可以双击 start_all.bat 启动{RESET}")
        print(f"{GREEN}{'=' * 60}{RESET}")
        return 0
    else:
        print(f"{RED}{'=' * 60}{RESET}")
        print(f"{RED}  有问题需要解决, 见上文 [FAIL] 标记{RESET}")
        print(f"{RED}{'=' * 60}{RESET}")
        print()
        print("常见解决方案:")
        print("  - 依赖缺失: 重新跑 install.bat")
        print("  - PyTorch 问题: 见 PYTORCH_INSTALL.md")
        print("  - 文件缺失: 检查解压是否完整, 或重新下载发布包")
        return 1

if __name__ == "__main__":
    sys.exit(main())
