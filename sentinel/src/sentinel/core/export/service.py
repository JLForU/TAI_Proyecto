"""ExportService — exportación bajo demanda ``csv|json`` con rango (ST-M4-07).

Filas derivadas de la tabla ``events`` (evidencia persistida); orden
determinista ``occurred_at ASC, event_id`` para que el mismo rango produzca
siempre el mismo archivo (BR-U2-39). Salida como ``str`` (AC: formato
determinista).
"""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

from ..db.database import Database
from ..db.repos.events import EventRepository

__all__ = ["ExportService", "CSV_HEADER"]

CSV_HEADER = (
    "timestamp,asset_or_pair,method,protocol,condition,rule,threshold,measured_value,result"
)


class ExportService:
    def __init__(self, db: Database, *, events: EventRepository | None = None) -> None:
        self._db = db
        self._events = events or EventRepository()

    def export(
        self,
        *,
        date_from: str,
        date_to: str,
        fmt: Literal["csv", "json"],
    ) -> str:
        with self._db.read() as conn:
            where, params = self._events._filters(
                date_from=date_from, date_to=date_to, asset_id=None, rule=None, severity=None
            )
            rows = list(
                conn.execute(
                    f"SELECT * FROM events{where} ORDER BY occurred_at ASC, event_id",
                    params,
                )
            )
        records = [_row_to_record(r) for r in rows]
        if fmt == "csv":
            return _to_csv(records)
        return json.dumps(records, ensure_ascii=False, sort_keys=True, indent=2)


def _row_to_record(r) -> dict[str, str]:  # type: ignore[no-untyped-def]
    raw = r["details"]
    details: dict = {}
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
            details = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:  # pragma: no cover - dato corrupto
            details = {}
    elif isinstance(raw, dict):
        details = raw
    return {
        "timestamp": str(r["occurred_at"]),
        "asset_or_pair": str(r["asset_id"] or details.get("pair") or details.get("ip") or "-"),
        "method": str(details.get("method", "")),
        "protocol": str(details.get("protocol", "")),
        "condition": str(details.get("condition", "")),
        "rule": str(r["rule"] or details.get("rule", "")),
        "threshold": str(details.get("threshold", "")),
        "measured_value": str(details.get("measured_value", "")),
        "result": str(details.get("result") or r["type"]),
    }


def _to_csv(records: list[dict[str, str]]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_HEADER.split(","), lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)
    return buf.getvalue()
