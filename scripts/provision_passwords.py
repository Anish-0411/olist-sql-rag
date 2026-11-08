"""Run after 004_roles.sql; keep admin credentials out of the application configuration."""

import argparse
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from sqlalchemy.engine import make_url

parser = argparse.ArgumentParser()
parser.add_argument("--admin-url", default="postgresql:///olist?user=saianish")
args = parser.parse_args()
config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
try:
    with psycopg.connect(args.admin_url) as conn:
        for key, role in [
            ("SALES_DATABASE_URL", "sql_rag_sales"),
            ("ANALYST_DATABASE_URL", "sql_rag_analyst"),
        ]:
            url = make_url(config[key])
            if url.username != role or not url.password or len(url.password) < 24:
                raise ValueError("Invalid role credentials")
            conn.execute(
                sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(role), sql.Literal(url.password)
                )
            )
except Exception:
    print(
        "Role provisioning failed. Check .env and the administrator connection; no credentials were printed.",
        file=sys.stderr,
    )
    raise SystemExit(1) from None
print("Provisioned the two dedicated API login passwords.")
