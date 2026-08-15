"""HTTP client for the Energy-Charts API."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx


class EnergyChartsClientError(RuntimeError):
    """Raised when Energy Charts cannot provide a valid response."""


@dataclass(frozen=True, slots=True)
class ExtractedResponse:
    """Unmodified API response plus extraction metadata."""

    content: bytes
    request_url: str
    extracted_at: datetime


class EnergyChartsClient:
    """Synchronous client for the machine-readable Energy-Charts v2 API."""

    def __init__(
        self,
        base_url: str = "https://api.energy-charts.info",
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout_seconds,
            transport=transport or httpx.HTTPTransport(retries=2),
            headers={
                "Accept": "application/json",
                "User-Agent": "marula-data-platform/0.1.0",
            },
        )

    def __enter__(self) -> "EnergyChartsClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release network resources."""
        self._client.close()

    def get_public_power(self, country: str, requested_date: date) -> ExtractedResponse:
        """Fetch one complete local day of public net electricity production."""
        normalized_country = country.strip().lower()
        if len(normalized_country) != 2 or not normalized_country.isalpha():
            raise ValueError("country must be a two-letter country code")

        try:
            response = self._client.get(
                "/v2/public_power",
                params={
                    "country": normalized_country,
                    "start": requested_date.isoformat(),
                    "end": requested_date.isoformat(),
                },
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise EnergyChartsClientError(
                f"Energy Charts request failed for {normalized_country} on {requested_date}"
            ) from error

        if not isinstance(payload, dict) or "data" not in payload or "series" not in payload:
            raise EnergyChartsClientError("Energy Charts returned an unexpected response structure")

        return ExtractedResponse(
            content=response.content,
            request_url=str(response.request.url),
            extracted_at=datetime.now(UTC),
        )
