import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from marula_data_platform.clients.energy_charts import ExtractedResponse
from marula_data_platform.pipelines.public_power import (
    PublicPowerTransformationError,
    RawSnapshot,
    run_public_power_ingestion,
    transform_public_power,
)

PublicPowerPayload = dict[str, Any]
PublicPowerPayloadFactory = Callable[[date], PublicPowerPayload]
TRANSFORMATION_PENDING = pytest.mark.xfail(
    strict=True,
    raises=NotImplementedError,
    reason="the Polars transformation is implemented in step 8",
)


def build_snapshot(
    payload: PublicPowerPayload,
    object_name: str | None = None,
) -> RawSnapshot:
    extracted_at = datetime.fromisoformat(payload["generated_at"]).astimezone(UTC) + timedelta(
        minutes=5
    )
    requested_date = datetime.fromisoformat(payload["available_from"]).date()
    object_name = object_name or (
        "energy-charts/public-power/country=de/"
        f"date={requested_date.isoformat()}/"
        f"extracted_at={extracted_at.strftime('%Y%m%dT%H%M%S.%fZ')}.json"
    )
    return RawSnapshot(
        content=json.dumps(payload).encode(),
        object_name=object_name,
        extracted_at=extracted_at,
    )


def find_row(rows: list[dict[str, Any]], observed_at: datetime, metric: str) -> dict[str, Any]:
    return next(
        row for row in rows if row["observed_at"] == observed_at and row["metric"] == metric
    )


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


@TRANSFORMATION_PENDING
def test_transform_returns_typed_long_format_rows(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    snapshot = build_snapshot(public_power_payload_factory(date(2026, 8, 1)))

    result = transform_public_power(snapshot)

    assert result.columns == [
        "country",
        "observed_at",
        "metric",
        "value",
        "unit",
        "interval_minutes",
        "source_generated_at",
        "extracted_at",
        "raw_object_name",
    ]
    assert result.height == 96 * 2
    assert {name: str(dtype) for name, dtype in result.schema.items()} == {
        "country": "String",
        "observed_at": "Datetime(time_unit='us', time_zone='UTC')",
        "metric": "String",
        "value": "Float64",
        "unit": "String",
        "interval_minutes": "Int16",
        "source_generated_at": "Datetime(time_unit='us', time_zone='UTC')",
        "extracted_at": "Datetime(time_unit='us', time_zone='UTC')",
        "raw_object_name": "String",
    }


@TRANSFORMATION_PENDING
def test_transform_maps_units_nulls_and_lineage(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    snapshot = build_snapshot(public_power_payload_factory(date(2026, 8, 1)))

    rows = transform_public_power(snapshot).to_dicts()

    first_timestamp = datetime(2026, 7, 31, 22, 0, tzinfo=UTC)
    second_timestamp = datetime(2026, 7, 31, 22, 15, tzinfo=UTC)
    solar = find_row(rows, first_timestamp, "solar")
    explicit_null = find_row(rows, first_timestamp, "renewable_share_of_load")
    missing_metric = find_row(rows, second_timestamp, "renewable_share_of_load")

    assert solar["value"] == 0.0
    assert solar["unit"] == "MW"
    assert explicit_null["value"] is None
    assert explicit_null["unit"] == "%"
    assert missing_metric["value"] is None
    assert solar["country"] == "de"
    assert solar["interval_minutes"] == 15
    assert solar["source_generated_at"] == datetime(2026, 8, 2, 4, 0, tzinfo=UTC)
    assert solar["extracted_at"] == snapshot.extracted_at
    assert solar["raw_object_name"] == snapshot.object_name


@pytest.mark.parametrize(
    ("requested_date", "expected_intervals"),
    [
        (date(2026, 3, 29), 92),
        (date(2026, 10, 25), 100),
    ],
)
@TRANSFORMATION_PENDING
def test_transform_accepts_complete_daylight_saving_days(
    public_power_payload_factory: PublicPowerPayloadFactory,
    requested_date: date,
    expected_intervals: int,
) -> None:
    payload = public_power_payload_factory(requested_date)

    result = transform_public_power(build_snapshot(payload))

    assert result.height == expected_intervals * 2


@TRANSFORMATION_PENDING
def test_transform_accepts_new_described_metric(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["series"].append({"id": "new_metric", "name": "New metric"})
    for point in payload["data"]:
        point["values"]["new_metric"] = 123.4

    result = transform_public_power(build_snapshot(payload))

    assert result.height == 96 * 3
    assert all(row["unit"] == "MW" for row in result.to_dicts() if row["metric"] == "new_metric")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["data"][0]["values"].update({"unknown_metric": 1.0}),
            "unknown metric",
        ),
        (
            lambda payload: payload["data"].pop(),
            "complete local day",
        ),
        (
            lambda payload: payload["data"][0].update({"timestamp": "2026-08-01T00:00:00"}),
            "timezone",
        ),
        (
            lambda payload: payload["data"][1].update(
                {"timestamp": payload["data"][0]["timestamp"]}
            ),
            "duplicate timestamp",
        ),
        (
            lambda payload: payload["data"][0]["values"].update({"solar": "not-a-number"}),
            "finite number or null",
        ),
    ],
)
@TRANSFORMATION_PENDING
def test_transform_rejects_invalid_snapshot(
    public_power_payload_factory: PublicPowerPayloadFactory,
    mutate: Callable[[PublicPowerPayload], object],
    message: str,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    mutate(payload)

    with pytest.raises(PublicPowerTransformationError, match=message):
        transform_public_power(build_snapshot(payload))


@TRANSFORMATION_PENDING
def test_transform_rejects_country_mismatch(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["country"] = "fr"

    with pytest.raises(PublicPowerTransformationError, match="country"):
        transform_public_power(build_snapshot(payload))
