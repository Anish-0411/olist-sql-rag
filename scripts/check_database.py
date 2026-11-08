"""Run the same role, PostgreSQL version, privilege, and metadata checks as app startup."""

from app.config import Settings
from app.database import Database
from app.errors import ServiceError

database = None
try:
    database = Database(Settings())
    database.verify()
except ServiceError as exc:
    raise SystemExit(f"Database checks failed [{exc.code}]: {exc.message}") from None
except Exception:
    raise SystemExit(
        "Database checks failed. Confirm PostgreSQL 16, .env credentials, views and permissions."
    ) from None
finally:
    if database:
        database.close()
print("Database checks passed for both restricted policies.")
