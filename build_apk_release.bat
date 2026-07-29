@echo off
setlocal EnableExtensions
title SleepSense - Standalone Release APK
REM ── Builds a self-contained, shareable APK (JS bundled, debug-signed). ──
REM ── No Metro / no PC connection needed at runtime. Backend URLs are    ──
REM ── seeded from mobile/app.json -> expo.extra.{authUrl,analyticsUrl}   ──
REM ── and can be changed later in-app via Profile > Backend URLs.        ──
REM
REM Builds through a no-space junction (C:\snlb) because CMake/ninja for
REM react-native-fast-tflite fails on the space in "...\Nitu Chacha\...".
REM Uses bundled JDK 17 (system JDK 22 crashes Gradle). arm64-v8a only.

REM The repo root is wherever this script lives, so moving or renaming the
REM folder no longer silently builds a stale copy through an old junction.
set "SRC=%~dp0"
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "LINK=C:\snlb"

if not exist "%LINK%" goto make_link

REM %LINK% already exists — make sure it still points at THIS checkout. A
REM junction left over from a previous location is the whole failure mode we
REM are guarding against: the build would quietly succeed against old sources.
set "LINKTGT="
for /f "usebackq delims=" %%T in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Get-Item -LiteralPath '%LINK%' -Force).Target } catch { }"`) do set "LINKTGT=%%T"
if not defined LINKTGT goto link_not_a_link
if /I "%LINKTGT%"=="%SRC%" goto link_ok
goto link_mismatch

:make_link
mklink /J "%LINK%" "%SRC%" >nul
if errorlevel 1 goto link_failed
if not exist "%LINK%\mobile\android\gradlew.bat" goto link_bad_content
echo Created junction %LINK% -^> %SRC%

:link_ok
set "JAVA_HOME=%LINK%\tools\jdk17\jdk-17.0.19+10"
if not exist "%JAVA_HOME%\bin\java.exe" goto no_jdk

REM Honour a pre-set SDK location; otherwise assume the default install path.
if not defined ANDROID_HOME set "ANDROID_HOME=%USERPROFILE%\Android\Sdk"
if not exist "%ANDROID_HOME%\platform-tools" goto no_sdk

set "PATH=%JAVA_HOME%\bin;%ANDROID_HOME%\platform-tools;%PATH%"

cd /d "%LINK%\mobile\android"
if errorlevel 1 goto no_project

echo ================================================
echo   Building standalone release APK (arm64-v8a)...
echo   Source: %SRC%
echo   (first run downloads Gradle deps - ~10-15 min)
echo ================================================
call gradlew.bat assembleRelease -PreactNativeArchitectures=arm64-v8a --no-daemon
set "BUILD_RC=%ERRORLEVEL%"

echo.
echo EXIT_CODE=%BUILD_RC%
if not "%BUILD_RC%"=="0" (
  echo BUILD FAILED - see the Gradle output above.
  exit /b %BUILD_RC%
)
echo Output APK:
echo   %SRC%\mobile\android\app\build\outputs\apk\release\app-release.apk
exit /b 0

REM ── Failure paths ────────────────────────────────────────────────────────
REM Each of these stops the build. Carrying on would either compile the wrong
REM source tree or fail much later with an unrelated-looking error.

:link_failed
echo.
echo ERROR: could not create the junction %LINK% -^> %SRC%
echo.
echo   mklink /J does not need administrator rights, so this usually means
echo   %LINK% is in use, or C:\ is not writable by this account.
echo   Try: rmdir "%LINK%"   then re-run this script.
exit /b 1

:link_bad_content
echo.
echo ERROR: %LINK% was created but %LINK%\mobile\android\gradlew.bat is missing.
echo.
echo   This script must live in the repository root (next to the mobile\
echo   directory). It resolved the repo root as:
echo     %SRC%
exit /b 1

:link_not_a_link
echo.
echo ERROR: %LINK% already exists and is a real directory, not a junction.
echo.
echo   Refusing to touch it - it may contain real data. Move or delete it
echo   yourself, then re-run this script.
exit /b 1

:link_mismatch
echo.
echo ERROR: %LINK% is a junction pointing at a different checkout.
echo.
echo   points at : %LINKTGT%
echo   expected  : %SRC%
echo.
echo   Building anyway would produce an APK from the OTHER folder. Remove the
echo   stale junction and re-run this script:
echo     rmdir "%LINK%"
exit /b 1

:no_jdk
echo.
echo ERROR: bundled JDK 17 not found at
echo   %JAVA_HOME%
echo.
echo   The system JDK is not a substitute - JDK 22 crashes Gradle here.
echo   Restore tools\jdk17\ in the repo root.
exit /b 1

:no_sdk
echo.
echo ERROR: Android SDK not found at
echo   %ANDROID_HOME%
echo.
echo   Set ANDROID_HOME to your SDK location and re-run, e.g.
echo     set "ANDROID_HOME=D:\Android\Sdk"
exit /b 1

:no_project
echo.
echo ERROR: could not enter %LINK%\mobile\android
exit /b 1
