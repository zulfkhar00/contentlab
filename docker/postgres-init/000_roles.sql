-- Supabase-compatible roles for standalone Docker PostgreSQL.
-- The domain + job-infrastructure migrations REVOKE/GRANT against these
-- roles, so they must exist before those files run. Sorts before
-- 00_auth_schema.sql so the postgres entrypoint runs it first.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        CREATE ROLE anon NOINHERIT NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        CREATE ROLE authenticated NOINHERIT NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
        CREATE ROLE service_role NOINHERIT NOLOGIN BYPASSRLS;
    END IF;
END
$$;
