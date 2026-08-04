from functools import lru_cache
import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Part Pilot", alias="PARTPILOT_APP_NAME")
    env: str = Field(default="development", alias="PARTPILOT_ENV")

    host_port: int = Field(default=7890, alias="PARTPILOT_HOST_PORT")
    container_port: int = Field(default=8000, alias="PARTPILOT_CONTAINER_PORT")

    # PARTPILOT:MCP_TRUSTED_PROXY_CONFIG:V506
    bind_address: str = Field(
        default="0.0.0.0",
        alias="PARTPILOT_BIND_ADDRESS",
    )
    trusted_proxy_cidrs: str = Field(
        default="",
        alias="PARTPILOT_TRUSTED_PROXY_CIDRS",
    )

    # PARTPILOT:MCP_PUBLIC_BASE_URL:V467
    public_base_url: str | None = Field(
        default=None,
        alias="PARTPILOT_PUBLIC_BASE_URL",
    )

    # PARTPILOT:MCP_INSTANCE_SECRET:V482
    instance_secret: str | None = Field(
        default=None,
        alias="PARTPILOT_INSTANCE_SECRET",
    )

    instance_secret_file: str = Field(
        default="/data/.partpilot-instance-secret",
        alias="PARTPILOT_INSTANCE_SECRET_FILE",
    )

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
    def normalized_bind_address(self) -> str:
        from app.core.client_ip import normalize_bind_address

        return normalize_bind_address(self.bind_address)

    @property
    def trusted_proxy_cidr_list(self) -> tuple[str, ...]:
        from app.core.client_ip import normalize_trusted_proxy_cidrs

        return normalize_trusted_proxy_cidrs(self.trusted_proxy_cidrs)

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
