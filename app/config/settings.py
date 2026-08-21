from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Literae API"
    app_version: str = "0.1.0"
    environment: str = "development"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    deepseek_api_key: SecretStr | None = None
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_timeout_seconds: float = Field(default=30, gt=0, le=120)
    openalex_base_url: str = "https://api.openalex.org"
    openalex_api_key: SecretStr | None = None
    openalex_email: str | None = None
    openalex_results_limit: int = Field(default=10, ge=1, le=25)
    openalex_timeout_seconds: float = Field(default=15, gt=0, le=60)
    lmnr_project_api_key: SecretStr | None = None
    lmnr_base_url: str | None = None
    laminar_force_http: bool = True
    laminar_disable_batch: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
