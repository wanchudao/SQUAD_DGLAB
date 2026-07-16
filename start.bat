@echo off
setlocal

cd /d "%~dp0"

set "BOOTSTRAP_LOG=%~dp0bootstrap.log"
set "PYTHON_EXE="
set "EXIT_CODE=0"

>>"%BOOTSTRAP_LOG%" echo ============================================================
>>"%BOOTSTRAP_LOG%" echo [%DATE% %TIME%] squad_dglab bootstrap start
>>"%BOOTSTRAP_LOG%" echo script_dir=%~dp0
>>"%BOOTSTRAP_LOG%" echo cwd=%CD%

where python >>"%BOOTSTRAP_LOG%" 2>&1
where py >>"%BOOTSTRAP_LOG%" 2>&1

for /f "delims=" %%I in ('where python 2^>nul') do (
    if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
)

if not defined PYTHON_EXE (
    for /f "usebackq delims=" %%I in (`py -3 -c "import sys; print(sys.executable)" 2^>nul`) do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
    )
)

if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python311\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Program Files\Python311\python.exe" set "PYTHON_EXE=C:\Program Files\Python311\python.exe"
if not defined PYTHON_EXE if exist "C:\Python311\python.exe" set "PYTHON_EXE=C:\Python311\python.exe"

if not defined PYTHON_EXE (
    >>"%BOOTSTRAP_LOG%" echo [ERROR] python executable not found
    exit /b 9009
)

>>"%BOOTSTRAP_LOG%" echo python_exe=%PYTHON_EXE%
>>"%BOOTSTRAP_LOG%" echo launching="%PYTHON_EXE%" "%~dp0main.py"

"%PYTHON_EXE%" "%~dp0main.py" >>"%BOOTSTRAP_LOG%" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

>>"%BOOTSTRAP_LOG%" echo exit_code=%EXIT_CODE%

exit /b %EXIT_CODE%
