"""Parsers puros de query params de la GUI (NFR-U3-SEC-02, P6 / Q5=NFR=A).

Cada parser es una función pura ``str -> valor`` o lanza
``foundation.errors.ValidationError`` (mapeada a **400** por el handler de
U2). Sin FastAPI aquí: testeable en aislamiento (MNT-02).
"""

from __future__ import annotations

import ipaddress
import re
from datetime import date

from sentinel.foundation.errors import ValidationError

__all__ = [
    "parse_date",
    "parse_date_range",
    "parse_format",
    "parse_host",
    "parse_optional_date",
    "parse_page",
]

_HOSTNAME_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*)$"
)


def parse_date(value: str, *, field: str) -> date:
    """``YYYY-MM-DD`` estricto ⇒ :class:`date`; si no, ``ValidationError``."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError(f"{field} must be YYYY-MM-DD") from exc


def parse_optional_date(value: str | None, *, field: str) -> date | None:
    """Como :func:`parse_date` pero ``None``/vacío ⇒ ``None`` (filtro opcional)."""
    if value is None or value == "":
        return None
    return parse_date(value, field=field)


def parse_date_range(from_: str | None, to: str | None) -> tuple[date, date]:
    """Rango **requerido** (BR-U3-24): ambos ``YYYY-MM-DD`` y ``from <= to``."""
    if not from_ or not to:
        raise ValidationError("from and to are required (YYYY-MM-DD)")
    start = parse_date(from_, field="from")
    end = parse_date(to, field="to")
    if start > end:
        raise ValidationError("from must be <= to")
    return start, end


def parse_page(value: str | None) -> int:
    """``page >= 1`` (default 1); no numérico o ``< 1`` ⇒ ``ValidationError``."""
    if value is None or value == "":
        return 1
    try:
        page = int(value)
    except (ValueError, TypeError) as exc:
        raise ValidationError("page must be an integer >= 1") from exc
    if page < 1:
        raise ValidationError("page must be an integer >= 1")
    return page


def parse_format(value: str | None) -> str:
    """``format`` ∈ {``md`` (default), ``pdf``} (BR-U3-19)."""
    if value is None or value == "":
        return "md"
    if value in ("md", "pdf"):
        return value
    raise ValidationError("format must be md or pdf")


def parse_host(value: str) -> str:
    """Forma de IP (v4/v6) u hostname para el trigger de discovery.

    No resuelve DNS ni comprueba alcance (el allowlist es de U4, IP4).
    """
    if not value or not value.strip():
        raise ValidationError("host is required")
    host = value.strip()
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    # "999.1.1.1" tiene forma de hostname pero es un IP malformado: rechazar.
    if re.fullmatch(r"[\d.]+", host):
        raise ValidationError("host must be an IP address or hostname")
    if _HOSTNAME_RE.match(host):
        return host
    raise ValidationError("host must be an IP address or hostname")
