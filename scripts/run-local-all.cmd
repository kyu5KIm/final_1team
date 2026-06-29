@echo off
setlocal

set "ROOT=C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"

start "hpm-test-flow-8500" /min powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run-test-flow.ps1"
start "hpm-backend-8000" /min powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run-backend.ps1"
start "hpm-frontend-5173" /min powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%ROOT%\scripts\run-frontend.ps1"

echo Started local services:
echo - test_flow FastAPI: http://127.0.0.1:8500
echo - Django backend:    http://127.0.0.1:8000
echo - Frontend:          http://127.0.0.1:5173
