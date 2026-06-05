@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM SQUAD x DG-LAB v1.0.0 һ����װ�ű� (v3.1)
REM
REM ���ԭ��:
REM   - ����Ƕ�� if (...) ���п�, ȫ���ĳ� if ... goto :label
REM   - ÿ���� [DEBUG] ���, ��ס�ܶ�λ
REM   - ʧ��Ĭ���˳� (���� npm install �� WARN)
REM
REM v3.1 ���:
REM   - ɾ�� chcp 65001, �ļ����� GBK/ANSI �����������
REM   - �ļ������� GBK / ANSI ���뱣��, ��Ҫ�� UTF-8
REM ============================================================

echo.
echo ============================================================
echo   SQUAD x DG-LAB v1.0.0 - һ����װ
echo ============================================================
echo.

REM ============================================================
REM Step 1/6: ��� Python (���汾��У��)
REM ============================================================
echo [Step 1/6] ��� Python...
python --version >nul 2>&1
if errorlevel 1 goto :no_python

for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo [OK] %%v

REM ------------------------------------------------------------
REM У�� Python �汾�ǲ��� 3.10 / 3.11 / 3.12
REM ------------------------------------------------------------
echo [DEBUG] У�� Python �汾��...
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)
echo [DEBUG] PY_MAJOR=!PY_MAJOR!, PY_MINOR=!PY_MINOR!

REM У���������ǲ�������
echo !PY_MAJOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :py_parse_failed
echo !PY_MINOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :py_parse_failed

if !PY_MAJOR! NEQ 3 goto :py_wrong_major
if !PY_MINOR! LSS 10 goto :py_too_old
if !PY_MINOR! GTR 12 goto :py_too_new
echo [OK] Python !PY_VER! �汾����Ҫ��
goto :step1_node

:py_parse_failed
echo [WARN] Python �汾�Ž����쳣 (PY_VER=!PY_VER!), ����У�����
goto :step1_node

:py_wrong_major
echo [ERROR] ��ǰ Python �� !PY_VER!, ����Ŀ��Ҫ Python 3.x
pause
exit /b 1

:py_too_old
echo [ERROR] Python !PY_VER! ̫��
echo         ����Ŀ��Ҫ Python 3.10 / 3.11 / 3.12
echo         �Ƽ� Python 3.11.9
echo         ����: https://www.python.org/downloads/
pause
exit /b 1

:py_too_new
echo.
echo [WARN] Python !PY_VER! ����
echo        ultralytics / YOLO ����δ���� Python 3.13+
echo        �Ƽ��汾: Python 3.11.9
echo.
echo �Ƿ����? (Y ���� / N �˳�, Ĭ�� N)
set /p PY_CONFIRM="������ (Y/N): "
if /i "!PY_CONFIRM!"=="Y" goto :step1_node
echo [ABORT] ���˳�, ���鰲װ Python 3.11.9
pause
exit /b 1

:no_python
echo [ERROR] û�ҵ� Python, ����װ Python 3.10 / 3.11 / 3.12
echo         �Ƽ� Python 3.11.9
echo         https://www.python.org/downloads/
echo.
echo [INFO] Opening Python download page...
start https://www.python.org/downloads/
pause
exit /b 1

:step1_node
REM ------------------------------------------------------------
REM Step 1 ��: ��� Node.js
REM ------------------------------------------------------------
echo [DEBUG] ��� Node.js...
set NODE_AVAILABLE=0
node --version >nul 2>&1
if errorlevel 1 goto :no_node

for /f "tokens=*" %%v in ('node --version 2^>^&1') do echo [OK] Node.js %%v
set NODE_AVAILABLE=1
goto :step2

:no_node
echo [WARN] û�ҵ� Node.js, �ٷ���˽��޷����� (Mock ģʽ�ɺ���)
echo        https://nodejs.org/
echo [INFO] Opening Node.js download page...
start https://nodejs.org/
goto :step2

REM ============================================================
REM Step 2/6: ���� pip
REM ============================================================
:step2
echo.
echo [Step 2/6] ���� pip...
python -m pip install --upgrade pip
if errorlevel 1 echo [WARN] pip ����ʧ��, ����

REM ============================================================
REM Step 3/6: ��� CUDA ����װ PyTorch (������У��)
REM ============================================================
echo.
echo [Step 3/6] ��� CUDA ����װ PyTorch...

set CUDA_VER=
set TORCH_INDEX=
set TORCH_TAG=

echo [DEBUG] ���� nvidia-smi ��� N ��...
nvidia-smi >nul 2>&1
if errorlevel 1 goto :no_nvidia
echo [OK] ��⵽ NVIDIA �Կ�

REM ��ȡ CUDA �汾
echo [DEBUG] ���� CUDA �汾��...
for /f "tokens=9" %%i in ('nvidia-smi ^| findstr /C:"CUDA Version"') do set CUDA_VER=%%i

if "!CUDA_VER!"=="" goto :cuda_parse_failed
echo [OK] ����֧�� CUDA ��߰汾: !CUDA_VER!

REM ������ΰ汾
for /f "tokens=1,2 delims=." %%a in ("!CUDA_VER!") do (
    set CUDA_MAJOR=%%a
    set CUDA_MINOR=%%b
)
echo [DEBUG] CUDA_MAJOR=!CUDA_MAJOR!, CUDA_MINOR=!CUDA_MINOR!

REM ------------------------------------------------------------
REM У�� CUDA ��������ǲ�������, ��ֹ nvidia-smi �����ʽ�쳣
REM ------------------------------------------------------------
echo !CUDA_MAJOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :cuda_format_unexpected
echo !CUDA_MINOR!| findstr /R "^[0-9][0-9]*$" >nul
if errorlevel 1 goto :cuda_format_unexpected

REM �汾ӳ��
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
echo [WARN] CUDA �汾̫�� (!CUDA_VER!), Ĭ���� cu118
set TORCH_INDEX=https://download.pytorch.org/whl/cu118
set TORCH_TAG=cu118
goto :step3_install

:cuda_format_unexpected
echo [WARN] CUDA �汾������ʽ�쳣 (MAJOR=!CUDA_MAJOR!, MINOR=!CUDA_MINOR!)
echo        nvidia-smi ������ܲ��Ǳ�׼��ʽ, Ĭ���� cu121 ����
set TORCH_INDEX=https://download.pytorch.org/whl/cu121
set TORCH_TAG=cu121
goto :step3_install

:cuda_parse_failed
echo [WARN] ���� CUDA �汾ʧ�� (CUDA_VER Ϊ��), Ĭ���� cu121
set TORCH_INDEX=https://download.pytorch.org/whl/cu121
set TORCH_TAG=cu121
goto :step3_install

:no_nvidia
echo.
echo ============================================================
echo [WARN] û�ҵ� nvidia-smi
echo ============================================================
echo.
echo ����ԭ��:
echo   1. �㲻�� N ���û� (A �� / ���� / Mac / ������)
echo   2. N ���û�����ûװ NVIDIA ����
echo   3. װ�������� PATH û��Ч (����һ������)
echo.
echo ��Ҫ����:
echo   - ����Ŀ���� GPU �� YOLO ʵʱʶ��
echo   - CPU ���� FPS ��� 30 ���� 2 ����, �����޷�ʵս
echo   - ǿ�ҽ�����ȥװ NVIDIA ���������ܱ��ű�:
echo     https://www.nvidia.com/Download/index.aspx
echo.
echo ��������ѡ��:
echo   [1] �˳��ű�, ��ȥװ���� (�Ƽ�)
echo   [2] ����װ CPU �� PyTorch (ֻ������������ / Mock ģʽ)
echo   [3] �˳��ű�, ���Լ��� PYTORCH_INSTALL.md �ֶ�װ
echo.
set /p CPU_CHOICE="������ 1 / 2 / 3 (Ĭ�� 1): "
if "!CPU_CHOICE!"=="" set CPU_CHOICE=1
if "!CPU_CHOICE!"=="1" goto :abort_no_gpu
if "!CPU_CHOICE!"=="3" goto :abort_manual
if "!CPU_CHOICE!"=="2" goto :install_cpu
echo [ABORT] ������Ч (ֻ���� 1/2/3), ���˳�
pause
exit /b 1

:abort_no_gpu
echo [ABORT] ���˳�, װ�� NVIDIA ������������ install.bat
pause
exit /b 1

:abort_manual
echo [ABORT] ���˳�, ��ο� PYTORCH_INSTALL.md �ֶ���װ
pause
exit /b 1

:install_cpu
echo.
echo [INFO] ��ѡ���� [2] װ CPU ��
echo        ���ڰ�װ CPU �� PyTorch...
python -m pip install torch torchvision torchaudio
if errorlevel 1 goto :torch_install_failed
set TORCH_TAG=cpu
goto :step3_done

:step3_install
echo.
echo [INFO] ����װ PyTorch !TORCH_TAG! �汾
echo [INFO] ������ַ: !TORCH_INDEX!
echo.
python -m pip install torch torchvision torchaudio --index-url !TORCH_INDEX! --default-timeout 120
if not errorlevel 1 goto :step3_done
echo.
echo [WARN] First attempt failed, retrying once...
python -m pip install torch torchvision torchaudio --index-url !TORCH_INDEX! --default-timeout 120
if not errorlevel 1 goto :step3_done
goto :torch_install_failed

:torch_install_failed
echo.
echo [ERROR] PyTorch ��װʧ��
echo         ����ԭ��:
echo         1. �������� (PyTorch ���������ù��ھ���)
echo         2. CUDA �汾��ƥ��
echo         ��ο� PYTORCH_INSTALL.md �ֶ���װ
pause
exit /b 1

:step3_done
echo.
echo [INFO] ��֤ PyTorch ��װ (��ǩ: !TORCH_TAG!)...
python -c "import torch; print('PyTorch:', torch.__version__); print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU mode')"
if errorlevel 1 goto :torch_import_failed
goto :step4

:torch_import_failed
echo [ERROR] PyTorch import ʧ��
pause
exit /b 1

REM ============================================================
REM Step 4/6: ��װ requirements.txt
REM ============================================================
:step4
echo.
echo [Step 4/6] ��װ Python ��������...
if not exist "requirements.txt" goto :no_requirements

python -m pip install -r requirements.txt
if errorlevel 1 goto :req_install_failed
echo [OK] Python ������װ���
goto :step5

:no_requirements
echo [ERROR] �Ҳ��� requirements.txt
pause
exit /b 1

:req_install_failed
echo [ERROR] requirements.txt ��װʧ��
echo         �����л� pip ����Դ������:
echo         pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
pause
exit /b 1

REM ============================================================
REM Step 5/6: Node.js ���� (�ٷ����)
REM ʵ��·��: official_v2\socket\v2\backend
REM ============================================================
:step5
echo.
echo [Step 5/6] ��װ Node.js ���� (�ٷ����)...
if "!NODE_AVAILABLE!"=="0" goto :step5_skip_no_node

set BACKEND_DIR=official_v2\socket\v2\backend
if not exist "!BACKEND_DIR!" goto :step5_skip_no_dir
if not exist "!BACKEND_DIR!\package.json" goto :step5_skip_no_pkg

echo [INFO] ����ٷ����Ŀ¼: !BACKEND_DIR!
pushd "!BACKEND_DIR!"
call npm install
if errorlevel 1 goto :npm_failed

echo [OK] Node ������װ��� (�ٷ����)

:step5_env_check
REM �Զ����� .env (�״ΰ�װ)
if exist ".env" goto :env_exists
if not exist ".env.example" goto :no_env_example
copy /Y ".env.example" ".env" >nul
echo [OK] ���Զ����� .env (�� .env.example ����)
echo      Ĭ�϶˿� 9999, �����޸���༭ .env
goto :env_done

:env_exists
echo [INFO] .env �Ѵ���, ��������
goto :env_done

:no_env_example
echo [WARN] û�ҵ� .env.example, ���ֶ���黷����������
goto :env_done

:env_done
popd
goto :step6

:npm_failed
popd
echo.
echo [WARN] First attempt failed, retrying with npmmirror...
pushd "!BACKEND_DIR!"
call npm config set registry https://registry.npmmirror.com
call npm install
popd
if not errorlevel 1 (
    echo [OK] npm install succeeded with mirror
    goto :step5_env_check
)
echo.
echo [WARN] npm install still failed
echo        Mock mode can skip this, continue anyway...
pause >nul
goto :step6

:step5_skip_no_node
echo [SKIP] ûװ Node.js, ������һ�� (Mock ģʽ�ɺ���)
goto :step6

:step5_skip_no_dir
echo [WARN] δ�ҵ��ٷ����Ŀ¼: !BACKEND_DIR! (Mock ģʽ�ɺ���)
goto :step6

:step5_skip_no_pkg
echo [WARN] ���Ŀ¼��û�� package.json, ����ٷ�����Ƿ�������ѹ
goto :step6

REM ============================================================
REM Step 6/6: �� check_deps.py ��֤
REM ============================================================
:step6
echo.
echo [Step 6/6] ��֤��װ...
if not exist "check_deps.py" goto :no_check_deps

python check_deps.py
if errorlevel 1 echo [WARN] check_deps.py ����������, ������
goto :done

:no_check_deps
echo [WARN] �Ҳ��� check_deps.py, ������֤
goto :done

REM ============================================================
REM ���
REM ============================================================
:done
echo.
echo ============================================================
echo   ��װ���!
echo ============================================================
echo.
echo ��һ��:
echo   1. ���ģʽ: ˫�� start_all.bat
echo   2. Mock ģʽ: �� README.md
echo.
echo ǿ�ȵ���: �༭ config.ini
echo PyTorch ����: �� PYTORCH_INSTALL.md
echo.
pause
endlocal
exit /b 0