-- Auth schema stub for standalone Docker PostgreSQL.
-- Uses DROP + CREATE instead of CREATE OR REPLACE to avoid type mismatch errors.

CREATE SCHEMA IF NOT EXISTS auth;

CREATE TABLE IF NOT EXISTS auth.users (
    id    uuid PRIMARY KEY,
    email text UNIQUE
);

DROP FUNCTION IF EXISTS auth.uid() CASCADE;
CREATE FUNCTION auth.uid() RETURNS uuid
LANGUAGE sql STABLE AS $$
  SELECT (NULLIF(current_setting('request.jwt.claims', true), '')::json->>'sub')::uuid
$$;

DROP FUNCTION IF EXISTS auth.role() CASCADE;
CREATE FUNCTION auth.role() RETURNS text
LANGUAGE sql STABLE AS $$
  SELECT NULLIF(current_setting('request.jwt.claims', true), '')::json->>'role'
$$;
