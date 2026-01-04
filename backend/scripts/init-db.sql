-- SIMS Plus - Database Initialization Script
-- This script runs on first PostgreSQL container startup

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create test database for pytest
CREATE DATABASE sims_plus_test;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE sims_plus TO postgres;
GRANT ALL PRIVILEGES ON DATABASE sims_plus_test TO postgres;

-- Optional: Create RLS helper function
CREATE OR REPLACE FUNCTION current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID;
END;
$$ LANGUAGE plpgsql STABLE;

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'SIMS Plus database initialized successfully';
END $$;
