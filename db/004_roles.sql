\set ON_ERROR_STOP on
-- Requires an administrator with CREATEROLE and ownership of this database/views.
-- Database-scoped hardening: PUBLIC loses TEMP and public-schema CREATE.
-- Review this effect if other applications share this database.
BEGIN;
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='sql_rag_sales') THEN
        CREATE ROLE sql_rag_sales NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='sql_rag_analyst') THEN
        CREATE ROLE sql_rag_analyst NOLOGIN;
    END IF;
END $$;
ALTER ROLE sql_rag_sales NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 8;
ALTER ROLE sql_rag_analyst NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT CONNECTION LIMIT 8;
-- Roles are cluster-wide; a pre-existing role must have no memberships.
DO $$ BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r
        ON r.oid=m.member WHERE r.rolname IN ('sql_rag_sales','sql_rag_analyst')) THEN
        RAISE EXCEPTION 'Dedicated API roles must not be members of any other role';
    END IF;
END $$;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE TEMPORARY ON DATABASE :"DBNAME" FROM PUBLIC;
REVOKE ALL ON DATABASE :"DBNAME" FROM sql_rag_sales, sql_rag_analyst;
GRANT CONNECT ON DATABASE :"DBNAME" TO sql_rag_sales, sql_rag_analyst;
REVOKE ALL ON SCHEMA public FROM sql_rag_sales, sql_rag_analyst;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM sql_rag_sales, sql_rag_analyst;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM sql_rag_sales, sql_rag_analyst;
REVOKE ALL ON SCHEMA analytics FROM sql_rag_sales, sql_rag_analyst;
GRANT USAGE ON SCHEMA analytics TO sql_rag_sales, sql_rag_analyst;
REVOKE ALL ON ALL TABLES IN SCHEMA analytics FROM sql_rag_sales, sql_rag_analyst;
GRANT SELECT ON analytics.orders, analytics.order_items, analytics.products, analytics.sellers
    TO sql_rag_sales, sql_rag_analyst;
GRANT SELECT ON analytics.reviews TO sql_rag_analyst;
-- No blanket/default SELECT grant: new views need an explicit reviewed grant.
ALTER ROLE sql_rag_sales SET default_transaction_read_only = on;
ALTER ROLE sql_rag_analyst SET default_transaction_read_only = on;
ALTER ROLE sql_rag_sales SET search_path = pg_catalog;
ALTER ROLE sql_rag_analyst SET search_path = pg_catalog;
ALTER ROLE sql_rag_sales SET statement_timeout = '3s';
ALTER ROLE sql_rag_analyst SET statement_timeout = '3s';
ALTER ROLE sql_rag_sales SET idle_in_transaction_session_timeout = '5s';
ALTER ROLE sql_rag_analyst SET idle_in_transaction_session_timeout = '5s';
COMMIT;
