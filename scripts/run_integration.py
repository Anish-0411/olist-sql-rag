"""Run live integration tests using .env role credentials and the separate olist_test DB."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import make_url

root = Path(__file__).resolve().parents[1]
config = dotenv_values(root / ".env")
env = dict(os.environ)
for role in ["SALES", "ANALYST"]:
    url = make_url(config[role + "_DATABASE_URL"])
    env["TEST_" + role + "_DATABASE_URL"] = url.set(database="olist_test").render_as_string(
        hide_password=False
    )
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            "integration",
            "-v",
            "--junitxml=reports/postgres-tests.xml",
        ],
        cwd=root,
        env=env,
    )
)
