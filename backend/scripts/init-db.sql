-- ============================================================
-- SIMS Plus - Database Initialization Script
-- ============================================================
-- Runs ONCE on first PostgreSQL container startup
-- via Docker's /docker-entrypoint-initdb.d/ mechanism.
--
-- Creates:
--   1. sims_admin user (owns database, runs migrations)
--   2. sims_app_user (runtime app user, RLS enforced)
--   3. Main database + test database
--   4. Extensions (uuid-ossp, pgcrypto)
--   5. RLS helper functions
--   6. Grants for both users
--
-- SECURITY: Two-user pattern (INV-1)
--   - sims_admin: DDL operations (CREATE TABLE, ALTER TABLE)
--   - sims_app_user: DML only (SELECT, INSERT, UPDATE, DELETE)
--   - RLS is enforced ONLY for sims_app_user (non-superuser)
-- ============================================================

-- ============================================================
-- 1. Create database users
-- ============================================================
-- sims_admin: Owns the database, runs Alembic migrations
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sims_admin') THEN
        CREATE ROLE sims_admin WITH LOGIN PASSWORD 'admin_password' CREATEDB;
    END IF;
END $$;

-- sims_app_user: Runtime application user, RLS enforced
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sims_app_user') THEN
        CREATE ROLE sims_app_user WITH LOGIN PASSWORD 'app_password';
    END IF;
END $$;

-- ============================================================
-- 2. Create test database
-- ============================================================
CREATE DATABASE sims_plus_test OWNER sims_admin;

-- ============================================================
-- 3. Main database setup (sims_plus)
-- ============================================================
-- We are already connected to sims_plus (POSTGRES_DB)

-- Transfer ownership to sims_admin
ALTER DATABASE sims_plus OWNER TO sims_admin;

-- Extensions (must be created by superuser)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- 4. RLS helper functions (main database)
-- ============================================================
-- NOTE: Functions are created by Alembic migrations, NOT here.
-- This avoids parameter name conflicts between init-db.sql and migrations.
-- The test database (below) still creates them since migrations don't run there.

-- ============================================================
-- 5. Grants for sims_admin (main database)
-- ============================================================
GRANT ALL PRIVILEGES ON DATABASE sims_plus TO sims_admin;
GRANT ALL PRIVILEGES ON SCHEMA public TO sims_admin;

-- ============================================================
-- 6. Grants for sims_app_user (main database)
-- ============================================================
GRANT CONNECT ON DATABASE sims_plus TO sims_app_user;
GRANT USAGE ON SCHEMA public TO sims_app_user;

-- Grant on existing tables (if any exist at init time)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sims_app_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user;

-- Grant on future tables (created by sims_admin via Alembic)
ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO sims_app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

-- Also grant defaults for tables created by postgres superuser
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

-- Note: Function grants are handled by DEFAULT PRIVILEGES above.
-- Explicit grants will be added by migrations when functions are created.

-- ============================================================
-- 7. Test database setup (sims_plus_test)
-- ============================================================
\c sims_plus_test

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- RLS helper functions (replicated for test database)
CREATE OR REPLACE FUNCTION set_tenant_context(p_tenant_id UUID)
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', p_tenant_id::TEXT, true);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION clear_tenant_context()
RETURNS VOID AS $$
BEGIN
    PERFORM set_config('app.current_tenant_id', '', true);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
DECLARE
    tenant_str TEXT;
    tenant_uuid UUID;
BEGIN
    tenant_str := current_setting('app.current_tenant_id', true);

    IF tenant_str IS NULL OR tenant_str = '' THEN
        RETURN NULL;
    END IF;

    BEGIN
        tenant_uuid := tenant_str::UUID;
        RETURN tenant_uuid;
    EXCEPTION WHEN OTHERS THEN
        RETURN NULL;
    END;
END;
$$ LANGUAGE plpgsql STABLE;

-- Grants for sims_admin (test database)
GRANT ALL PRIVILEGES ON DATABASE sims_plus_test TO sims_admin;
GRANT ALL PRIVILEGES ON SCHEMA public TO sims_admin;

-- Grants for sims_app_user (test database)
GRANT CONNECT ON DATABASE sims_plus_test TO sims_app_user;
GRANT USAGE ON SCHEMA public TO sims_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sims_app_user;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO sims_app_user;

ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO sims_app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE sims_admin IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO sims_app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO sims_app_user;

GRANT EXECUTE ON FUNCTION set_tenant_context(UUID) TO sims_app_user;
GRANT EXECUTE ON FUNCTION clear_tenant_context() TO sims_app_user;
GRANT EXECUTE ON FUNCTION get_current_tenant_id() TO sims_app_user;

-- ============================================================
-- 8. Switch back to main database and confirm
-- ============================================================
\c sims_plus

DO $$
BEGIN
    RAISE NOTICE '============================================================';
    RAISE NOTICE 'SIMS Plus database initialization complete.';
    RAISE NOTICE '';
    RAISE NOTICE 'Created:';
    RAISE NOTICE '  - Database: sims_plus (owner: sims_admin)';
    RAISE NOTICE '  - Database: sims_plus_test (owner: sims_admin)';
    RAISE NOTICE '  - Role: sims_admin (DDL, migrations)';
    RAISE NOTICE '  - Role: sims_app_user (DML, RLS enforced)';
    RAISE NOTICE '  - Functions: set_tenant_context(), clear_tenant_context(),';
    RAISE NOTICE '               get_current_tenant_id()';
    RAISE NOTICE '';
    RAISE NOTICE 'IMPORTANT: Backend MUST connect as sims_app_user.';
    RAISE NOTICE '           Alembic migrations use sims_admin.';
    RAISE NOTICE '============================================================';
END $$;
