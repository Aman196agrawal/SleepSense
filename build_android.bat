@echo off
title SleepSense - Android Dev Build
cd /d "%~dp0mobile"

REM ── Use the portable JDK 17 we downloaded (React Native 0.81 needs JDK 17, ──
REM ── not your system JDK 22, which crashes the Gradle build).               ──
set "JAVA_HOME=%~dp0tools\jdk-17.0.13+11"
set "ANDROID_HOME=C:\Users\BIT\Android\Sdk"
set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"

REM ── Make the installed app reach Metro + the backend over your Wi-Fi LAN IP ──
set "REACT_NATIVE_PACKAGER_HOSTNAME=192.168.1.27"

echo ================================================
echo   SleepSense - Android Dev Build
echo ================================================
echo.
echo Using JDK 17:
java -version
echo.
echo Connected devices (your phone should be listed below):
adb devices
echo.
echo If no device is listed, plug in your phone with USB debugging ON,
echo accept the "Allow USB debugging?" prompt, then re-run this file.
echo.
echo Starting build + install. First run downloads Gradle and compiles
echo everything - this takes about 10-15 minutes. Leave it running.
echo.
call npx expo run:android
echo.
echo ================================================
echo   Done. If the app installed, you can now test
echo   "Continue with Google" on your phone.
echo ================================================
pause
