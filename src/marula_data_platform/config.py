"""Validated application configuration."""

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load configuration from environment variables or the local env file."""

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    energy_charts_base_url: str = "https://api.energy-charts.info"
    energy_charts_timeout_seconds: float = Field(default=30.0, gt=0)

    minio_endpoint: str
    minio_access_key: SecretStr
    minio_secret_key: SecretStr
    minio_bucket: str = Field(min_length=3)
    minio_secure: bool

    @field_validator("minio_endpoint")
    @classmethod
    def endpoint_must_not_include_scheme(cls, value: str) -> str:
        """Keep protocol selection in MINIO_SECURE, as required by the SDK."""
        if "://" in value:
            raise ValueError("must not include http:// or https://; use MINIO_SECURE instead")
        return value
