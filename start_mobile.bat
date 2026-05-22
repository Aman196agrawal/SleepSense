@echo off
title SleepSense - Mobile App (Expo)
cd /d "%~dp0mobile"
echo.
echo ================================================
echo   SleepSense - Mobile App
echo   Scan the QR code with Expo Go on your phone
echo   (Phone must be on the same WiFi)
echo ================================================
echo.
npx expo start
pause
