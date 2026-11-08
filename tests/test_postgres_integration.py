"""Real PostgreSQL tests. No SQLite substitution, automatic seeding, or production writes."""

import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.config import Settings
from app.database import Database
from app.errors import ServiceError
from app.generators import PlaceholderGenerator
from app.main import create_app
from app.policy import CONTRACT, Principal
from app.security import validate_sql

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_settings():
    sales = os.getenv("TEST_SALES_DATABASE_URL")
    analyst = os.getenv("TEST_ANALYST_DATABASE_URL")
    if not sales or not analyst:
        pytest.skip(
            "Set both TEST_*_DATABASE_URL values for a separately seeded PostgreSQL 16 olist_test database"
        )
    for url in [sales, analyst]:
        if make_url(url).database != "olist_test":
            pytest.fail("Integration tests require the separate database named olist_test")
    return Settings(
        _env_file=None,
        sales_database_url=sales,
        analyst_database_url=analyst,
        sales_token="test-sales-" + "s" * 32,
        analyst_token="test-analyst-" + "a" * 32,
        generator_mode="placeholder",
    )


@pytest.fixture(scope="module")
def pg(pg_settings):
    database = Database(pg_settings)
    try:
        database.verify()
        # Refuse to assert fixture results against a different dataset.
        with database.connection(Principal("test", "sales")) as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM analytics.orders")).scalar_one() == 3
        yield database
    finally:
        database.close()


def execute_question(pg, question, role="sales", limit=100):
    principal = Principal("test", role)
    schema = pg.schema(principal)
    candidate = PlaceholderGenerator().generate(question, schema, limit)
    return pg.execute(principal, validate_sql(candidate.sql, schema, limit))


def test_real_restricted_roles_version_and_schema(pg):
    pg.verify()
    assert "reviews" not in pg.schema(Principal("test", "sales"))
    assert pg.schema(Principal("test", "analyst")) == CONTRACT


def test_real_top_products_revenue_excludes_canceled_and_freight(pg):
    result = execute_question(pg, "Show the top 5 products by revenue")
    assert result.rows == [
        {"product_id": "p1", "revenue": Decimal("300.00")},
        {"product_id": "p2", "revenue": Decimal("50.00")},
        {"product_id": "p3", "revenue": Decimal("25.00")},
    ]
    assert not result.truncated


def test_real_monthly_revenue(pg):
    result = execute_question(pg, "monthly revenue")
    assert [(r["month"].month, r["revenue"]) for r in result.rows] == [
        (1, Decimal("150.00")),
        (2, Decimal("225.00")),
    ]


def test_real_total_orders(pg):
    assert execute_question(pg, "total orders").rows == [{"order_count": 3}]


def test_real_orders_by_status(pg):
    assert execute_question(pg, "orders by status").rows == [
        {"order_status": "delivered", "order_count": 2},
        {"order_status": "canceled", "order_count": 1},
    ]


def test_real_reviews_multiple_records(pg):
    assert execute_question(pg, "average review score", "analyst").rows == [
        {"average_review_score": Decimal("4.00")}
    ]


def test_real_truncation(pg):
    result = execute_question(pg, "top 5 products by revenue", limit=1)
    assert len(result.rows) == 1 and result.truncated


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM public.customers",
        "SELECT * FROM public.order_reviews",
        "SELECT * FROM analytics.reviews",
        "UPDATE analytics.orders SET order_status='bad' WHERE false",
        "CREATE TEMPORARY TABLE cannot_create(id int)",
        "CREATE TABLE analytics.cannot_create(id int)",
    ],
)
def test_real_database_denies_even_if_validator_were_bypassed(pg, sql):
    # Direct trusted test SQL proves database grants independently of AST checks.
    with pytest.raises(ServiceError):
        with pg.connection(Principal("test", "sales")) as conn:
            conn.exec_driver_sql(sql)


def test_real_statement_timeout(pg):
    with pytest.raises(ServiceError) as result:
        with pg.connection(Principal("test", "sales")) as conn:
            conn.exec_driver_sql("SET LOCAL statement_timeout='100ms'")
            conn.exec_driver_sql("SELECT pg_catalog.pg_sleep(1)")
    assert result.value.code == "QUERY_TIMEOUT"


def test_real_http_end_to_end(pg, pg_settings):
    with TestClient(create_app(pg_settings)) as client:
        response = client.post(
            "/api/v1/sql-rag/query",
            headers={"Authorization": "Bearer " + pg_settings.sales_token.get_secret_value()},
            json={"question": "Show the top 5 products by revenue"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["evidence"]["rows"][0] == {"product_id": "p1", "revenue": "300.00"}
        assert data["evidence"]["row_count"] == 3
