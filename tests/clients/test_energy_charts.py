from datetime import date

import httpx
import pytest

from marula_data_platform.clients.energy_charts import (
    EnergyChartsClient,
    EnergyChartsClientError,
)


def test_get_public_power_returns_unmodified_response() -> None:
    expected_content = b'{"series": [], "data": []}'

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/public_power"
        assert request.url.params["country"] == "de"
        assert request.url.params["start"] == "2026-08-01"
        assert request.url.params["end"] == "2026-08-01"
        assert request.headers["user-agent"] == "marula-data-platform/0.1.0"
        return httpx.Response(200, content=expected_content)

    with EnergyChartsClient(transport=httpx.MockTransport(handler)) as client:
        response = client.get_public_power("DE", date(2026, 8, 1))

    assert response.content == expected_content
    assert response.extracted_at.tzinfo is not None


def test_get_public_power_wraps_http_errors() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "temporarily unavailable"})

    with (
        EnergyChartsClient(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(EnergyChartsClientError, match="request failed"),
    ):
        client.get_public_power("de", date(2026, 8, 1))
