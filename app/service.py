import hashlib
import time
from threading import BoundedSemaphore
from uuid import UUID

from app.config import Settings
from app.errors import ServiceError
from app.models import Evidence, Metadata, QueryRequest, QueryResponse
from app.policy import Principal
from app.results import build_answer, normalize_results
from app.security import validate_sql


class QueryService:
    def __init__(self, settings: Settings, database, generator):
        self.settings = settings
        self.database = database
        self.generator = generator
        self.slots = BoundedSemaphore(settings.max_concurrent_queries)

    def run(self, principal: Principal, request: QueryRequest, request_id: str, audit: dict):
        if not self.slots.acquire(blocking=False):
            raise ServiceError("BUSY", "Query capacity is busy; retry later.", 429)
        try:
            started = time.monotonic()
            limit = min(request.max_rows, self.settings.max_rows)
            schema = self.database.schema(principal)
            candidate = self.generator.generate(request.question, schema, limit)
            validated = validate_sql(candidate.sql, schema, limit)
            audit.update(
                strategy=candidate.strategy,
                sql_sha256=hashlib.sha256(validated.sql.encode()).hexdigest(),
            )
            raw = self.database.execute(principal, validated)
            rows = normalize_results(raw)
            audit["row_count"] = len(rows)
            warnings = []
            if raw.truncated:
                warnings.append(
                    "Results were truncated; do not interpret these rows as the full result."
                )
            if candidate.strategy == "api":
                warnings.append(
                    "SQL safety checks do not verify that the model interpreted your question correctly. Review the SQL evidence."
                )
            if candidate.intent in {"top_products_by_revenue", "monthly_revenue"}:
                warnings.append(
                    "Revenue is item price on delivered orders in BRL, excluding freight; months use purchase dates."
                )
            return QueryResponse(
                request_id=UUID(request_id),
                answer=build_answer(rows, raw.truncated),
                evidence=Evidence(
                    sql=validated.sql,
                    source_views=list(validated.source_views),
                    columns=raw.columns,
                    rows=rows,
                    row_count=len(rows),
                    row_limit=limit,
                    truncated=raw.truncated,
                ),
                metadata=Metadata(
                    strategy=candidate.strategy,
                    intent=candidate.intent,
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                    warnings=warnings,
                ),
            )
        finally:
            self.slots.release()
