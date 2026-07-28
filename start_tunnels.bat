@echo off
title SleepSense - Tunnels
REM ── Starts the public cloudflared tunnels (auth 8001, analytics 8002) in their ──
REM ── own persistent minimized windows. KEEP THEM OPEN during the demo.          ──
REM ── URLs are written to tools\tun_auth.log / tun_ana.log.                       ──
REM ── NOTE: each launch gets NEW random URLs, so the APK must be rebuilt to match.──
set "TOOLS=%~dp0tools"
del "%TOOLS%\tun_auth.log" "%TOOLS%\tun_ana.log" 2>nul
start "SleepSense Tunnel - AUTH 8001" /MIN cmd /c ""%TOOLS%\cloudflared.exe" tunnel --url http://localhost:8001 --no-autoupdate > "%TOOLS%\tun_auth.log" 2>&1"
start "SleepSense Tunnel - ANALYTICS 8002" /MIN cmd /c ""%TOOLS%\cloudflared.exe" tunnel --url http://localhost:8002 --no-autoupdate > "%TOOLS%\tun_ana.log" 2>&1"
echo Tunnels launching (minimized). URLs appear in:
echo   %TOOLS%\tun_auth.log
echo   %TOOLS%\tun_ana.log
echo Keep those windows open for the whole demo.
