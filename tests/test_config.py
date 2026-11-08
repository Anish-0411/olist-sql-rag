import pytest
from pydantic import ValidationError

from app.config import Settings


def values(settings):
    return settings.model_dump()


@pytest.mark.parametrize(
    "update",
    [
        {"sales_token": "short"},
        {"analyst_token": "s" * 40},
        {"sales_database_url": "postgresql+psycopg://saianish@localhost/olist"},
        {"sales_database_url": "sqlite:///olist.db"},
        {"statement_timeout_ms": 0},
        {"max_rows": 5000},
        {"generator_mode": "anything"},
        {"generator_mode": "api", "llm_base_url": "http://external.test/v1"},
        {"generator_mode": "api", "llm_base_url": "https://user:pass@example.com/v1"},
        {"generator_mode": "api", "llm_base_url": "https://example.com/v1?key=secret"},
    ],
)
def test_fail_unsafe_configuration(settings, update):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(values(settings) | update))


def test_loopback_api_mode_for_future_offline_model(settings):
    configured = Settings(
        _env_file=None,
        **(
            values(settings)
            | {
                "generator_mode": "api",
                "llm_base_url": "http://127.0.0.1:11434/v1",
                "llm_allow_local_http": True,
                "llm_model": "local-model",
                "llm_api_key": "local-only",
            }
        ),
    )
    assert configured.generator_mode == "api"
