from typing import Any

import pytest

from marula_data_platform.storage.minio import BucketNotFoundError, MinioStorage


class FakeMinioClient:
    def __init__(self, bucket_exists: bool = True) -> None:
        self._bucket_exists = bucket_exists
        self.put_call: dict[str, Any] | None = None

    def bucket_exists(self, _: str) -> bool:
        return self._bucket_exists

    def put_object(self, **kwargs: Any) -> None:
        self.put_call = kwargs


def test_put_json_preserves_content_and_metadata() -> None:
    client = FakeMinioClient()
    storage = MinioStorage(
        endpoint="unused:9000",
        access_key="unused",
        secret_key="unused",
        bucket="marula-raw",
        secure=False,
        client=client,  # type: ignore[arg-type]
    )

    storage.put_json("object.json", b'{"raw": true}', {"source": "example"})

    assert client.put_call is not None
    assert client.put_call["bucket_name"] == "marula-raw"
    assert client.put_call["object_name"] == "object.json"
    assert client.put_call["data"].read() == b'{"raw": true}'
    assert client.put_call["metadata"] == {"source": "example"}


def test_put_json_requires_existing_bucket() -> None:
    storage = MinioStorage(
        endpoint="unused:9000",
        access_key="unused",
        secret_key="unused",
        bucket="missing",
        secure=False,
        client=FakeMinioClient(bucket_exists=False),  # type: ignore[arg-type]
    )

    with pytest.raises(BucketNotFoundError, match="missing"):
        storage.put_json("object.json", b"{}")
