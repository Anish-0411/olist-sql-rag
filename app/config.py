from typing import Literal
from urllib.parse import urlparse

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    sales_database_url: SecretStr
    analyst_database_url: SecretStr
    sales_token: SecretStr
    analyst_token: SecretStr
    generator_mode: Literal["placeholder", "api"] = "placeholder"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_api_key: SecretStr = SecretStr("")
    llm_allow_local_http: bool = False
    statement_timeout_ms: int = Field(default=3000, ge=100, le=10000)
    max_rows: int = Field(default=100, ge=1, le=1000)
    max_concurrent_queries: int = Field(default=4, ge=1, le=16)

    @model_validator(mode="after")
    def safe_configuration(self):
        tokens = [self.sales_token.get_secret_value(), self.analyst_token.get_secret_value()]
        if min(map(len, tokens)) < 32 or tokens[0] == tokens[1]:
            raise ValueError(
                "Configure two distinct random bearer tokens of at least 32 characters"
            )
        for secret, role in [
            (self.sales_database_url, "sql_rag_sales"),
            (self.analyst_database_url, "sql_rag_analyst"),
        ]:
            url = make_url(secret.get_secret_value())
            if url.drivername != "postgresql+psycopg" or url.username != role:
                raise ValueError("Use the dedicated postgresql+psycopg login for each policy")
        if self.generator_mode == "api":
            url = urlparse(self.llm_base_url)
            local_http = (
                self.llm_allow_local_http
                and url.scheme == "http"
                and url.hostname in {"localhost", "127.0.0.1", "::1"}
            )
            if not (url.scheme == "https" or local_http) or not url.hostname:
                raise ValueError("LLM endpoint requires HTTPS or explicitly enabled loopback HTTP")
            if url.username or url.password or url.query or url.fragment:
                raise ValueError("LLM endpoint must not contain credentials, query, or fragment")
            if not self.llm_model or not self.llm_api_key.get_secret_value():
                raise ValueError("API generation requires LLM_MODEL and LLM_API_KEY")
        return self
