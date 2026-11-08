import json
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.errors import ServiceError
from app.generators import Candidate
from app.main import create_app
from conftest import FakeDatabase

URL = "/api/v1/sql-rag/query"


def test_http_end_to_end_with_explicit_database_double(client, auth):
    response = client.post(
        URL, headers=auth, json={"question": "Show the top 5 products by revenue"}
    )
    assert response.status_code == 200
    body = response.json()
    assert UUID(body["request_id"])
    assert response.headers["x-request-id"] == body["request_id"]
    assert body["evidence"]["rows"][0] == {"product_id": "p1", "revenue": "300.00"}
    assert body["metadata"]["strategy"] == "placeholder"
    assert body["evidence"]["source_views"] == ["analytics.order_items", "analytics.orders"]
    assert "300.00" in body["answer"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer wrong"}, {"Authorization": "Basic xxx"}]
)
def test_authentication_precedes_body_validation(client, headers):
    response = client.post(URL, headers=headers, content="invalid json")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert client.app.state.service.database.calls == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": "x"},
        {"question": "   "},
        {"question": 7},
        {"question": "total orders", "sql": "SELECT 1"},
        {"question": "total orders", "role": "analyst"},
        {"question": "total orders", "max_rows": 0},
        {"question": "total orders", "max_rows": "5"},
        {"question": "total orders", "max_rows": True},
        {"question": "total orders", "max_rows": 1001},
        {"question": "x" * 1001},
        {"question": "total\x00orders"},
    ],
)
def test_invalid_request_is_safe(client, auth, body):
    response = client.post(URL, headers=auth, json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"
    assert "input" not in response.text
    assert client.app.state.service.database.calls == []


def test_body_size_limit(client, auth):
    response = client.post(URL, headers=auth, content=b"x" * 16385)
    assert response.status_code == 413


def test_chunked_body_size_limit(client, auth):
    response = client.post(URL, headers=auth, content=iter([b"x" * 9000, b"y" * 9000]))
    assert response.status_code == 413


def test_role_schema_and_review_permissions(client, auth, settings):
    schema = client.get("/api/v1/sql-rag/schema", headers=auth).json()
    assert "reviews" not in schema["tables"]
    assert "customer_id" not in schema["tables"]["orders"]
    assert (
        client.post(URL, headers=auth, json={"question": "average review score"}).status_code == 403
    )
    analyst = {"Authorization": "Bearer " + settings.analyst_token.get_secret_value()}
    schema = client.get("/api/v1/sql-rag/schema", headers=analyst).json()
    assert "reviews" in schema["tables"]
    assert "review_comment_message" not in schema["tables"]["reviews"]


def test_truncation(client, auth):
    response = client.post(
        URL, headers=auth, json={"question": "top 5 products by revenue", "max_rows": 1}
    )
    data = response.json()
    assert data["evidence"]["truncated"] is True
    assert data["evidence"]["row_count"] == 1
    assert data["evidence"]["sql"].endswith("LIMIT 2")


def test_unsupported_question(client, auth):
    response = client.post(
        URL, headers=auth, json={"question": "top 5 products by revenue in 2018"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_QUESTION"


class MaliciousGenerator:
    def generate(self, question, schema, row_limit):
        return Candidate("SELECT pg_sleep(10) AS x FROM analytics.orders o", "api", "test")


def test_malicious_generation_never_reaches_execution(settings, auth):
    with TestClient(create_app(settings, FakeDatabase, MaliciousGenerator())) as client:
        response = client.post(URL, headers=auth, json={"question": "anything"})
        assert response.status_code == 422
        assert not any(c[0] == "execute" for c in client.app.state.service.database.calls)


def test_safe_database_timeout(client, auth):
    def fail(*args):
        raise ServiceError("QUERY_TIMEOUT", "The query exceeded its execution budget.", 504)

    client.app.state.service.database.execute = fail
    response = client.post(URL, headers=auth, json={"question": "top 5 products by revenue"})
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "QUERY_TIMEOUT"


def test_unexpected_error_does_not_leak(client, auth):
    def fail(*args):
        raise RuntimeError("secret-password /private/database/path")

    client.app.state.service.database.execute = fail
    response = client.post(URL, headers=auth, json={"question": "top 5 products by revenue"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_safe_audit_fields(client, auth, monkeypatch):
    events = []
    monkeypatch.setattr(
        "app.middleware.audit_logger.info", lambda value: events.append(json.loads(value))
    )
    question = "Show the top 5 products by revenue"
    client.post(URL, headers=auth, json={"question": question})
    assert events[-1]["status"] == 200
    assert events[-1]["row_count"] == 3
    assert len(events[-1]["sql_sha256"]) == 64
    serialized = json.dumps(events)
    assert question not in serialized and "Bearer" not in serialized
    assert "300.00" not in serialized and "SELECT" not in serialized


def test_capacity_released_after_failure(client, auth):
    service = client.app.state.service
    for _ in range(service.settings.max_concurrent_queries):
        assert service.slots.acquire(blocking=False)
    assert client.post(URL, headers=auth, json={"question": "total orders"}).status_code == 429
    for _ in range(service.settings.max_concurrent_queries):
        service.slots.release()
    assert client.post(URL, headers=auth, json={"question": "total orders"}).status_code == 200
    for _ in range(6):
        assert (
            client.post(URL, headers=auth, json={"question": "unsupported query"}).status_code
            == 422
        )
    assert client.post(URL, headers=auth, json={"question": "total orders"}).status_code == 200


def test_openapi_documents_bearer_auth(client):
    schema = client.get("/openapi.json").json()
    assert schema["paths"][URL]["post"]["security"] == [{"BearerAuth": []}]
    assert client.get("/health/live").status_code == 200


def test_startup_fails_closed_and_disposes_resources(settings):
    created = []

    class UnsafeDatabase(FakeDatabase):
        def __init__(self, settings):
            super().__init__(settings)
            created.append(self)

        def verify(self):
            raise ServiceError("UNSAFE_DATABASE", "secret administrator details", 503)

    with pytest.raises(RuntimeError, match="Startup checks failed") as result:
        with TestClient(create_app(settings, UnsafeDatabase)):
            pass
    assert created[0].closed is True
    assert "secret" not in str(result.value)
