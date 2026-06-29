@echo off
setlocal

set "ROOT=C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"
set "PYTHON_EXE=C:\Users\Playdata\miniconda3\envs\hpm_test_1\python.exe"
set "PYTHONPATH=%ROOT%\.runtime_pydeps\hpm_test_1;%PYTHONPATH%"
set "PYTHONIOENCODING=utf-8"
set "LOG_DIR=%ROOT%\.runtime_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%ROOT%\backend\hpm"
echo [%date% %time%] starting Django backend on 127.0.0.1:8000>> "%LOG_DIR%\backend.log"
"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000 --noreload >> "%LOG_DIR%\backend.log" 2>&1
