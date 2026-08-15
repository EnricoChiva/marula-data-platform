"""Raw ingestion pipeline for Energy-Charts public power data."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from marula_data_platform.clients.energy_charts import ExtractedResponse


class PublicPowerSource(Protocol):
    """Required API-client behavior for this pipeline."""

    def get_public_power(self, country: str, requested_date: date) -> ExtractedResponse: ...


class RawStorage(Protocol):
    """Required object-storage behavior for this pipeline."""

    @property
    def bucket(self) -> str: ...

    def put_json(
        self,
        object_name: str,
        content: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """Location and extraction time of one stored raw response."""

    bucket: str
    object_name: str
    extracted_at: datetime


def extract_public_power(
    source: PublicPowerSource,
    country: str,
    requested_date: date,
) -> ExtractedResponse:
    """Extract one complete day without changing the source response."""
    return source.get_public_power(country=country, requested_date=requested_date)


def build_raw_object_name(country: str, requested_date: date, extracted_at: datetime) -> str:
    """Build an immutable, partition-friendly raw object name."""
    extraction_timestamp = extracted_at.strftime("%Y%m%dT%H%M%S.%fZ")
    return (
        "energy-charts/public-power/"
        f"country={country.lower()}/date={requested_date.isoformat()}/"
        f"extracted_at={extraction_timestamp}.json"
    )


def run_public_power_ingestion(
    source: PublicPowerSource,
    storage: RawStorage,
    country: str,
    requested_date: date,
) -> IngestionResult:
    """Extract a daily response and persist it unchanged in the raw layer."""
    response = extract_public_power(source, country, requested_date)
    object_name = build_raw_object_name(country, requested_date, response.extracted_at)

    storage.put_json(
        object_name=object_name,
        content=response.content,
        metadata={
            "source": "energy-charts.info",
            "source-endpoint": "v2/public_power",
            "source-license": "CC-BY-4.0",
            "country": country.lower(),
            "requested-date": requested_date.isoformat(),
            "request-url": response.request_url,
        },
    )

    return IngestionResult(
        bucket=storage.bucket,
        object_name=object_name,
        extracted_at=response.extracted_at,
    )
