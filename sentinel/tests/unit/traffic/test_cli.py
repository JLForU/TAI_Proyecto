"""CLI del sensor (U5, BR-U5-29/30): códigos de salida y modo --loop."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sentinel.traffic import __main__ as cli
from sentinel.traffic.worker import WindowResult

W1_START = datetime(2026, 11, 19, 12, 0, 0, tzinfo=UTC)
W1_END = datetime(2026, 11, 19, 12, 0, 5, tzinfo=UTC)


def _result(status: str = "emitted") -> WindowResult:
    return WindowResult(  # type: ignore[arg-type]
        status=status, window_start=W1_START, window_end=W1_END, items=1, traffic=1
    )


def _wire(monkeypatch: pytest.MonkeyPatch, run_window, *, valid_config: bool = True) -> None:  # type: ignore[no-untyped-def]
    if valid_config:
        monkeypatch.setenv("SENTINEL_TRAFFIC_WINDOW_SECONDS", "5")
    else:
        monkeypatch.setenv("SENTINEL_TRAFFIC_WINDOW_SECONDS", "7")
    monkeypatch.setattr(cli, "SimulatedSource", lambda **_k: object())
    monkeypatch.setattr(cli, "IngestClient", lambda: _FakeClient())
    monkeypatch.setattr(cli, "run_window", run_window)


class _FakeClient:
    def close(self) -> None:
        return None


def test_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, lambda *_a, **_k: _result("emitted"))
    assert cli.main(["--once"]) == 0

    _wire(monkeypatch, lambda *_a, **_k: _result("export_failed"))
    assert cli.main(["--once"]) == 1

    _wire(monkeypatch, lambda *_a, **_k: _result("source_error"))
    assert cli.main(["--once"]) == 1


def test_exit_code_invalid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, lambda *_a, **_k: _result("emitted"), valid_config=False)
    assert cli.main(["--once"]) == 1


def test_loop_runs_windows_until_sigterm(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def fake_run_window(*_a, **_k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] >= 2:
            cli._TERMINATE = True  # simula SIGTERM atendido entre ventanas
        return _result("emitted")

    _wire(monkeypatch, fake_run_window)
    monkeypatch.setattr(cli, "_sleep_until_next_boundary", lambda _w: None)
    assert cli.main(["--loop"]) == 0
    assert calls["n"] == 2


def test_loop_keeps_going_after_failed_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """P1: en --loop una ventana fallida solo loguea y el loop continúa."""
    calls = {"n": 0}

    def fake_run_window(*_a, **_k):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] >= 3:
            cli._TERMINATE = True
        return _result("export_failed" if calls["n"] < 3 else "emitted")

    _wire(monkeypatch, fake_run_window)
    monkeypatch.setattr(cli, "_sleep_until_next_boundary", lambda _w: None)
    assert cli.main(["--loop"]) == 0
    assert calls["n"] == 3
