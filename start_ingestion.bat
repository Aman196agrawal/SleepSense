@echo off
title SleepSense - Audio Ingestion Service (Port 8003)
cd /d "%~dp0services\audio-ingestion-service"
REM Config comes from services\audio-ingestion-service\.env — SECRET_KEY there
REM must match auth and analytics or their JWTs will not validate here.
REM
REM By default that .env sets AUDIO_STORAGE_BACKEND=local, so chunk audio is
REM written to data\audio\<user_id>\<session_id>\ as plain files. No Docker or
REM MinIO needed. Switch to AUDIO_STORAGE_BACKEND=s3 for the compose stack.
echo.
echo ================================================
echo   SleepSense - Audio Ingestion Service
echo   Running on http://localhost:8003
echo   API Docs: http://localhost:8003/docs
echo   Readiness: http://localhost:8003/ready
echo   Audio out: services\audio-ingestion-service\data\audio\
echo ================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
pause
