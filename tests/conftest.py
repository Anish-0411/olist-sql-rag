from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import RawResults
from app.main import create_app
from app.policy import authorized_contract


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        sales_database_url="postgresql+psycopg://sql_rag_sales:fixture-password@127.0.0.1/olist_test",
        analyst_database_url="postgresql+psycopg://sql_rag_analyst:fixture-password@127.0.0.1/olist_test",
        sales_token="s" * 40,
        analyst_token="a" * 40,
    )


class FakeDatabase:
    """HTTP/service double; never claim these tests validate PostgreSQL behavior."""

    def __init__(self, settings):
        self.calls = []
        self.closed = False

    def verify(self):
        return None

    def schema(self, principal):
        self.calls.append(("schema", principal.role))
        return authorized_contract(principal)

    def execute(self, principal, query):
        self.calls.append(("execute", principal.role, query))
        rows = [
            {"product_id": "p1", "revenue": Decimal("300.00")},
            {"product_id": "p2", "revenue": Decimal("50.00")},
            {"product_id": "p3", "revenue": Decimal("25.00")},
        ]
        return RawResults(
            ["product_id", "revenue"], rows[: query.row_limit], query.row_limit < len(rows)
        )

    def close(self):
        self.closed = True


@pytest.fixture
def client(settings):
    with TestClient(
        create_app(settings, database_factory=FakeDatabase), raise_server_exceptions=False
    ) as client:
        yield client


@pytest.fixture
def auth(settings):
    return {"Authorization": "Bearer " + settings.sales_token.get_secret_value()}
