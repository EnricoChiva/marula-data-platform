import argparse
from datetime import date

import pytest

from marula_data_platform.cli import iso_date, main


def test_main_without_command_prints_help(capsys) -> None:
    main([])

    captured = capsys.readouterr()
    assert "ingest-public-power" in captured.out


def test_iso_date_parses_valid_date() -> None:
    assert iso_date("2026-08-01") == date(2026, 8, 1)


def test_iso_date_rejects_invalid_format() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="YYYY-MM-DD"):
        iso_date("01.08.2026")
