from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="PartPilot", alias="PARTPILOT_APP_NAME")
    env: str = Field(default="development", alias="PARTPILOT_ENV")
    database_url: str = Field(
        default="sqlite:///../data/partpilot.db",
        alias="PARTPILOT_DATABASE_URL",
    )
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:8000"],
        alias="PARTPILOT_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
