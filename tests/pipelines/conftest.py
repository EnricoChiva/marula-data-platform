"""Synthetic Energy-Charts payloads for public-power pipeline tests."""

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest

PublicPowerPayload = dict[str, Any]
PublicPowerPayloadFactory = Callable[[date], PublicPowerPayload]


def build_public_power_payload(requested_date: date) -> PublicPowerPayload:
    """Build one complete synthetic local day with two representative series."""
    timezone = ZoneInfo("Europe/Berlin")
    interval = timedelta(minutes=15)
    start_local = datetime.combine(requested_date, time.min, tzinfo=timezone)
    end_local = datetime.combine(
        requested_date + timedelta(days=1),
        time.min,
        tzinfo=timezone,
    )

    current_utc = start_local.astimezone(UTC)
    end_utc = end_local.astimezone(UTC)
    data: list[dict[str, Any]] = []

    while current_utc < end_utc:
        index = len(data)
        values: dict[str, float | None] = {
            "solar": float(index) * 10.5,
        }

        if index == 0:
            values["renewable_share_of_load"] = None
        elif index > 1:
            values["renewable_share_of_load"] = 50.0 + (index % 10) / 10

        data.append(
            {
                "timestamp": current_utc.astimezone(timezone).isoformat(),
                "values": values,
            }
        )
        current_utc += interval

    generated_at = datetime.combine(
        requested_date + timedelta(days=1),
        time(hour=6),
        tzinfo=timezone,
    )

    return {
        "schema_version": "2.0",
        "generated_at": generated_at.isoformat(),
        "available_from": data[0]["timestamp"],
        "available_until": data[-1]["timestamp"],
        "country": "de",
        "bidding_zone": None,
        "timezone": "Europe/Berlin",
        "resolution": "PT15M",
        "interval_minutes": 15,
        "unit": "MW",
        "endpoint": "public_power",
        "deprecated": False,
        "license": "CC BY 4.0, attribution: energy-charts.info",
        "attributes": {},
        "series": [
            {
                "id": "solar",
                "name": "Solar",
            },
            {
                "id": "renewable_share_of_load",
                "name": "Renewable share of load",
                "unit": "%",
            },
        ],
        "data": data,
    }


@pytest.fixture
def public_power_payload_factory() -> PublicPowerPayloadFactory:
    """Provide a factory so individual tests can mutate isolated payloads."""
    return build_public_power_payload
