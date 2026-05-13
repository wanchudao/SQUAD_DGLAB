@echo off
title SQUAD_DGLAB Launcher

set "ROOT=%~dp0"
set "BACKEND=%ROOT%official_v2\socket\v2\backend"
set "TRIGGER=%ROOT%python_trigger"
set "NMOD=node_modules"

echo Project root: %ROOT%
echo Backend path: %BACKEND%
echo Trigger path: %TRIGGER%
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

REM ---- Choose mode ----
echo Choose mode:
echo   1 = Mock
echo   2 = Real
set /p MODE=Enter 1 or 2:

set REAL=0
if "%MODE%"=="2" set REAL=1

echo.
echo Selected: MODE=%MODE%, DGLAB_REAL=%REAL%
echo.

REM ---- Real mode warning ----
if "%REAL%"=="1" goto REAL_WARN
goto START_SERVICES

:REAL_WARN
echo !!! WARNING: REAL DEVICE MODE !!!
echo Set strength limit in DG-LAB APP first.
echo Press Ctrl+C to abort, or any key to continue...
pause > nul

:START_SERVICES
echo.
echo Starting Backend...
start "DGLAB Backend" cmd /k "cd /d %BACKEND% && npm start"

timeout /t 3 /nobreak > nul

REM ---- Set DGLAB_REAL in parent shell so child cmd inherits it ----
set DGLAB_REAL=%REAL%

echo Starting Trigger (DGLAB_REAL=%DGLAB_REAL%)...
start "Trigger Service" cmd /k "cd /d %TRIGGER% && uvicorn app:app --host 127.0.0.1 --port 18000"

echo.
echo Done. Check the two new windows.
pause
