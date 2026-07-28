@echo off
title SleepSense - Standalone Release APK
REM ── Builds a self-contained, shareable APK (JS bundled, debug-signed). ──
REM ── No Metro / no PC connection needed at runtime. Backend URLs are    ──
REM ── baked in from mobile/app.json -> expo.extra.{authUrl,analyticsUrl}.──
REM
REM Builds through a no-space junction (C:\snlb) because CMake/ninja for
REM react-native-fast-tflite fails on the space in "...\Nitu Chacha\...".
REM Uses bundled JDK 17 (system JDK 22 crashes Gradle). arm64-v8a only.

if not exist C:\snlb mklink /J C:\snlb "C:\Users\BIT\OneDrive\Desktop\Nitu Chacha\SnoreLab"

set "JAVA_HOME=C:\snlb\tools\jdk17\jdk-17.0.19+10"
set "ANDROID_HOME=C:\Users\BIT\Android\Sdk"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"

cd /d C:\snlb\mobile\android

echo ================================================
echo   Building standalone release APK (arm64-v8a)...
echo   (first run downloads Gradle deps - ~10-15 min)
echo ================================================
call gradlew.bat assembleRelease -PreactNativeArchitectures=arm64-v8a --no-daemon

echo.
echo EXIT_CODE=%ERRORLEVEL%
echo Output APK:
echo   mobile\android\app\build\outputs\apk\release\app-release.apk
