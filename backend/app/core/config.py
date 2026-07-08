from functools import lru_cache
from uuid import UUID

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str
    redis_url: str
    backend_cors_origins: str = "http://localhost:3000"
    dev_user_id: UUID
    anthropic_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.backend_cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
