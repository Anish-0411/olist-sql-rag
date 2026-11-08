from datetime import datetime
from decimal import Decimal

import pytest

from app.database import RawResults
from app.errors import ServiceError
from app.results import build_answer, normalize_results, normalize_value


def test_normalization_preserves_precision_nulls_and_dates():
    assert normalize_value(Decimal("12345678901234.10")) == "12345678901234.10"
    assert normalize_value(None) is None
    assert normalize_value(datetime(2018, 1, 1)) == "2018-01-01T00:00:00"
    assert normalize_value(3) == 3
    assert normalize_value(True) is True


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), Decimal("NaN"), b"bytes", object(), "x" * 2001]
)
def test_invalid_or_oversized_values_fail(value):
    with pytest.raises(ServiceError):
        normalize_value(value)


def test_column_mismatch_and_total_budget():
    with pytest.raises(ServiceError):
        normalize_results(RawResults(["x"], [{"y": 1}], False))
    with pytest.raises(ServiceError):
        normalize_results(RawResults(["x"], [{"x": "a" * 2000}] * 1000, False))


def test_grounded_answer_handles_empty_null_and_truncation():
    assert build_answer([], False) == "No rows matched the query."
    answer = build_answer([{"score": None}], True)
    assert "score = null" in answer and "limited" in answer
