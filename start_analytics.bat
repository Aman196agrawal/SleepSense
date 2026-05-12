@echo off
title Product Gem - Analytics Service (Port 8002)
cd /d "C:\Users\BIT\OneDrive\Desktop\Nitu Chacha\SnoreLab\services\analytics-service"
set DATABASE_URL=sqlite:///./data/analytics.db
set SECRET_KEY=product-gem-dev-secret-key-32chars!!
echo.
echo ================================================
echo   Product Gem - Analytics Service
echo   Running on http://localhost:8002
echo   API Docs: http://localhost:8002/docs
echo ================================================
echo.
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
pause
