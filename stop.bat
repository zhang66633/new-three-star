@echo off
chcp 65001 >nul
echo ========================================
echo   Stopping New Three Kingdoms
echo ========================================

echo Stopping backend (port 8000)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo   Backend stopped (PID: %%a)
)

echo Stopping frontend (port 5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo   Frontend stopped (PID: %%a)
)

echo.
echo All services stopped.
pause
