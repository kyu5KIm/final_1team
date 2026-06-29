@echo off
setlocal

set "ROOT=C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"
set "LOG_DIR=%ROOT%\.runtime_logs"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

cd /d "%ROOT%\frontend\hpm"
echo [%date% %time%] starting frontend on 127.0.0.1:5173>> "%LOG_DIR%\frontend.log"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort >> "%LOG_DIR%\frontend.log" 2>&1
