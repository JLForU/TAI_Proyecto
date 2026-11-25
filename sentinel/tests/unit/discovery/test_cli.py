"""CLI standalone (U4, BR-U4-30/32): códigos de salida y modo --loop."""

from __future__ import annotations

import pytest

from sentinel.discovery import __main__ as cli
from sentinel.discovery.config import DiscoverySettings
from sentinel.discovery.domain import CycleResult
from sentinel.foundation.errors import ConfigError, ScopeError


def _completed() -> CycleResult:
    return CycleResult(status="completed", hosts_seen=2, hosts_targeted=2)


def _timeout() -> CycleResult:
    return CycleResult(
        status="timeout", hosts_seen=1, hosts_targeted=2, partial=True, error="timeout"
    )


def _wire(monkeypatch: pytest.MonkeyPatch, run_cycle) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("SENTINEL_DISCOVERY_HOSTS", "10.0.0.1")
    monkeypatch.setattr(cli, "create_scanner", lambda _settings: object())
    monkeypatch.setattr(cli, "IngestClient", lambda: object())
    monkeypatch.setattr(cli, "run_cycle", run_cycle)


def test_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, lambda *_a, **_k: _completed())
    assert cli.main(["--once"]) == 0

    _wire(monkeypatch, lambda *_a, **_k: _timeout())
    assert cli.main(["--once"]) == 1


def test_exit_code_failed_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):  # type: ignore[no-untyped-def]
        raise ScopeError("host fuera de alcance")

    _wire(monkeypatch, boom)
    assert cli.main(["--once"]) == 1


def test_failed_cycle_logs_discovery_cycle_failed(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    def boom(*_a, **_k):  # type: ignore[no-untyped-def]
        raise ScopeError("host fuera de alcance")

    _wire(monkeypatch, boom)
    with caplog.at_level(logging.ERROR):
        assert cli.main(["--once"]) == 1
    events = [r.event for r in caplog.records if hasattr(r, "event")]
    assert "discovery_cycle_failed" in events
    causes = [r.cause for r in caplog.records if hasattr(r, "cause")]
    assert "scope_violation" in causes


def test_timeout_logs_cause_timeout(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    import logging

    _wire(monkeypatch, lambda *_a, **_k: _timeout())
    with caplog.at_level(logging.ERROR):
        assert cli.main(["--once"]) == 1
    causes = [r.cause for r in caplog.records if hasattr(r, "cause")]
    assert "timeout" in causes


def test_config_error_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SENTINEL_DISCOVERY_HOSTS", raising=False)
    monkeypatch.delenv("SENTINEL_DISCOVERY_CIDRS", raising=False)
    monkeypatch.delenv("SENTINEL_DISCOVERY_SCOPE_MODE", raising=False)
    assert cli.main(["--once"]) == 1


def test_invalid_interval_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    _wire(monkeypatch, lambda *_a, **_k: _completed())
    assert cli.main(["--once", "--interval", "0"]) == 1


def test_loop_keeps_cycling_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """P1: fallo por ciclo ⇒ log + siguiente intervalo, sin circuit breaker."""
    runs: list[str] = []
    sleeps: list[int] = []

    def run_cycle(*_a, **_k):  # type: ignore[no-untyped-def]
        runs.append("run")
        if len(runs) == 1:
            raise ScopeError("host fuera de alcance")
        return _completed()

    def fake_sleep(minutes: int) -> None:
        sleeps.append(minutes)
        if len(sleeps) >= 2:
            raise _StopLoopError()

    class _StopLoopError(Exception):
        pass

    _wire(monkeypatch, run_cycle)
    monkeypatch.setattr(cli, "sleep", fake_sleep)
    monkeypatch.setattr(cli, "load_discovery_settings", lambda: DiscoverySettings(hosts="10.0.0.1"))

    with pytest.raises(_StopLoopError):
        cli.main(["--loop", "--interval", "5"])
    assert len(runs) == 2
    assert sleeps == [300, 300]


def test_loop_uses_settings_interval(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[int] = []

    class _StopLoopError(Exception):
        pass

    def fake_sleep(minutes: int) -> None:
        seen.append(minutes)
        raise _StopLoopError

    _wire(monkeypatch, lambda *_a, **_k: _completed())
    monkeypatch.setattr(cli, "sleep", fake_sleep)
    monkeypatch.setattr(
        cli,
        "load_discovery_settings",
        lambda: DiscoverySettings(hosts="10.0.0.1", interval_minutes=7),
    )
    with pytest.raises(_StopLoopError):
        cli.main(["--loop"])
    assert seen == [420]


def test_config_error_from_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad() -> DiscoverySettings:
        raise ConfigError("boom")

    monkeypatch.setattr(cli, "load_discovery_settings", bad)
    assert cli.main(["--once"]) == 1
