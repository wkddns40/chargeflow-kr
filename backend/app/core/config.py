from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql://chargeflow:chargeflow@localhost:5432/chargeflow"
    cors_origins_raw: str = "http://localhost:3000"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_parse_timeout_seconds: float = 8.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
