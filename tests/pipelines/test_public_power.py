from datetime import UTC, date, datetime

from marula_data_platform.clients.energy_charts import ExtractedResponse
from marula_data_platform.pipelines.public_power import run_public_power_ingestion


class FakeSource:
    def __init__(self, response: ExtractedResponse) -> None:
        self.response = response

    def get_public_power(self, country: str, requested_date: date) -> ExtractedResponse:
        assert country == "de"
        assert requested_date == date(2026, 8, 1)
        return self.response


class FakeStorage:
    bucket = "marula-raw"

    def __init__(self) -> None:
        self.stored_object: tuple[str, bytes, dict[str, str] | None] | None = None

    def put_json(
        self,
        object_name: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.stored_object = (object_name, content, metadata)


def test_ingestion_stores_immutable_raw_response() -> None:
    extracted_at = datetime(2026, 8, 15, 12, 30, tzinfo=UTC)
    source = FakeSource(
        ExtractedResponse(
            content=b'{"series": [], "data": []}',
            request_url=(
                "https://api.energy-charts.info/v2/public_power"
                "?country=de&start=2026-08-01&end=2026-08-01"
            ),
            extracted_at=extracted_at,
        )
    )
    storage = FakeStorage()

    result = run_public_power_ingestion(
        source=source,
        storage=storage,
        country="de",
        requested_date=date(2026, 8, 1),
    )

    expected_name = (
        "energy-charts/public-power/country=de/date=2026-08-01/"
        "extracted_at=20260815T123000.000000Z.json"
    )
    assert result.object_name == expected_name
    assert storage.stored_object is not None
    object_name, content, metadata = storage.stored_object
    assert object_name == expected_name
    assert content == source.response.content
    assert metadata is not None
    assert metadata["source-license"] == "CC-BY-4.0"
