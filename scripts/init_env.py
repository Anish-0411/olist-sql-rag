"""Generate local secrets without overwriting an existing .env or printing secrets."""

import os
import secrets
from pathlib import Path

target = Path(__file__).resolve().parents[1] / ".env"
content = "\n".join(
    [
        f"SALES_DATABASE_URL=postgresql+psycopg://sql_rag_sales:{secrets.token_hex(24)}@127.0.0.1:5432/olist",
        f"ANALYST_DATABASE_URL=postgresql+psycopg://sql_rag_analyst:{secrets.token_hex(24)}@127.0.0.1:5432/olist",
        "SALES_TOKEN=" + secrets.token_urlsafe(36),
        "ANALYST_TOKEN=" + secrets.token_urlsafe(36),
        "GENERATOR_MODE=placeholder",
        "LLM_BASE_URL=https://api.openai.com/v1",
        "LLM_MODEL=",
        "LLM_API_KEY=",
        "LLM_ALLOW_LOCAL_HTTP=false",
        "STATEMENT_TIMEOUT_MS=3000",
        "MAX_ROWS=100",
        "MAX_CONCURRENT_QUERIES=4",
        "",
    ]
)
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    raise SystemExit(".env already exists; leaving it unchanged.") from None
with os.fdopen(fd, "w") as handle:
    handle.write(content)
print("Created .env with random local credentials. Keep it private.")
