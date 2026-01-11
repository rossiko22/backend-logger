-- 1. Create the database (skip if already created)
CREATE DATABASE api_service_db;

-- 2. Create a user with password (adjust password as needed)
CREATE USER api_user WITH PASSWORD 'yourpassword';

-- 3. Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE api_service_db TO api_user;

-- 4. Connect to the database
\c api_service_db

DROP TABLE IF EXISTS api_calls;

CREATE TABLE api_calls (
    id SERIAL PRIMARY KEY,
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    ip_address TEXT,
    request_body JSONB,
    status_code INTEGER,
    called_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Optional: check table structure
\d api_calls
