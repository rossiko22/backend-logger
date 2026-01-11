-- 1. Create the database (skip if already created)
CREATE DATABASE api_service_db;

-- 2. Create a user with password (adjust password as needed)
CREATE USER api_user WITH PASSWORD 'yourpassword';

-- 3. Grant all privileges on the database to the user
GRANT ALL PRIVILEGES ON DATABASE api_service_db TO api_user;

-- 4. Connect to the database
\c api_service_db

-- 5. Create the table to log API calls
CREATE TABLE api_calls (
    id SERIAL PRIMARY KEY,                  -- Auto-increment ID
    endpoint VARCHAR(255) NOT NULL,        -- API endpoint called
    method VARCHAR(10) NOT NULL,           -- HTTP method (GET, POST, etc.)
    ip_address VARCHAR(45) NOT NULL,       -- IPv4 or IPv6 of the caller
    request_body JSONB,                    -- POST request body (optional)
    status_code INT,                       -- HTTP response status code
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP -- Timestamp of call
);

-- Optional: check table structure
\d api_calls
