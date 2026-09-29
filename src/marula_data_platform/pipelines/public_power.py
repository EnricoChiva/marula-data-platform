"""Ingestion and transformation pipeline for Energy-Charts public power data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Literal, Protocol
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from marula_data_platform.clients.energy_charts import ExtractedResponse

if TYPE_CHECKING:
    import polars as pl


class PublicPowerTransformationError(ValueError):
    """Raised when a raw public-power snapshot violates the transformation contract."""


def _require_non_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


NonBlankString = Annotated[
    str,
    Field(strict=True),
    AfterValidator(_require_non_blank),
]
CountryCode = Annotated[
    str,
    Field(strict=True, pattern=r"^[A-Za-z]{2}$"),
]
PositiveIntervalMinutes = Annotated[
    int,
    Field(strict=True, gt=0),
]
FiniteNumber = Annotated[
    float,
    Field(strict=True, allow_inf_nan=False),
]
AwareTimestamp = Annotated[
    AwareDatetime,
    Field(strict=True),
]


class PublicPowerSeries(BaseModel):
    """Describe one metric required to interpret public-power values."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    id: NonBlankString
    unit: NonBlankString | None = None


class PublicPowerDataPoint(BaseModel):
    """Represent all public-power values reported for one instant."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    timestamp: AwareTimestamp
    values: dict[NonBlankString, FiniteNumber | None]


class PublicPowerPayload(BaseModel):
    """Validate the Energy-Charts fields required by the transformation."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: Literal["2.0"]
    generated_at: AwareTimestamp
    country: CountryCode
    timezone: NonBlankString
    interval_minutes: PositiveIntervalMinutes
    unit: NonBlankString | None = None
    series: Annotated[list[PublicPowerSeries], Field(min_length=1)]
    data: Annotated[list[PublicPowerDataPoint], Field(min_length=1)]

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        """Normalize a valid two-letter country code for stable keys."""
        return value.lower()

    @field_validator("timezone")
    @classmethod
    def require_known_timezone(cls, value: str) -> str:
        """Require an IANA timezone understood by the runtime."""
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a known IANA timezone") from error
        return value

    @model_validator(mode="after")
    def require_consistent_series_and_data(self) -> PublicPowerPayload:
        """Validate relationships that span series definitions and data points."""
        series_ids = [series.id for series in self.series]
        duplicate_series_ids = sorted(
            series_id for series_id in set(series_ids) if series_ids.count(series_id) > 1
        )
        if duplicate_series_ids:
            raise ValueError(f"duplicate series id: {', '.join(duplicate_series_ids)}")

        if self.unit is None:
            missing_units = [series.id for series in self.series if series.unit is None]
            if missing_units:
                raise ValueError(f"unit is missing for series: {', '.join(missing_units)}")

        known_series_ids = set(series_ids)
        observed_metric_ids = {metric_id for point in self.data for metric_id in point.values}
        unknown_metric_ids = sorted(observed_metric_ids - known_series_ids)
        if unknown_metric_ids:
            raise ValueError(f"unknown metric: {', '.join(unknown_metric_ids)}")

        timestamps = [point.timestamp for point in self.data]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("duplicate timestamp")

        return self


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


@dataclass(frozen=True, slots=True)
class RawSnapshot:
    """Immutable raw content and the lineage needed by a transformation."""

    content: bytes
    object_name: str
    extracted_at: datetime


def extract_public_power(
    source: PublicPowerSource,
    country: str,
    requested_date: date,
) -> ExtractedResponse:
    """Extract one complete day without changing the source response."""
    return source.get_public_power(country=country, requested_date=requested_date)


def transform_public_power(snapshot: RawSnapshot) -> pl.DataFrame:
    """Transform one validated daily snapshot into typed long-format rows."""
    raise NotImplementedError("public-power transformation is implemented in step 8")


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
