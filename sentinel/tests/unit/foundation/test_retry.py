"""Tests de with_retries (P3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sentinel.foundation.errors import IngestionError
from sentinel.foundation.retry import with_retries


def test_success_first_try() -> None:
    with patch("sentinel.foundation.retry.time.sleep") as sleep:
        assert with_retries(lambda: 42, attempts=3, jitter=False) == 42
        sleep.assert_not_called()


def test_success_after_retries() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ValueError("boom")
        return "ok"

    with patch("sentinel.foundation.retry.time.sleep") as sleep:
        result = with_retries(flaky, attempts=5, base_delay=0.5, jitter=False)
        assert result == "ok"
        assert calls["n"] == 3
        assert [c.args[0] for c in sleep.call_args_list] == [0.5, 1.0]


def test_exhausted_attempts_wraps_in_ingestion_error() -> None:
    def always_fails() -> None:
        raise ConnectionError("down")

    with patch("sentinel.foundation.retry.time.sleep") as sleep:
        with pytest.raises(IngestionError) as exc_info:
            with_retries(
                always_fails, attempts=3, base_delay=1.0, jitter=False, operation="send batch"
            )
        assert exc_info.value.code == "ingestion_error"
        assert isinstance(exc_info.value.__cause__, ConnectionError)
        assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0]
        assert sleep.call_count == 2


def test_backoff_capped_at_max_delay() -> None:
    with patch("sentinel.foundation.retry.time.sleep") as sleep:
        with pytest.raises(IngestionError):
            with_retries(
                lambda: (_ for _ in ()).throw(ValueError("x")),
                attempts=6,
                base_delay=1.0,
                max_delay=3.0,
                jitter=False,
            )
        delays = [c.args[0] for c in sleep.call_args_list]
        assert delays == [1.0, 2.0, 3.0, 3.0, 3.0]


def test_jitter_applied() -> None:
    with (
        patch("sentinel.foundation.retry.time.sleep") as sleep,
        patch("sentinel.foundation.retry.random.uniform", return_value=0.5) as uniform,
    ):
        with pytest.raises(IngestionError):
            with_retries(
                lambda: (_ for _ in ()).throw(ValueError("x")),
                attempts=2,
                base_delay=1.0,
                jitter=True,
            )
        uniform.assert_called_once()
        assert sleep.call_args.args[0] == 1.0 + 0.5


def test_non_retryable_exception_propagates() -> None:
    def type_error() -> None:
        raise TypeError("bug")

    with patch("sentinel.foundation.retry.time.sleep") as sleep:
        with pytest.raises(TypeError):
            with_retries(type_error, attempts=3, retry_on=(ValueError,))
        sleep.assert_not_called()


def test_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        with_retries(lambda: 1, attempts=0)
