import pytest
from pydantic import ValidationError

from marula_data_platform.config import Settings


def test_settings_reject_minio_endpoint_with_scheme() -> None:
    with pytest.raises(ValidationError, match="must not include"):
        Settings(
            _env_file=None,
            minio_endpoint="http://localhost:9000",
            minio_access_key="access",
            minio_secret_key="secret",
            minio_bucket="marula-raw",
            minio_secure=False,
        )


def test_settings_hide_secrets_in_representation() -> None:
    settings = Settings(
        _env_file=None,
        minio_endpoint="localhost:9000",
        minio_access_key="access-value",
        minio_secret_key="secret-value",
        minio_bucket="marula-raw",
        minio_secure=False,
    )

    assert "access-value" not in repr(settings)
    assert "secret-value" not in repr(settings)
