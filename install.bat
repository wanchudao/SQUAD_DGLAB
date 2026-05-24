@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM ============================================================
REM SQUAD x DG-LAB v1.0.0 一键安装脚本 (v3)
REM
REM 设计原则:
REM   - 不用嵌套 if (...) 多行块, 全部改成 if ... goto :label
REM   - 每步加 [DEBUG] 输出, 卡住能定位
REM   - 失败默认退出 (除了 npm install 是 WARN)
REM
REM v3 变更:
REM   - Step 1 增加 Python 版本号校验 (拒绝 < 3.10, 警告 > 3.12)
REM   - Step 3 增加 CUDA 解析格式校验 (防止 nvidia-smi 输出异常)
REM ============================================================

echo.
echo ============================================================
echo   SQUAD x DG-LAB v1.0.0 - 一键安装
echo ============================================================
echo.

REM ============================================================
REM Step 1/6: 检查 Python (含版本号校验)
REM ============================================================
echo [Step 1/6] 检查 Python...
python --version >nul 2>&1
if errorlevel 1 goto :no_python

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v

REM ------------------------------------------------------------
REM 校验 Python 版本是不是 3.10 / 3.11 / 3.12
REM ------------------------------------------------------------
echo [DEBUG] 校验 Python 版本号...
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
echo [DEBUG] PY_MAJOR=!PY_MAJOR!, PY_MINOR=!PY_MINOR!

REM 校验解析结果是不是数字
echo !PY_MAJOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :py_parse_failed
echo !PY_MINOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :py_parse_failed

if !PY_MAJOR! NEQ 3 goto :py_wrong_major
if !PY_MINOR! LSS 10 goto :py_too_old
if !PY_MINOR! GTR 12 goto :py_too_new
echo [OK] Python !PY_VER! 版本符合要求
goto :step1_node

:py_parse_failed
echo [WARN] Python 版本号解析异常 (PY_VER=!PY_VER!), 跳过校验继续
goto :step1_node

:py_wrong_major
echo [ERROR] 当前 Python 是 !PY_VER!, 本项目需要 Python 3.x
pause
exit /b 1

:py_too_old
echo [ERROR] Python !PY_VER! 太旧
echo         本项目需要 Python 3.10 / 3.11 / 3.12
echo         推荐 Python 3.11.9
echo         下载: https://www.python.org/downloads/
pause
exit /b 1

:py_too_new
echo.
echo [WARN] Python !PY_VER! 较新
echo        ultralytics / YOLO 可能未适配 Python 3.13+
echo        推荐版本: Python 3.11.9
echo.
echo 是否继续? (Y 继续 / N 退出, 默认 N)
set /p PY_CONFIRM="请输入 (Y/N): "
if /i "!PY_CONFIRM!"=="Y" goto :step1_node
echo [ABORT] 已退出, 建议安装 Python 3.11.9
pause
exit /b 1

:no_python
echo [ERROR] 没找到 Python, 请先装 Python 3.10 / 3.11 / 3.12
echo         推荐 Python 3.11.9
echo         https://www.python.org/downloads/
pause
exit /b 1

:step1_node
REM ------------------------------------------------------------
REM Step 1 续: 检查 Node.js
REM ------------------------------------------------------------
echo [DEBUG] 检查 Node.js...
set NODE_AVAILABLE=0
node --version >nul 2>&1
if errorlevel 1 goto :no_node

for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] Node.js %%v
set NODE_AVAILABLE=1
goto :step2

:no_node
echo [WARN] 没找到 Node.js, 官方后端将无法运行 (Mock 模式可忽略)
echo        https://nodejs.org/
goto :step2

REM ============================================================
REM Step 2/6: 升级 pip
REM ============================================================
:step2
echo.
echo [Step 2/6] 升级 pip...
python -m pip install --upgrade pip
if errorlevel 1 echo [WARN] pip 升级失败, 继续

REM ============================================================
REM Step 3/6: 检测 CUDA 并安装 PyTorch (含解析校验)
REM ============================================================
echo.
echo [Step 3/6] 检测 CUDA 并安装 PyTorch...

set CUDA_VER=
set TORCH_INDEX=
set TORCH_TAG=

echo [DEBUG] 调用 nvidia-smi 检测 N 卡...
nvidia-smi >nul 2>&1
if errorlevel 1 goto :no_nvidia
echo [OK] 检测到 NVIDIA 显卡

REM 提取 CUDA 版本
echo [DEBUG] 解析 CUDA 版本号...
for /f "tokens=9" %%i in ('nvidia-smi ^| findstr /C:"CUDA Version"') do set CUDA_VER=%%i

if "!CUDA_VER!"=="" goto :cuda_parse_failed
echo [OK] 驱动支持 CUDA 最高版本: !CUDA_VER!

REM 拆分主次版本
for /f "tokens=1,2 delims=." %%a in ("!CUDA_VER!") do (
    set CUDA_MAJOR=%%a
    set CUDA_MINOR=%%b
)
echo [DEBUG] CUDA_MAJOR=!CUDA_MAJOR!, CUDA_MINOR=!CUDA_MINOR!

REM ------------------------------------------------------------
REM 校验 CUDA 解析结果是不是数字, 防止 nvidia-smi 输出格式异常
REM ------------------------------------------------------------
echo !CUDA_MAJOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :cuda_format_unexpected
echo !CUDA_MINOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :cuda_format_unexpected

REM 版本映射
if !CUDA_MAJOR! GEQ 13 goto :map_cu126
if !CUDA_MAJOR! EQU 12 goto :map_cuda12
if !CUDA_MAJOR! EQU 11 goto :map_cu118
goto :map_cu118_too_old

:map_cuda12
if !CUDA_MINOR! GEQ 6 goto :map_cu126
if !CUDA_MINOR! GEQ 4 goto :map_cu124
goto :map_cu121

:map_cu126
set TORCH_INDEX=https://download.pytorch.org/whl/cu126
set TORCH_TAG=cu126
goto :step3_install

:map_cu124
set TORCH_INDEX=https://download.pytorch.org/whl/cu124
set TORCH_TAG=cu124
goto :step3_install

:map_cu121
set TORCH_INDEX=https://download.pytorch.org/whl/cu121
set TORCH_TAG=cu121
goto :step3_install

:map_cu118
set TORCH_INDEX=https://download.pytorch.org/whl/cu118
set TORCH_TAG=cu118
goto :step3_install

:map_cu118_too_old
echo [WARN] CUDA 版本太低 (!CUDA_VER!), 默认用 cu118
set TORCH_INDEX=https://download.pytorch.org/whl/cu118
set TORCH_TAG=cu118
goto :step3_install

:cuda_format_unexpected
echo [WARN] CUDA 版本解析格式异常 (MAJOR=!CUDA_MAJOR!, MINOR=!CUDA_MINOR!)
echo        nvidia-smi 输出可能不是标准格式, 默认用 cu121 兜底
set TORCH_INDEX=https://download.pytorch.org/whl/cu121
set TORCH_TAG=cu121
goto :step3_install

:cuda_parse_failed
echo [WARN] 解析 CUDA 版本失败 (CUDA_VER 为空), 默认用 cu121
set TORCH_INDEX=https://download.pytorch.org/whl/cu121
set TORCH_TAG=cu121
goto :step3_install

:no_nvidia
echo.
echo ============================================================
echo [WARN] 没找到 nvidia-smi
echo ============================================================
echo.
echo 可能原因:
echo   1. 你不是 N 卡用户 (A 卡 / 集显 / Mac / 云主机)
echo   2. N 卡用户但还没装 NVIDIA 驱动
echo   3. 装了驱动但 PATH 没生效 (重启一下试试)
echo.
echo 重要提醒:
echo   - 本项目依赖 GPU 跑 YOLO 实时识别
echo   - CPU 版下 FPS 会从 30 掉到 2 以下, 基本无法实战
echo   - 强烈建议先去装 NVIDIA 驱动再重跑本脚本:
echo     https://www.nvidia.com/Download/index.aspx
echo.
echo 你有三个选择:
echo   [1] 退出脚本, 先去装驱动 (推荐)
echo   [2] 继续装 CPU 版 PyTorch (只用来开发调试 / Mock 模式)
echo   [3] 退出脚本, 我自己看 PYTORCH_INSTALL.md 手动装
echo.
set /p CPU_CHOICE="请输入 1 / 2 / 3 (默认 1): "
if "!CPU_CHOICE!"=="" set CPU_CHOICE=1
if "!CPU_CHOICE!"=="1" goto :abort_no_gpu
if "!CPU_CHOICE!"=="3" goto :abort_manual
if "!CPU_CHOICE!"=="2" goto :install_cpu
echo [ABORT] 输入无效 (只能是 1/2/3), 已退出
pause
exit /b 1

:abort_no_gpu
echo [ABORT] 已退出, 装好 NVIDIA 驱动后重新跑 install.bat
pause
exit /b 1

:abort_manual
echo [ABORT] 已退出, 请参考 PYTORCH_INSTALL.md 手动安装
pause
exit /b 1

:install_cpu
echo.
echo [INFO] 你选择了 [2] 装 CPU 版
echo        正在安装 CPU 版 PyTorch...
python -m pip install torch torchvision torchaudio
if errorlevel 1 goto :torch_install_failed
set TORCH_TAG=cpu
goto :step3_done

:step3_install
echo.
echo [INFO] 将安装 PyTorch !TORCH_TAG! 版本
echo [INFO] 索引地址: !TORCH_INDEX!
echo.
python -m pip install torch torchvision torchaudio --index-url !TORCH_INDEX!
if errorlevel 1 goto :torch_install_failed
goto :step3_done

:torch_install_failed
echo.
echo [ERROR] PyTorch 安装失败
echo         可能原因:
echo         1. 网络问题 (PyTorch 索引不能用国内镜像)
echo         2. CUDA 版本不匹配
echo         请参考 PYTORCH_INSTALL.md 手动安装
pause
exit /b 1

:step3_done
echo.
echo [INFO] 验证 PyTorch 安装 (标签: !TORCH_TAG!)...
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU mode')"
if errorlevel 1 goto :torch_import_failed
goto :step4

:torch_import_failed
echo [ERROR] PyTorch import 失败
pause
exit /b 1

REM ============================================================
REM Step 4/6: 安装 requirements.txt
REM ============================================================
:step4
echo.
echo [Step 4/6] 安装 Python 其余依赖...
if not exist "requirements.txt" goto :no_requirements

python -m pip install -r requirements.txt
if errorlevel 1 goto :req_install_failed
echo [OK] Python 依赖安装完成
goto :step5

:no_requirements
echo [ERROR] 找不到 requirements.txt
pause
exit /b 1

:req_install_failed
echo [ERROR] requirements.txt 安装失败
echo         尝试切换 pip 镜像源后重试:
echo         pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pause
exit /b 1

REM ============================================================
REM Step 5/6: Node.js 依赖 (官方后端)
REM 实际路径: official_v2\socket\v2\backend
REM ============================================================
:step5
echo.
echo [Step 5/6] 安装 Node.js 依赖 (官方后端)...
if "!NODE_AVAILABLE!"=="0" goto :step5_skip_no_node

set BACKEND_DIR=official_v2\socket\v2\backend
if not exist "!BACKEND_DIR!" goto :step5_skip_no_dir
if not exist "!BACKEND_DIR!\package.json" goto :step5_skip_no_pkg

echo [INFO] 进入官方后端目录: !BACKEND_DIR!
pushd "!BACKEND_DIR!"
call npm install
if errorlevel 1 goto :npm_failed

echo [OK] Node 依赖安装完成 (官方后端)

REM 自动复制 .env (首次安装)
if exist ".env" goto :env_exists
if not exist ".env.example" goto :no_env_example
copy /Y ".env.example" ".env" >nul
echo [OK] 已自动创建 .env (从 .env.example 复制)
echo      默认端口 9999, 如需修改请编辑 .env
goto :env_done

:env_exists
echo [INFO] .env 已存在, 跳过复制
goto :env_done

:no_env_example
echo [WARN] 没找到 .env.example, 请手动检查环境变量配置
goto :env_done

:env_done
popd
goto :step6

:npm_failed
popd
echo.
echo [WARN] Node 依赖安装失败
echo        切换 npm 镜像源后重试:
echo        npm config set registry https://registry.npmmirror.com
echo        然后重新运行 install.bat
echo.
echo 只用 Mock 模式可以忽略, 按任意键继续...
pause >nul
goto :step6

:step5_skip_no_node
echo [SKIP] 没装 Node.js, 跳过这一步 (Mock 模式可忽略)
goto :step6

:step5_skip_no_dir
echo [WARN] 未找到官方后端目录: !BACKEND_DIR! (Mock 模式可忽略)
goto :step6

:step5_skip_no_pkg
echo [WARN] 后端目录里没有 package.json, 请检查官方后端是否完整解压
goto :step6

REM ============================================================
REM Step 6/6: 跑 check_deps.py 验证
REM ============================================================
:step6
echo.
echo [Step 6/6] 验证安装...
if not exist "check_deps.py" goto :no_check_deps

python check_deps.py
if errorlevel 1 echo [WARN] check_deps.py 报告有问题, 见上文
goto :done

:no_check_deps
echo [WARN] 找不到 check_deps.py, 跳过验证
goto :done

REM ============================================================
REM 完成
REM ============================================================
:done
echo.
echo ============================================================
echo   安装完成!
echo ============================================================
echo.
echo 下一步:
echo   1. 真机模式: 双击 start_all.bat
echo   2. Mock 模式: 见 README.md
echo.
echo 强度调整: 编辑 config.ini
echo PyTorch 问题: 见 PYTORCH_INSTALL.md
echo.
pause
endlocal
exit /b 0

