import hashlib
import hmac
import json
import logging
import time
from uuid import uuid4

from starlette.responses import JSONResponse

from app.policy import Principal

audit_logger = logging.getLogger("sql_rag.audit")
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    audit_logger.addHandler(handler)
audit_logger.propagate = False


class RequestBoundary:
    """Authenticate before JSON/Pydantic validation; bound bodies including chunked input."""

    def __init__(self, app, owner):
        self.app = app
        self.owner = owner

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        started = time.monotonic()
        request_id = str(uuid4())  # Never accept an untrusted caller ID as an audit identifier.
        state = scope.setdefault("state", {})
        response_started = False
        state["request_id"] = request_id
        audit = state["audit"] = {
            "event": "http_request",
            "request_id": request_id,
            "status": 500,
            "actor": "anonymous",
        }

        async def wrapped_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                audit["status"] = message["status"]
                message["headers"] = list(message.get("headers", [])) + [
                    (b"x-request-id", request_id.encode()),
                    (b"cache-control", b"no-store"),
                    (b"x-content-type-options", b"nosniff"),
                ]
            await send(message)

        async def fail(status, code, message):
            audit["error_code"] = code
            headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
            await JSONResponse(
                {"request_id": request_id, "error": {"code": code, "message": message}},
                status_code=status,
                headers=headers,
            )(scope, receive, wrapped_send)

        try:
            if scope["path"].startswith("/api/"):
                settings = self.owner.state.settings
                auth_headers = [v for k, v in scope["headers"] if k.lower() == b"authorization"]
                principal = None
                if len(auth_headers) == 1:
                    parts = auth_headers[0].decode("latin-1").split()
                    if len(parts) == 2 and parts[0].lower() == "bearer" and len(parts[1]) <= 512:
                        supplied = hashlib.sha256(parts[1].encode()).digest()
                        for role, secret in [
                            ("sales", settings.sales_token),
                            ("analyst", settings.analyst_token),
                        ]:
                            expected = hashlib.sha256(secret.get_secret_value().encode()).digest()
                            if hmac.compare_digest(supplied, expected):
                                principal = Principal("development-" + role, role)
                if principal is None:
                    return await fail(401, "UNAUTHORIZED", "A valid bearer token is required.")
                state["principal"] = principal
                audit.update(actor=principal.subject, policy=principal.role)
                # Accumulate at most 16 KiB; no trust in Content-Length.
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    body.extend(message.get("body", b""))
                    if len(body) > 16384:
                        return await fail(413, "REQUEST_TOO_LARGE", "Request body exceeds 16 KiB.")
                    if not message.get("more_body", False):
                        break
                delivered = False

                async def replay():
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                return await self.app(scope, replay, wrapped_send)
            return await self.app(scope, receive, wrapped_send)
        except Exception:
            # Boundary errors get the same sanitized envelope, headers and audit treatment.
            if not response_started:
                return await fail(500, "INTERNAL_ERROR", "The request could not be completed.")
            raise
        finally:
            audit["elapsed_ms"] = int((time.monotonic() - started) * 1000)
            audit_logger.info(json.dumps(audit, separators=(",", ":"), sort_keys=True))
