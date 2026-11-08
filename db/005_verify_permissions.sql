\set ON_ERROR_STOP on
-- Run as each restricted login; every returned check must be true.
SELECT current_user AS login,
    current_user IN ('sql_rag_sales','sql_rag_analyst') AS dedicated_login,
    current_setting('default_transaction_read_only') = 'on' AS read_only_default,
    NOT pg_catalog.has_database_privilege(current_user,current_database(),'CREATE') AS no_database_create,
    NOT pg_catalog.has_database_privilege(current_user,current_database(),'TEMP') AS no_temp,
    NOT pg_catalog.has_schema_privilege(current_user,'public','CREATE') AS no_public_create,
    NOT pg_catalog.has_schema_privilege(current_user,'analytics','CREATE') AS no_analytics_create,
    NOT pg_catalog.has_table_privilege(current_user,'public.orders','SELECT') AS no_base_read,
    NOT pg_catalog.has_table_privilege(current_user,'analytics.orders','UPDATE') AS no_view_write,
    pg_catalog.has_table_privilege(current_user,'analytics.orders','SELECT') AS approved_read,
    (pg_catalog.has_table_privilege(current_user,'analytics.reviews','SELECT') =
        (current_user='sql_rag_analyst')) AS review_policy_matches;
DO $$ BEGIN
    IF current_user NOT IN ('sql_rag_sales','sql_rag_analyst') THEN
        RAISE EXCEPTION 'Verification must connect as a restricted API login';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=current_user
        AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls)) THEN
        RAISE EXCEPTION 'API login has dangerous role flags';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_auth_members WHERE member =
        (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=current_user)) THEN
        RAISE EXCEPTION 'API login must not have role memberships';
    END IF;
    IF pg_catalog.has_table_privilege(current_user,'public.orders','SELECT')
       OR current_setting('default_transaction_read_only') <> 'on'
       OR pg_catalog.has_database_privilege(current_user,current_database(),'CREATE')
       OR pg_catalog.has_database_privilege(current_user,current_database(),'TEMP')
       OR pg_catalog.has_schema_privilege(current_user,'public','CREATE')
       OR pg_catalog.has_schema_privilege(current_user,'analytics','CREATE')
       OR NOT pg_catalog.has_table_privilege(current_user,'analytics.orders','SELECT')
       OR pg_catalog.has_table_privilege(current_user,'analytics.orders','UPDATE')
       OR (pg_catalog.has_table_privilege(current_user,'analytics.reviews','SELECT') <>
           (current_user='sql_rag_analyst')) THEN
        RAISE EXCEPTION 'Unexpected API privileges';
    END IF;
END $$;
