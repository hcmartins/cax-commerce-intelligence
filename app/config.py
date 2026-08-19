from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "local"
    app_name: str = "Commerce Intelligence"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    log_level: str = "INFO"
    log_json: bool = False

    database_url: str = "postgresql+psycopg://ai_commerce:ai_commerce@localhost:5432/ai_commerce"

    # "auto" prefers Anthropic, falling back to OpenAI, then the mock — whichever
    # key is actually set. "anthropic"/"openai" force that provider specifically
    # (still falling back to mock if its key is missing); "mock" always mocks.
    ai_provider: Literal["mock", "anthropic", "openai", "auto"] = "mock"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    search_provider: Literal["mock"] = "mock"
    supplier_provider: Literal["mock"] = "mock"
    marketplace_provider: Literal["mock"] = "mock"
    operations_provider: Literal["mock"] = "mock"

    default_marketplace_fee_pct: float = 15.0
    default_payment_fee_pct: float = 3.0
    default_currency: str = "USD"

    api_base_url: str = "http://localhost:8000/api/v1"

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
