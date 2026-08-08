@echo off
chcp 65001 >nul
echo ========================================
echo   Stopping New Three Kingdoms
echo ========================================

rem -- Backend: kill uvicorn reloader parent + worker --
rem NOTE: python main.py starts uvicorn with reload=True, which spawns a
rem reloader parent. Killing only the worker leaves the reloader to respawn
rem it. So we match by command line and kill all related processes at once.
echo Stopping backend (uvicorn reloader + worker)...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'main:app' -or $_.CommandLine -match 'main\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

rem -- Frontend: kill vite dev server --
echo Stopping frontend (vite on :5173)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    taskkill /f /pid %%a >nul 2>&1
    echo   Frontend stopped (PID: %%a)
)

echo.
echo All services stopped.
pause
