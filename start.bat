@echo off
chcp 65001 >nul
echo ========================================
echo   New Three Kingdoms
echo ========================================

cd /d "%~dp0backend"
start "Backend" cmd /k "python main.py"

cd /d "%~dp0frontend"
start "Frontend" cmd /k "npm run dev"

echo Backend : http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Both windows started. Close them to stop services.
