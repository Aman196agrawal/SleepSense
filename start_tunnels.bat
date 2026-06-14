@echo off
title SleepSense — Tunnels
REM Starts cloudflared tunnels for all 3 services and auto-restarts them if they die.
REM Keep this window open while your mentor is testing.

set "CF=%~dp0tools\cloudflared.exe"

echo Starting tunnels...
echo (URLs will appear below — they change each restart, so rebuild the APK after restarting)
echo.

:loop
start "" /B "%CF%" tunnel --url http://localhost:8001 2>&1 | findstr /i "trycloudflare" & echo [auth]
start "" /B "%CF%" tunnel --url http://localhost:8002 2>&1 | findstr /i "trycloudflare" & echo [analytics]
start "" /B "%CF%" tunnel --url http://localhost:8003 2>&1 | findstr /i "trycloudflare" & echo [ingestion]

REM Wait 60 seconds then check if processes are still alive
timeout /t 60 /nobreak >nul
tasklist | findstr /i "cloudflared" >nul
if errorlevel 1 (
    echo Tunnels died — restarting...
    goto loop
)
goto loop
