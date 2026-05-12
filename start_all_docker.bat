@echo off
echo Starting full SleepSense stack via Docker Compose...
echo.
docker compose up --build -d
echo.
echo Stack is coming up. Check service health with:
echo   docker compose ps
echo   docker compose logs -f auth-service
echo   docker compose logs -f analytics-service
echo.
echo Service URLs:
echo   Auth Service      : http://localhost:8001/docs
echo   Analytics Service : http://localhost:8002/docs
echo   InfluxDB UI       : http://localhost:8086
echo   MinIO Console     : http://localhost:9001
