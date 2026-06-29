@echo off
setlocal

set "ROOT=C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"
set "PYTHON_EXE=C:\Users\Playdata\miniconda3\envs\hpm_test_1\python.exe"
set "PYTHONPATH=%ROOT%\.runtime_pydeps\hpm_test_1;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
set "LOG_DIR=%ROOT%\.runtime_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%ROOT%\test_flow"
echo [%date% %time%] starting test_flow FastAPI on 127.0.0.1:8500>> "%LOG_DIR%\test-flow.log"
"%PYTHON_EXE%" -m uvicorn app:app --host 127.0.0.1 --port 8500 >> "%LOG_DIR%\test-flow.log" 2>&1
