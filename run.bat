@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.10+ and check "Add to PATH".
  pause
  exit /b 1
)
echo Installing dependencies if needed...
python -m pip install -q -r requirements.txt
echo.
echo Starting BALMORES STRUX AI at http://127.0.0.1:8000
echo Close this window to stop the server.
echo.
python -m uvicorn app:app --host 127.0.0.1 --port 8000
