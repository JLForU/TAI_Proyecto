"""Tests de la jerarquía de errores (BR-23, BR-24)."""

from __future__ import annotations

from sentinel.foundation.errors import (
    ConfigError,
    IngestionError,
    ProbeError,
    ScopeError,
    SentinelError,
    StorageError,
    ValidationError,
)


def test_hierarchy() -> None:
    for cls in (
        ConfigError,
        ScopeError,
        ValidationError,
        ProbeError,
        IngestionError,
        StorageError,
    ):
        assert issubclass(cls, SentinelError)
        assert issubclass(cls, Exception)


def test_stable_codes() -> None:
    assert ScopeError("x").code == "scope_violation"
    assert ConfigError("x").code == "config_error"
    assert ValidationError("x").code == "validation_error"
    assert ProbeError("x").code == "probe_error"
    assert IngestionError("x").code == "ingestion_error"
    assert StorageError("x").code == "storage_error"
    assert SentinelError("x").code == "sentinel_error"


def test_code_override() -> None:
    err = ScopeError("custom", code="host_not_in_scope")
    assert err.code == "host_not_in_scope"
    assert err.message == "custom"


def test_message_is_str() -> None:
    assert str(ConfigError("bad config")) == "bad config"
