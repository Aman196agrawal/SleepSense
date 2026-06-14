@echo off
title SleepSense - Standalone Release APK
REM ── Builds a self-contained, shareable APK (JS bundled, debug-signed). ──
REM ── No Metro / no PC connection needed at runtime. Backend URLs are    ──
REM ── baked in from mobile/app.json -> expo.extra.{authUrl,analyticsUrl}.──

set "JAVA_HOME=%~dp0tools\jdk-17.0.13+11"
set "ANDROID_HOME=C:\Users\BIT\Android\Sdk"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"

cd /d "%~dp0mobile\android"

echo ================================================
echo   Building standalone release APK...
echo   (first run downloads Gradle deps - ~10-15 min)
echo ================================================
call gradlew.bat assembleRelease --no-daemon

echo.
echo Output APK:
echo   mobile\android\app\build\outputs\apk\release\app-release.apk
pause
