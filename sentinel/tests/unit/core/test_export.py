"""Tests de ExportService (ST-M4-07, BR-U2-39, Q7 FD)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sentinel.core.db.database import Database
from sentinel.core.export.service import CSV_HEADER, ExportService
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.models import Batch, DiscoveryObservation

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)
RANGE_FROM = "2000-01-01T00:00:00+00:00"
RANGE_TO = "2100-01-01T00:00:00+00:00"


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "export.db"))
    database.startup_checks()
    yield database
    database.close()


@pytest.fixture()
def export(db: Database) -> ExportService:
    ing = IngestionService(db, missing_cycles=3)
    ing.process(
        Batch(
            items=[
                DiscoveryObservation(
                    observed_at=NOW + timedelta(seconds=i),
                    ip=f"10.0.0.{i}",
                    mac=None,
                    hostname=f"h{i}",
                    method="arp",
                )
                for i in (1, 2)
            ]
        )
    )
    return ExportService(db)


def test_csv_header_and_rows(export: ExportService) -> None:
    out = export.export(date_from=RANGE_FROM, date_to=RANGE_TO, fmt="csv")
    lines = out.splitlines()
    assert lines[0] == CSV_HEADER
    assert len(lines) == 3  # header + 2 eventos


def test_json_deterministic(export: ExportService) -> None:
    a = export.export(date_from=RANGE_FROM, date_to=RANGE_TO, fmt="json")
    b = export.export(date_from=RANGE_FROM, date_to=RANGE_TO, fmt="json")
    assert a == b
    records = json.loads(a)
    assert len(records) == 2
    assert records[0].keys() == {
        "timestamp",
        "asset_or_pair",
        "method",
        "protocol",
        "condition",
        "rule",
        "threshold",
        "measured_value",
        "result",
    }
    # orden determinista por occurred_at ASC
    assert records[0]["timestamp"] <= records[1]["timestamp"]


def test_range_filters_rows(export: ExportService) -> None:
    # occurred_at = instante de ingesta (tiempo real): rangos calculados
    future = export.export(
        date_from=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        date_to=RANGE_TO,
        fmt="csv",
    )
    assert len(future.splitlines()) == 1  # solo header
    empty = export.export(date_from=RANGE_FROM, date_to="2026-01-01T00:00:00+00:00", fmt="csv")
    assert len(empty.splitlines()) == 1  # solo header
    full = export.export(date_from=RANGE_FROM, date_to=RANGE_TO, fmt="csv")
    assert len(full.splitlines()) == 3  # header + 2
