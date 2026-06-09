SELECT 'CREATE DATABASE sleepsense_ingestion'    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sleepsense_ingestion'   )\gexec
SELECT 'CREATE DATABASE sleepsense_inference'    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sleepsense_inference'   )\gexec
SELECT 'CREATE DATABASE sleepsense_notifications' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sleepsense_notifications')\gexec
SELECT 'CREATE DATABASE sleepsense_insights'     WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'sleepsense_insights'    )\gexec
