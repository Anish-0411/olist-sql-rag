from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.config import Settings
from app.errors import ServiceError
from app.policy import Principal, authorized_contract
from app.security import ValidatedQuery


@dataclass
class RawResults:
    columns: list[str]
    rows: list[dict]
    truncated: bool


class Database:
    """Only this component can open query connections. Never receives raw candidate SQL."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engines = {
            role: create_engine(
                url.get_secret_value(),
                pool_size=2,
                max_overflow=0,
                pool_timeout=3,
                pool_pre_ping=True,
                echo=False,
                hide_parameters=True,
                connect_args={"connect_timeout": 3},
            )
            for role, url in [
                ("sales", settings.sales_database_url),
                ("analyst", settings.analyst_database_url),
            ]
        }

    @contextmanager
    def connection(self, principal: Principal):
        try:
            with self.engines[principal.role].connect() as conn, conn.begin():
                conn.exec_driver_sql("SET TRANSACTION READ ONLY")
                conn.exec_driver_sql("SET LOCAL search_path = pg_catalog")
                conn.exec_driver_sql("SET LOCAL standard_conforming_strings = on")
                conn.execute(
                    text("SELECT pg_catalog.set_config('statement_timeout', :v, true)"),
                    {"v": str(self.settings.statement_timeout_ms)},
                )
                conn.exec_driver_sql("SET LOCAL lock_timeout = '500ms'")
                conn.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '5s'")
                yield conn
        except ServiceError:
            raise
        except DBAPIError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            if code in {"57014", "55P03"}:
                raise ServiceError(
                    "QUERY_TIMEOUT", "The query exceeded its execution budget.", 504
                ) from None
            if code and code.startswith(("22", "42")):
                raise ServiceError(
                    "QUERY_EXECUTION_FAILED", "The validated query could not be executed.", 422
                ) from None
            raise ServiceError(
                "DATABASE_UNAVAILABLE", "The database is temporarily unavailable.", 503
            ) from None
        except SQLAlchemyError:
            raise ServiceError(
                "DATABASE_UNAVAILABLE", "The database is temporarily unavailable.", 503
            ) from None

    def verify(self):
        """Fail startup on privileged/misprovisioned credentials or contract drift."""
        for role in self.engines:
            principal = Principal("startup", role)
            expected_role = "sql_rag_" + role
            with self.connection(principal) as conn:
                if conn.dialect.server_version_info[0] != 16:
                    raise ServiceError("UNSAFE_DATABASE", "PostgreSQL 16 is required.", 503)
                flags = (
                    conn.execute(
                        text("""SELECT current_user AS username, rolsuper,
                    rolcreaterole, rolcreatedb, rolreplication, rolbypassrls
                    FROM pg_catalog.pg_roles WHERE rolname = current_user""")
                    )
                    .mappings()
                    .one()
                )
                memberships = conn.execute(
                    text("""SELECT COUNT(*) FROM pg_catalog.pg_auth_members
                    WHERE member = (SELECT oid FROM pg_catalog.pg_roles WHERE rolname = current_user)""")
                ).scalar_one()
                if (
                    flags["username"] != expected_role
                    or any(flags[k] for k in flags if k != "username")
                    or memberships
                ):
                    raise ServiceError(
                        "UNSAFE_DATABASE", "Dedicated restricted database roles are required.", 503
                    )
                dangerous = conn.execute(
                    text("""SELECT
                    pg_catalog.has_database_privilege(current_user, current_database(), 'CREATE') OR
                    pg_catalog.has_database_privilege(current_user, current_database(), 'TEMP') OR
                    EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n WHERE n.nspname !~ '^pg_'
                        AND n.nspname <> 'information_schema'
                        AND pg_catalog.has_schema_privilege(current_user, n.oid, 'CREATE')) OR
                    EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'
                        AND c.relkind IN ('r','p','v','m','f') AND (
                            pg_catalog.has_table_privilege(current_user, c.oid, 'INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                            OR (pg_catalog.has_table_privilege(current_user, c.oid, 'SELECT')
                                AND NOT (n.nspname = 'analytics' AND c.relname IN :allowed))
                        ))""").bindparams(bindparam("allowed", expanding=True)),
                    {"allowed": sorted(principal.views)},
                ).scalar_one()
                if dangerous:
                    raise ServiceError(
                        "UNSAFE_DATABASE", "Unexpected effective database privileges detected.", 503
                    )
            self.schema(principal)

    def schema(self, principal: Principal) -> dict:
        expected = authorized_contract(principal)
        query = text("""SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = :schema AND table_name IN :names
            ORDER BY table_name, ordinal_position""").bindparams(bindparam("names", expanding=True))
        with self.connection(principal) as conn:
            rows = conn.execute(
                query, {"schema": "analytics", "names": sorted(expected)}
            ).mappings()
            actual = {}
            for row in rows:
                actual.setdefault(row["table_name"], {})[row["column_name"]] = row["data_type"]
        if actual != expected:
            raise ServiceError(
                "SCHEMA_UNAVAILABLE", "The approved schema is unavailable or has changed.", 503
            )
        return actual

    def execute(self, principal: Principal, query: ValidatedQuery) -> RawResults:
        if not isinstance(query, ValidatedQuery):
            raise TypeError("Executor accepts only validated queries")
        if not set(query.source_views) <= {"analytics." + n for n in principal.views}:
            raise ServiceError("FORBIDDEN", "Query exceeds the caller policy.", 403)
        with self.connection(principal) as conn:
            # A named cursor plus fetchmany keeps client buffering bounded.
            with conn.execution_options(
                stream_results=True, max_row_buffer=query.row_limit + 1
            ).exec_driver_sql(query.sql, execution_options={"no_parameters": True}) as result:
                columns = list(result.keys())
                if len(columns) != len(set(columns)):
                    raise ServiceError(
                        "RESULT_INVALID", "Query returned duplicate output columns.", 502
                    )
                rows = result.mappings().fetchmany(query.row_limit + 1)
                return RawResults(
                    columns, [dict(r) for r in rows[: query.row_limit]], len(rows) > query.row_limit
                )

    def close(self):
        for engine in self.engines.values():
            engine.dispose()
