@echo off
echo.
echo ============================================================
echo  I4C Cybercrime Predictive Cash-Out Decision Support System
echo  PS ID 26184 - Smart India Hackathon
echo ============================================================
echo.

:: Move to the project directory
cd /d "C:\Users\kisha\.gemini\antigravity-ide\scratch\i4c_hotspot_predictor"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and try again.
    pause
    exit /b 1
)

echo [1/3] Checking dependencies...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies. Check your internet connection.
    pause
    exit /b 1
)
echo       Dependencies OK.
echo.

echo [2/3] Starting FastAPI server on http://127.0.0.1:8000 ...
echo.
echo  ----------------------------------------------------------
echo   Dashboard URL : http://127.0.0.1:8000
echo   API Docs      : http://127.0.0.1:8000/docs
echo   Press Ctrl+C to stop the server
echo  ----------------------------------------------------------
echo.

echo [3/3] Opening dashboard in default browser in 2 seconds...
timeout /t 2 /nobreak >nul
start "" "http://127.0.0.1:8000"

:: Start uvicorn (this blocks until Ctrl+C)
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

echo.
echo Server stopped.
pause
