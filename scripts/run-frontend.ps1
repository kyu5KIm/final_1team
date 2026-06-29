$Root = "C:\Users\Playdata\Desktop\git\SKN24-FINAL-1Team"
$LogDir = "$Root\.runtime_logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null
Set-Location "$Root\frontend\hpm"
"[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] starting frontend on 127.0.0.1:5173" | Add-Content "$LogDir\frontend.log"
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort *>> "$LogDir\frontend.log"

