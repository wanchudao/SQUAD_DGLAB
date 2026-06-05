@echo off
setlocal EnableExtensions EnableDelayedExpansion
title SQUAD_DGLAB Launcher

set "ROOT=%~dp0"
set "BACKEND=%ROOT%official_v2\socket\v2\backend"
set "TRIGGER=%ROOT%python_trigger"
set "VISION=%ROOT%vision"
set "NMOD=node_modules"

echo Project root: %ROOT%
echo Backend path: %BACKEND%
echo Trigger path: %TRIGGER%
echo Vision  path: %VISION%
echo.

REM ---- npm install if needed ----
if not exist "%BACKEND%\%NMOD%" goto NEED_INSTALL
goto SKIP_INSTALL

:NEED_INSTALL
echo [SETUP] Running npm install...
pushd "%BACKEND%"
call npm install
popd
echo.

:SKIP_INSTALL

REM ---- Choose sender mode ----
echo ============================================
echo Choose sender mode:
echo   1 = Mock  (no real device, safe for testing)
echo   2 = Real  (sends to real DG-LAB device)
echo ============================================
set /p MODE=Enter 1 or 2:

set "REAL=0"
if "%MODE%"=="2" set "REAL=1"

echo.
echo Selected: MODE=%MODE%, DGLAB_REAL=%REAL%
echo.

REM ---- Choose suppression mode ----
echo ============================================
echo Choose suppression detection mode:
echo   1 = off       (default, recommended)
echo   2 = blur      (vanilla SQUAD, EXPERIMENTAL, may misfire)
echo   3 = vignette  (modded SQUAD only, EXPERIMENTAL)
echo.
echo Both blur and vignette are experimental.
echo If you do not know which one to pick, choose 1 (off).
echo ============================================
set /p SUPP_SEL=Enter 1, 2 or 3:

set "SUPP_MODE=off"
if "%SUPP_SEL%"=="2" set "SUPP_MODE=blur"
if "%SUPP_SEL%"=="3" set "SUPP_MODE=vignette"

echo.
echo Selected: SUPPRESSION_MODE=%SUPP_MODE%
echo.

REM ---- Real mode warning ----
if "%REAL%"=="1" goto REAL_WARN
goto SKIP_IP

:REAL_WARN
echo !!! WARNING: REAL DEVICE MODE !!!
echo Set strength limit in DG-LAB APP first.
echo.

REM ---- Detect IPv4 addresses from ipconfig ----
set "IP_COUNT=0"

for /f "tokens=2 delims=:" %%A in ('ipconfig ^| findstr /R /C:"IPv4.*"') do (
    set "RAW_IP=%%A"
    set "RAW_IP=!RAW_IP: =!"
    if not "!RAW_IP!"=="" (
        set /a IP_COUNT+=1
        set "IP_!IP_COUNT!=!RAW_IP!"
    )
)

if %IP_COUNT% LEQ 0 (
    echo [WARN] No IPv4 address found from ipconfig.
    set "LAN_IP=127.0.0.1"
    goto IP_DONE
)

echo.
echo Detected IPv4 addresses:
for /l %%I in (1,1,%IP_COUNT%) do (
    call echo   %%I = %%IP_%%I%%
)

echo.
set /p IPSEL=Choose IP number (1-%IP_COUNT%): 

set "LAN_IP="
for /l %%I in (1,1,%IP_COUNT%) do (
    if "!IPSEL!"=="%%I" set "LAN_IP=!IP_%%I!"
)

if not defined LAN_IP (
    echo [WARN] Invalid selection, fallback to first IP.
    set "LAN_IP=!IP_1!"
)

:IP_DONE
echo.
echo Selected LAN_IP=%LAN_IP%
echo Press Ctrl+C to abort, or any key to continue...
pause > nul
goto START_SERVICES

:SKIP_IP
set "LAN_IP=127.0.0.1"

:START_SERVICES
echo.
echo ============================================
echo Starting services in order:
echo   1. Backend  (port 9999)
echo   2. Trigger  (port 18000)
echo   3. Vision   (YOLO + suppression)
echo ============================================
echo.

echo [1/3] Starting Backend...
start "DGLAB Backend" cmd /k "cd /d %BACKEND% && npm start"

timeout /t 3 /nobreak > nul

REM ---- Set env vars in parent shell so child cmd inherits them ----
set "DGLAB_REAL=%REAL%"
set "DGLAB_LAN_IP=%LAN_IP%"
set "SQUAD_SUPPRESSION_MODE=%SUPP_MODE%"

echo [2/3] Starting Trigger (DGLAB_REAL=%DGLAB_REAL%, DGLAB_LAN_IP=%DGLAB_LAN_IP%)...
start "Trigger Service" cmd /k "cd /d %TRIGGER% && uvicorn app:app --host 127.0.0.1 --port 18000"

timeout /t 4 /nobreak > nul

echo [3/3] Checking CUDA before Vision...
python -c "import torch; assert torch.cuda.is_available(), 'CUDA not available'" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================
    echo [WARN] CUDA not available - Vision will fall back to CPU
    echo        YOLO inference will be much slower on CPU
    echo        Check PYTORCH_INSTALL.md if you expected GPU
    echo ============================================
    echo.
)
echo [3/3] Starting Vision (SQUAD_SUPPRESSION_MODE=%SQUAD_SUPPRESSION_MODE%)...
start "Vision Detector" cmd /k "cd /d %VISION% && python realtime_detect_and_trigger.py"

echo.
echo ============================================
echo All three services launched.
echo Three new windows should be open:
echo   - DGLAB Backend
echo   - Trigger Service
echo   - Vision Detector
echo ============================================
echo.
pause
