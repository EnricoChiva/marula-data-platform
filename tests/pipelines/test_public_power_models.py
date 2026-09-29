import json
from collections.abc import Callable
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from marula_data_platform.pipelines.public_power import PublicPowerPayload

PublicPowerPayloadDict = dict[str, Any]
PublicPowerPayloadFactory = Callable[[date], PublicPowerPayloadDict]


def validate_payload(payload: PublicPowerPayloadDict) -> PublicPowerPayload:
    return PublicPowerPayload.model_validate_json(json.dumps(payload))


def test_payload_validates_required_fields_and_ignores_additional_fields(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["country"] = "DE"
    payload["future_api_field"] = {"can": "be ignored"}
    payload["series"][0].pop("name")

    result = validate_payload(payload)

    assert result.schema_version == "2.0"
    assert result.country == "de"
    assert result.series[0].id == "solar"
    assert result.series[0].unit is None
    assert result.data[0].timestamp.utcoffset() is not None
    assert not hasattr(result, "future_api_field")
    assert not hasattr(result.series[0], "name")


def test_payload_rejects_unsupported_schema_version(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["schema_version"] = "3.0"

    with pytest.raises(ValidationError, match="2.0"):
        validate_payload(payload)


@pytest.mark.parametrize("invalid_value", ["42.5", True, float("nan"), float("inf")])
def test_payload_rejects_non_strict_or_non_finite_measurement_values(
    public_power_payload_factory: PublicPowerPayloadFactory,
    invalid_value: object,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["data"][0]["values"]["solar"] = invalid_value

    with pytest.raises(ValidationError):
        validate_payload(payload)


def test_payload_accepts_integer_float_null_and_missing_measurement_values(
    public_power_payload_factory: PublicPowerPayloadFactory,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    payload["data"][0]["values"]["solar"] = 42
    payload["data"][0]["values"]["renewable_share_of_load"] = None
    payload["data"][1]["values"] = {}

    result = validate_payload(payload)

    assert result.data[0].values["solar"] == 42.0
    assert result.data[0].values["renewable_share_of_load"] is None
    assert result.data[1].values == {}


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.update({"interval_minutes": "15"}),
            "valid integer",
        ),
        (
            lambda payload: payload.update({"timezone": "Not/A_Timezone"}),
            "known IANA timezone",
        ),
        (
            lambda payload: payload["data"][0].update({"timestamp": "2026-08-01T00:00:00"}),
            "timezone",
        ),
        (
            lambda payload: payload["series"].append({"id": "solar", "unit": "MW"}),
            "duplicate series id",
        ),
        (
            lambda payload: payload["data"][0]["values"].update({"unknown_metric": 1.0}),
            "unknown metric",
        ),
        (
            lambda payload: payload["data"][1].update(
                {"timestamp": payload["data"][0]["timestamp"]}
            ),
            "duplicate timestamp",
        ),
        (
            lambda payload: (
                payload.update({"unit": None}),
                payload["series"][0].pop("unit", None),
            ),
            "unit is missing",
        ),
    ],
)
def test_payload_rejects_contract_violations(
    public_power_payload_factory: PublicPowerPayloadFactory,
    mutate: Callable[[PublicPowerPayloadDict], object],
    message: str,
) -> None:
    payload = public_power_payload_factory(date(2026, 8, 1))
    mutate(payload)

    with pytest.raises(ValidationError, match=message):
        validate_payload(payload)
