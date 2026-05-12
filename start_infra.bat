@echo off
echo Starting infrastructure services (PostgreSQL, Redis, Kafka, InfluxDB, MinIO)...
echo This may take 1-2 minutes on first run while images are downloaded.
echo.

docker compose up postgres redis kafka influxdb minio -d

echo.
echo Waiting for services to be healthy...
timeout /t 15 /nobreak > nul

echo.
echo Infrastructure ready!
echo.
echo   PostgreSQL  : localhost:5432   (user: postgres / pass: devpassword / db: sleepsense)
echo   Redis       : localhost:6379
echo   Kafka       : localhost:9092
echo   InfluxDB    : http://localhost:8086   (admin / devpassword123)
echo   MinIO S3    : http://localhost:9000   (minioadmin / minioadmin)
echo   MinIO UI    : http://localhost:9001
echo.
echo To start application services in Docker too:
echo   docker compose up auth-service analytics-service -d
echo.
echo To start application services locally (for dev with hot-reload):
echo   start_auth.bat
echo   start_analytics.bat
