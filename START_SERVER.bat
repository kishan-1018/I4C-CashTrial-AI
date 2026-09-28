@echo off
title I4C Cybercrime Predictive Cash-Out Decision Support System
echo.
echo ===============================================================================
echo   I4C Cybercrime Predictive Cash-Out Decision Support System
echo   Smart India Hackathon 2026 - Problem Statement ID: 26184
echo ===============================================================================
echo.

:: Move to the project root directory
cd /d "%~dp0"

:: Check if Python is installed and accessible
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found on PATH!
    echo Please install Python 3.10+ and add it to your System PATH.
    echo.
    pause
    exit /b 1
)

echo [1/3] Verifying Python runtime and installed packages...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [WARNING] Dependency check encountered issues. Proceeding to launch...
) else (
    echo       Dependencies verified successfully.
)
echo.

echo ===============================================================================
echo   LOGIN CREDENTIALS & ACCESS TIERS
echo ===============================================================================
echo   [TIER 1] Public Citizen / Victim Portal :
echo            - URL        : http://127.0.0.1:8000 (Default Landing Page)
echo            - Access     : Unauthenticated / Public Complainant
echo.
echo   [TIER 2] Law Enforcement Investigator Console :
echo            - Username   : investigator
echo            - Password   : investigator123
echo            - Alternative: officer / investigator123 (ACP Priya Deshmukh)
echo.
echo   [TIER 3] System Administrator Console :
echo            - Username   : admin
echo            - Password   : admin123
echo            - Alternative: sysadmin / admin123 (Senior Ops Engineer)
echo.
echo ===============================================================================
echo   SERVER ACCESS ENDPOINTS
echo ===============================================================================
echo   * Main Dashboard  : http://127.0.0.1:8000
echo   * Interactive API : http://127.0.0.1:8000/docs
echo   * Audit Ledger    : http://127.0.0.1:8000/api/audit-ledger
echo   * Stop Server     : Press Ctrl+C in this console window
echo ===============================================================================
echo.

echo [2/3] Launching background browser trigger (opens in 3 seconds)...
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

echo [3/3] Starting FastAPI Uvicorn ASGI Server on http://127.0.0.1:8000 ...
echo.
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload

echo.
echo Server has stopped.
pause
