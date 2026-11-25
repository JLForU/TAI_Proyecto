"""Configuración estricta del worker de discovery (U4, BR-U4-01..05).

Patrón ``foundation.config``: ``frozen`` + ``extra="forbid"``, fail-fast con
``ConfigError`` — una config inválida no es un estado recuperable (nada se
sondea). ``CoreSettings`` de U1 no cambia (BR-U4-04); el token de ingesta se
lee en ``client.py`` sin redefinir.
"""

from __future__ import annotations

import os
import shlex
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from sentinel.foundation.errors import ConfigError

__all__ = [
    "CONNECT_TIMEOUT_S",
    "DiscoverySettings",
    "PHASE_BUDGET_FRACTIONS",
    "PING_TIMEOUT_S",
    "load_discovery_settings",
    "parse_ports",
]

EnvScopeMode = Literal["cidr", "explicit_hosts"]
EnvScanner = Literal["auto", "nmap", "fixtures"]

_ENV_MAP = {
    "SENTINEL_DISCOVERY_SCOPE_MODE": "scope_mode",
    "SENTINEL_DISCOVERY_HOSTS": "hosts",
    "SENTINEL_DISCOVERY_CIDRS": "cidrs",
    "SENTINEL_DISCOVERY_PORTS": "ports",
    "SENTINEL_DISCOVERY_INTERVAL_MIN": "interval_minutes",
    "SENTINEL_DISCOVERY_TIMEOUT_SECONDS": "timeout_seconds",
    "SENTINEL_DISCOVERY_SCANNER": "scanner",
    "SENTINEL_DISCOVERY_NMAP_ARGS": "nmap_args",
}

#: Timeouts fijos de sonda (P5/Q4=A): sin claves nuevas de config.
PING_TIMEOUT_S = 1.0
CONNECT_TIMEOUT_S = 1.0

#: Presupuesto de fases del ciclo (P4/Q3=A): fracciones del deadline total.
PHASE_BUDGET_FRACTIONS: dict[str, float] = {"arp": 0.20, "icmp": 0.30, "tcp": 0.30, "nmap": 0.20}


class DiscoverySettings(BaseModel):
    """Settings del worker (FD §3.1 / domain-entities §1.6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scope_mode: EnvScopeMode = "explicit_hosts"
    hosts: str = ""
    cidrs: str = ""
    ports: str = "22,80,443"
    interval_minutes: int = 15
    timeout_seconds: int = 30
    scanner: EnvScanner = "auto"
    nmap_args: str = ""

    def hosts_list(self) -> tuple[str, ...]:
        return _split_csv(self.hosts)

    def cidrs_list(self) -> tuple[str, ...]:
        return _split_csv(self.cidrs)


def _split_csv(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def parse_ports(raw: str) -> tuple[int, ...]:
    """CSV de puertos → enteros 1..65535 sin duplicados (BR-U4-05)."""
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts:
        raise ConfigError("ports must not be empty")
    ports: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise ConfigError(f"invalid port: {part}")
        value = int(part)
        if not 1 <= value <= 65535:
            raise ConfigError(f"port out of range: {value}")
        if value in ports:
            raise ConfigError(f"duplicate port: {value}")
        ports.append(value)
    return tuple(ports)


def _validate_business_rules(settings: DiscoverySettings) -> None:
    from sentinel.discovery.scanner import validate_scan_options

    parse_ports(settings.ports)

    if settings.scope_mode == "explicit_hosts" and not settings.hosts_list():
        raise ConfigError("SENTINEL_DISCOVERY_HOSTS must not be empty (explicit_hosts)")
    if settings.scope_mode == "cidr":
        cidrs = settings.cidrs_list()
        if not cidrs:
            raise ConfigError("SENTINEL_DISCOVERY_CIDRS must not be empty (cidr mode)")
        from ipaddress import ip_network

        for raw in cidrs:
            try:
                ip_network(raw, strict=False)
            except ValueError as exc:
                raise ConfigError(f"invalid cidr: {raw}") from exc

    if settings.interval_minutes < 1:
        raise ConfigError("SENTINEL_DISCOVERY_INTERVAL_MIN must be >= 1")
    if not 1 <= settings.timeout_seconds <= 3600:
        raise ConfigError("SENTINEL_DISCOVERY_TIMEOUT_SECONDS must be in 1..3600")

    try:
        extras = shlex.split(settings.nmap_args) if settings.nmap_args.strip() else []
    except ValueError as exc:
        raise ConfigError(f"invalid SENTINEL_DISCOVERY_NMAP_ARGS: {exc}") from exc
    validate_scan_options(extras)


def load_discovery_settings(environ: dict[str, str] | None = None) -> DiscoverySettings:
    """Carga ``DiscoverySettings`` desde ``SENTINEL_DISCOVERY_*`` (fail-fast).

    Lanza :class:`ConfigError` ante cualquier violación (BR-U4-01): allowlist
    vacía, puertos inválidos, intervalo/timeout fuera de rango o flags de
    escaneo fuera de la whitelist (BR-U4-02/05/10).
    """
    env = os.environ if environ is None else environ
    unknown = sorted(
        key for key in env if key.startswith("SENTINEL_DISCOVERY_") and key not in _ENV_MAP
    )
    if unknown:
        raise ConfigError(f"unknown discovery settings: {', '.join(unknown)}")
    data: dict[str, Any] = {
        field: env[env_key] for env_key, field in _ENV_MAP.items() if env_key in env
    }
    try:
        settings = DiscoverySettings.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"invalid discovery settings: {exc}") from exc
    _validate_business_rules(settings)
    return settings
