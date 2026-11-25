"""Hook `on_accepted` de IngestionService (FD §3.2, BR-U6-14/15, U6)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from sentinel.core.db.database import Database
from sentinel.core.ingestion.service import IngestionService
from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import Batch, DiscoveryObservation, Observation

# Logger instanciado en collection: pytest adjunta su handler de captura a los
# loggers existentes, y get_logger fija propagate=False (patrón de U5).
_log = get_logger("core.ingestion")

NOW = datetime(2026, 11, 11, 10, 0, 0, tzinfo=UTC)


@pytest.fixture()
def db(tmp_path: Path) -> Database:
    database = Database(str(tmp_path / "hook.db"))
    database.startup_checks()
    yield database
    database.close()


def _disc(ip: str, t: datetime = NOW) -> DiscoveryObservation:
    return DiscoveryObservation(
        observed_at=t, ip=ip, mac="aa:bb:cc:dd:ee:ff", hostname="host", method="arp"
    )


def test_hook_receives_accepted_only(db: Database) -> None:
    """Solo las aceptadas llegan al hook; las deduplicadas no (BR-U6-14)."""
    received: list[list[Observation]] = []
    svc = IngestionService(db, missing_cycles=3, on_accepted=received.append)

    batch = Batch(items=[_disc("10.0.0.1"), _disc("10.0.0.2")])
    first = svc.process(batch)
    assert first.accepted == 2 and first.deduplicated == 0

    # Reenvío idéntico ⇒ deduplicadas ⇒ el hook NO se invoca de nuevo.
    second = svc.process(batch)
    assert second.accepted == 0 and second.deduplicated == 2

    assert len(received) == 1
    assert len(received[0]) == 2
    assert all(isinstance(o, DiscoveryObservation) for o in received[0])


def test_hook_exception_swallowed(db: Database, caplog: pytest.LogCaptureFixture) -> None:
    """Un hook que lanza jamás rompe el 202 (BR-U6-15): log + resultado OK."""
    import logging

    def boom(_: list[Observation]) -> None:
        raise RuntimeError("baseline store down")

    svc = IngestionService(db, missing_cycles=3, on_accepted=boom)
    with caplog.at_level(logging.WARNING):
        result = svc.process(Batch(items=[_disc("10.0.0.3")]))
    assert result.accepted == 1  # 202 igual: el hook no afecta el resultado
    events = [getattr(r, "event", None) for r in caplog.records]
    assert "ingestion_hook_failed" in events


def test_hook_none_default_regression(db: Database) -> None:
    """Sin hook ⇒ comportamiento idéntico al actual (regresión U2)."""
    svc = IngestionService(db, missing_cycles=3)
    assert getattr(svc, "_on_accepted", None) is None
    batch = Batch(items=[_disc("10.0.0.4")])
    result = svc.process(batch)
    assert result.accepted == 1
    # Reenvío ⇒ deduplicación intacta
    again = svc.process(batch)
    assert again.deduplicated == 1 and again.accepted == 0


def test_hook_receives_only_batch_items(db: Database) -> None:
    """El hook recibe exactamente las observaciones aceptadas de ESTE lote."""
    seen: list[Observation] = []
    svc = IngestionService(db, missing_cycles=3, on_accepted=seen.extend)
    svc.process(Batch(items=[_disc("10.0.0.5")]))
    svc.process(Batch(items=[_disc("10.0.0.6")]))
    assert len(seen) == 2
    ips = {str(o.ip) for o in seen if isinstance(o, DiscoveryObservation)}  # type: ignore[union-attr]
    assert ips == {"10.0.0.5", "10.0.0.6"}


def test_hook_not_called_on_empty_accept(db: Database) -> None:
    """Lote totalmente deduplicado ⇒ sin aceptadas ⇒ hook no invocado."""
    calls: list[Any] = []
    svc = IngestionService(db, missing_cycles=3, on_accepted=lambda obs: calls.append(obs))
    batch = Batch(items=[_disc("10.0.0.7")])
    svc.process(batch)
    svc.process(batch)  # todo deduplicado
    assert len(calls) == 1
