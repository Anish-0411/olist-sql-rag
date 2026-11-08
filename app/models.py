from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    question: str = Field(min_length=3, max_length=1000)
    max_rows: int = Field(default=100, ge=1, le=1000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3 or any(ord(c) < 32 and c not in "\n\t" for c in value):
            raise ValueError("Invalid question")
        return value


class Evidence(BaseModel):
    sql: str
    source_views: list[str]
    columns: list[str]
    rows: list[dict[str, str | int | float | bool | None]]
    row_count: int
    row_limit: int
    truncated: bool


class Metadata(BaseModel):
    strategy: Literal["placeholder", "api"]
    intent: str
    elapsed_ms: int
    warnings: list[str]


class QueryResponse(BaseModel):
    request_id: UUID
    answer: str
    evidence: Evidence
    metadata: Metadata


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    request_id: UUID
    error: ErrorDetail
