@echo off
cd /d "%~dp0"
echo ============================================
echo  jobbot one-time setup
echo ============================================
where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python is not installed.
  echo 1. Go to https://www.python.org/downloads and install it.
  echo 2. IMPORTANT: tick "Add python.exe to PATH" during install.
  echo 3. Double-click this file again.
  pause
  exit /b 1
)
echo This takes a few minutes the first time. Leave this window open.
echo.
echo [1/3] Creating a private Python environment...
python -m venv .venv
if errorlevel 1 ( echo Setup failed at the environment step. & pause & exit /b 1 )
echo [2/3] Installing packages...
.venv\Scripts\python -m pip install --quiet -r requirements.txt
if errorlevel 1 ( echo Package install failed - check your internet connection and rerun. & pause & exit /b 1 )
echo [3/3] Installing the browser used to fill application forms...
.venv\Scripts\python -m playwright install chromium
if errorlevel 1 ( echo Browser install failed - check your internet connection and rerun. & pause & exit /b 1 )
echo.
echo ============================================
echo  Done! Double-click start_jobbot.bat to use it.
echo ============================================
pause
