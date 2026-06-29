$Root = "C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"
$PythonExe = "C:\Users\Playdata\miniconda3\envs\hpm_test_1\python.exe"
$env:PYTHONPATH = "$Root\.runtime_pydeps\hpm_test_1;$env:PYTHONPATH"
$env:PYTHONIOENCODING = "utf-8"
$LogDir = "$Root\.runtime_logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
Set-Location "$Root\backend\hpm"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] starting Django backend on 127.0.0.1:8000" | Add-Content "$LogDir\backend.log"
& $PythonExe manage.py runserver 127.0.0.1:8000 --noreload *>> "$LogDir\backend.log"

