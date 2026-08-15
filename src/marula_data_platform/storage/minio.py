"""MinIO adapter for raw pipeline data."""

from collections.abc import Mapping
from io import BytesIO

from minio import Minio


class BucketNotFoundError(RuntimeError):
    """Raised when the configured raw bucket does not exist."""


class MinioStorage:
    """Write immutable raw objects to a configured MinIO bucket."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool,
        client: Minio | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )

    @property
    def bucket(self) -> str:
        """Return the configured bucket name."""
        return self._bucket

    def put_json(
        self,
        object_name: str,
        content: bytes,
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        """Store JSON bytes without changing their representation."""
        if not self._client.bucket_exists(self._bucket):
            raise BucketNotFoundError(f"MinIO bucket does not exist: {self._bucket}")

        self._client.put_object(
            bucket_name=self._bucket,
            object_name=object_name,
            data=BytesIO(content),
            length=len(content),
            content_type="application/json",
            metadata=dict(metadata or {}),
        )
