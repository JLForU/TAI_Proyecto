"""Tests de ``gui.validation`` (NFR-U3-SEC-02, P6)."""

from __future__ import annotations

from datetime import date

import pytest

from sentinel.foundation.errors import ValidationError
from sentinel.gui.validation import (
    parse_date,
    parse_date_range,
    parse_format,
    parse_host,
    parse_optional_date,
    parse_page,
)


class TestParseDate:
    def test_valid(self) -> None:
        assert parse_date("2026-11-01", field="from") == date(2026, 11, 1)

    @pytest.mark.parametrize(
        "bad", ["31/12/2026", "2026-13-01", "not-a-date", "2026-11-01T00:00:00"]
    )
    def test_invalid(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            parse_date(bad, field="from")


class TestParseDateRange:
    def test_valid(self) -> None:
        assert parse_date_range("2026-11-01", "2026-11-07") == (
            date(2026, 11, 1),
            date(2026, 11, 7),
        )

    @pytest.mark.parametrize("from_,to", [(None, "2026-11-07"), ("2026-11-01", None), ("", "")])
    def test_required(self, from_: str | None, to: str | None) -> None:
        with pytest.raises(ValidationError, match="required"):
            parse_date_range(from_, to)

    def test_from_after_to(self) -> None:
        with pytest.raises(ValidationError, match="from must be"):
            parse_date_range("2026-11-07", "2026-11-01")


class TestParseOptionalDate:
    def test_none_and_empty(self) -> None:
        assert parse_optional_date(None, field="from") is None
        assert parse_optional_date("", field="to") is None

    def test_valid(self) -> None:
        assert parse_optional_date("2026-11-01", field="from") == date(2026, 11, 1)


class TestParsePage:
    def test_default(self) -> None:
        assert parse_page(None) == 1
        assert parse_page("") == 1

    def test_valid(self) -> None:
        assert parse_page("3") == 3

    @pytest.mark.parametrize("bad", ["0", "-2", "abc", "1.5"])
    def test_invalid(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            parse_page(bad)


class TestParseFormat:
    def test_default_md(self) -> None:
        assert parse_format(None) == "md"
        assert parse_format("") == "md"

    @pytest.mark.parametrize("fmt", ["md", "pdf"])
    def test_valid(self, fmt: str) -> None:
        assert parse_format(fmt) == fmt

    def test_invalid(self) -> None:
        with pytest.raises(ValidationError, match="md or pdf"):
            parse_format("exe")


class TestParseHost:
    @pytest.mark.parametrize(
        "host", ["192.168.1.10", "10.0.0.1", "2001:db8::1", "scanner.local", "gw-01.example.com"]
    )
    def test_valid(self, host: str) -> None:
        assert parse_host(host) == host

    def test_strips_whitespace(self) -> None:
        assert parse_host("  192.168.1.10 ") == "192.168.1.10"

    @pytest.mark.parametrize(
        "bad", ["", "   ", "999.1.1.1", "-bad-.host", "host name", "192.168.1.10;rm -rf /"]
    )
    def test_invalid(self, bad: str) -> None:
        with pytest.raises(ValidationError):
            parse_host(bad)
