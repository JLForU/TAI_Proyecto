"""NFR-U7-PERF-01: p95 de recolección << 1 s (informativo, 50 muestras).

Mide ``collect(db=...)`` en proceso (sin HTTP) con la BD ya inicializada; no
forma parte de un gate de cobertura, solo evita regresiones obvias (p. ej. un
``SELECT`` sin índice sobre ``observations``).
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from sentinel.core.db.database import Database
from sentinel.core.metrics.collect import collect


def test_collect_p95_under_one_second(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "latency.db"))
    db.startup_checks()
    collect(db=db)  # warmup (imports perezosos, caches de SQLite)
    timings: list[float] = []
    for _ in range(50):
        start = time.perf_counter()
        collect(db=db)
        timings.append(time.perf_counter() - start)
    p95 = statistics.quantiles(timings, n=20)[18]
    assert p95 < 1.0, f"p95={p95:.4f}s"
