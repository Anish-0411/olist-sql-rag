from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.config import Settings
from app.database import Database
from app.errors import ServiceError
from app.generators import APIGenerator, PlaceholderGenerator
from app.middleware import RequestBoundary
from app.models import ErrorResponse, QueryRequest, QueryResponse
from app.policy import schema_document
from app.service import QueryService


def create_app(settings: Settings | None = None, database_factory=Database, generator=None):
    @asynccontextmanager
    async def lifespan(app):
        database = None
        try:
            configured = settings or Settings()
            app.state.settings = configured
            database = database_factory(configured)
            database.verify()
            chosen = generator or (
                PlaceholderGenerator()
                if configured.generator_mode == "placeholder"
                else APIGenerator(configured)
            )
            app.state.service = QueryService(configured, database, chosen)
        except Exception:
            if database:
                database.close()
            raise RuntimeError(
                "Startup checks failed. Verify .env, PostgreSQL 16, approved views, and restricted role permissions; see README.md."
            ) from None
        try:
            yield
        finally:
            database.close()

    app = FastAPI(
        title="Olist Text-to-SQL",
        version="0.1.0",
        lifespan=lifespan,
        description="Restricted Olist analytics. Use Authorize with your development bearer token.",
    )
    app.add_middleware(RequestBoundary, owner=app)

    def error(request, code, message, status):
        request.state.audit["error_code"] = code
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else None
        return JSONResponse(
            {"request_id": request.state.request_id, "error": {"code": code, "message": message}},
            status_code=status,
            headers=headers,
        )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return error(request, exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(
            request,
            "INVALID_REQUEST",
            "Provide a question of 3–1000 characters and an optional integer max_rows from 1 to 1000; no extra fields.",
            422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error(
            request,
            "HTTP_ERROR",
            "The requested endpoint or operation is unavailable.",
            exc.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return error(request, "INTERNAL_ERROR", "The request could not be completed.", 500)

    @app.get("/health/live", tags=["health"])
    def live():
        return {"status": "ok"}

    errors = {
        code: {"model": ErrorResponse} for code in [401, 403, 413, 422, 429, 500, 502, 503, 504]
    }

    @app.get("/api/v1/sql-rag/schema", tags=["analytics"], responses=errors)
    def schema(request: Request):
        return {
            "request_id": request.state.request_id,
            **schema_document(app.state.service.database.schema(request.state.principal)),
        }

    @app.post(
        "/api/v1/sql-rag/query", response_model=QueryResponse, tags=["analytics"], responses=errors
    )
    def query(body: QueryRequest, request: Request):
        return app.state.service.run(
            request.state.principal, body, request.state.request_id, request.state.audit
        )

    # Security is enforced by RequestBoundary before request parsing. Advertise it in OpenAPI too.
    from fastapi.openapi.utils import get_openapi

    def openapi():
        if app.openapi_schema:
            return app.openapi_schema
        result = get_openapi(
            title=app.title, version=app.version, description=app.description, routes=app.routes
        )
        result.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
        }
        for path, methods in result["paths"].items():
            if path.startswith("/api/"):
                for method in methods.values():
                    method["security"] = [{"BearerAuth": []}]
        app.openapi_schema = result
        return result

    app.openapi = openapi
    return app


app = create_app()
