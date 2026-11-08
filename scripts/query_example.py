"""Send an example without putting the bearer token into shell history."""

import argparse
from pathlib import Path

import httpx
from dotenv import dotenv_values

parser = argparse.ArgumentParser()
parser.add_argument("question", nargs="?", default="Show the top 5 products by revenue")
parser.add_argument("--role", choices=["sales", "analyst"], default="sales")
args = parser.parse_args()
config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
with httpx.Client(timeout=35, trust_env=False) as client:
    response = client.post(
        "http://127.0.0.1:8000/api/v1/sql-rag/query",
        headers={"Authorization": "Bearer " + config[args.role.upper() + "_TOKEN"]},
        json={"question": args.question},
    )
    print(response.status_code)
    import json

    print(json.dumps(response.json(), indent=2))
