from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GrowthOps API"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://growthops:growthops@localhost:5432/growthops"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
