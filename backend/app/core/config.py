from functools import lru_cache
import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Part Pilot", alias="PARTPILOT_APP_NAME")
    env: str = Field(default="development", alias="PARTPILOT_ENV")

    host_port: int = Field(default=7890, alias="PARTPILOT_HOST_PORT")
    container_port: int = Field(default=8000, alias="PARTPILOT_CONTAINER_PORT")

    database_url: str = Field(
        default="sqlite:///../data/partpilot.db",
        alias="PARTPILOT_DATABASE_URL",
    )

    # Keep this as a string so .env can use normal comma-separated values.
    # JSON list syntax is also accepted for compatibility.
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:8000",
        alias="PARTPILOT_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()

        if not raw:
            return []

        if raw == "*":
            return ["*"]

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                pass

        return [origin.strip() for origin in raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
