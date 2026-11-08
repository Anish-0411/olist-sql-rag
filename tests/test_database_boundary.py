from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import DBAPIError, TimeoutError

from app.database import Database
from app.errors import ServiceError
from app.policy import Principal
from app.security import ValidatedQuery


@pytest.fixture
def database(settings):
    instance = Database(settings)
    yield instance
    instance.close()


@pytest.mark.parametrize(
    ("sqlstate", "expected", "status"),
    [
        ("57014", "QUERY_TIMEOUT", 504),
        ("55P03", "QUERY_TIMEOUT", 504),
        ("42601", "QUERY_EXECUTION_FAILED", 422),
        ("22012", "QUERY_EXECUTION_FAILED", 422),
        ("08006", "DATABASE_UNAVAILABLE", 503),
        (None, "DATABASE_UNAVAILABLE", 503),
    ],
)
def test_database_errors_never_expose_driver_messages(database, sqlstate, expected, status):
    original = Exception("SECRET database details")
    original.sqlstate = sqlstate
    error = DBAPIError("SECRET SQL", {}, original, False)
    engine = MagicMock()
    engine.connect.side_effect = error
    database.engines["sales"].dispose()
    database.engines["sales"] = engine
    with pytest.raises(ServiceError) as result:
        with database.connection(Principal("s", "sales")):
            pass
    assert result.value.code == expected and result.value.status == status
    assert "SECRET" not in result.value.message


def test_pool_timeout_is_sanitized(database):
    engine = MagicMock()
    engine.connect.side_effect = TimeoutError("SECRET connection string")
    database.engines["sales"].dispose()
    database.engines["sales"] = engine
    with pytest.raises(ServiceError) as result:
        with database.connection(Principal("s", "sales")):
            pass
    assert result.value.code == "DATABASE_UNAVAILABLE"


def test_executor_refuses_raw_sql_and_cross_role_query(database):
    with pytest.raises(TypeError):
        database.execute(Principal("s", "sales"), "SELECT 1")
    with pytest.raises(ServiceError) as result:
        database.execute(
            Principal("s", "sales"), ValidatedQuery("SELECT 1", ("analytics.reviews",), 10)
        )
    assert result.value.status == 403
