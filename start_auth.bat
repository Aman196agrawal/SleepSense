@echo off
title SleepSense - Auth Service (Port 8001)
cd /d "%~dp0services\auth-service"
set DATABASE_URL=sqlite:///./data/auth.db
REM Local-dev convenience secret. Override via .env for any shared/remote use.
set SECRET_KEY=local-dev-only-not-for-production-use!!
set ACCESS_TOKEN_EXPIRE_MINUTES=60
set REFRESH_TOKEN_EXPIRE_DAYS=30
echo.
echo ================================================
echo   SleepSense - Auth Service
echo   Running on http://localhost:8001
echo   API Docs: http://localhost:8001/docs
echo ================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
pause
