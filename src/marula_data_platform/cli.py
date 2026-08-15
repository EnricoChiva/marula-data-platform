"""Command-line entry point for Marula data pipelines."""

import argparse
from collections.abc import Sequence
from datetime import date

from marula_data_platform.clients.energy_charts import EnergyChartsClient
from marula_data_platform.config import Settings
from marula_data_platform.pipelines.public_power import run_public_power_ingestion
from marula_data_platform.storage.minio import MinioStorage


def iso_date(value: str) -> date:
    """Parse an ISO date for argparse with a useful validation message."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected a date in YYYY-MM-DD format") from error


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line interface."""
    parser = argparse.ArgumentParser(prog="marula-pipeline")
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser(
        "ingest-public-power",
        help="store one day of Energy-Charts public power data in the raw bucket",
    )
    ingest_parser.add_argument("--date", required=True, type=iso_date, dest="requested_date")
    ingest_parser.add_argument("--country", default="de")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the requested Marula pipeline command."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    settings = Settings()
    storage = MinioStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key.get_secret_value(),
        secret_key=settings.minio_secret_key.get_secret_value(),
        bucket=settings.minio_bucket,
        secure=settings.minio_secure,
    )

    with EnergyChartsClient(
        base_url=settings.energy_charts_base_url,
        timeout_seconds=settings.energy_charts_timeout_seconds,
    ) as source:
        result = run_public_power_ingestion(
            source=source,
            storage=storage,
            country=args.country,
            requested_date=args.requested_date,
        )

    print(f"Stored raw response at s3://{result.bucket}/{result.object_name}")
