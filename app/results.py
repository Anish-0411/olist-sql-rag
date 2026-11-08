import json
import math
from datetime import date, datetime
from decimal import Decimal

from app.database import RawResults
from app.errors import ServiceError


def normalize_value(value):
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, str):
        if len(value) > 2000:
            raise ServiceError(
                "RESULT_TOO_LARGE", "A returned value exceeds the response budget.", 422
            )
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ServiceError("RESULT_INVALID", "Query returned a non-finite number.", 502)
        return format(value, "f")  # Preserve currency precision; never silently convert to float.
    if isinstance(value, float) and math.isfinite(value):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise ServiceError("RESULT_INVALID", "Query returned an unsupported data type.", 502)


def normalize_results(raw: RawResults) -> list[dict]:
    normalized = []
    for row in raw.rows:
        if set(row) != set(raw.columns):
            raise ServiceError("RESULT_INVALID", "Query result columns did not match.", 502)
        normalized.append({key: normalize_value(row[key]) for key in raw.columns})
    if len(json.dumps(normalized, ensure_ascii=False).encode("utf-8")) > 1_000_000:
        raise ServiceError("RESULT_TOO_LARGE", "Results exceed the response budget.", 422)
    return normalized


def build_answer(rows: list[dict], truncated: bool) -> str:
    if not rows:
        return "No rows matched the query."
    prefix = f"Returned {len(rows)} row{'s' if len(rows) != 1 else ''}."
    if truncated:
        prefix += " More rows matched; this response is limited."
    first = "; ".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in rows[0].items())
    return prefix + " First row: " + first + "."
