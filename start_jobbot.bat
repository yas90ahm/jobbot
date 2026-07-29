@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Please run setup.bat first ^(one time only^).
  pause
  exit /b 1
)
echo jobbot is running - your browser will open in a moment.
echo Keep this window open while you use it. Close it to stop jobbot.
.venv\Scripts\python -m jobbot web
pause
