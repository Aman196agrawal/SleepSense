@echo off
title SleepSense - Auth Service (Port 8001)
cd /d "C:\Users\BIT\OneDrive\Desktop\Nitu Chacha\SnoreLab\services\auth-service"
set DATABASE_URL=sqlite:///./data/auth.db
set SECRET_KEY=sleepsense-dev-secret-key-32chars!!
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
