@echo off
title SleepSense - Analytics Service (Port 8002)
cd /d "C:\Users\BIT\OneDrive\Desktop\Nitu Chacha\SnoreLab\services\analytics-service"
set DATABASE_URL=sqlite:///./data/analytics.db
REM Local-dev convenience secret. Override via .env for any shared/remote use.
set SECRET_KEY=local-dev-only-not-for-production-use!!
echo.
echo ================================================
echo   SleepSense - Analytics Service
echo   Running on http://localhost:8002
echo   API Docs: http://localhost:8002/docs
echo ================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
pause
