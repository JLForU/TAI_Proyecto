"""Worker del ciclo de discovery (U4, FD §3.3/§3.5): fases, deadline, fusión.

Orden ``arp → icmp → tcp → nmap`` con chequeo de deadline en cada fase
(BR-U4-14); timeouts de sonda fijos (P5); pool ≤32 hilos con resultados
normalizados por IP antes de fusionar (P4/determinismo); 1 hallazgo por host
con método preponderante (BR-U4-16). Al final: un solo POST con ``reconcile``
según estado (BR-U4-23) — el worker nunca importa ``sentinel.core`` (BR-U4-26).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from time import monotonic
from typing import TYPE_CHECKING, Literal

from sentinel.discovery.client import to_observations
from sentinel.discovery.config import PHASE_BUDGET_FRACTIONS, DiscoverySettings, parse_ports
from sentinel.discovery.domain import CycleResult, HostFinding, merge_findings, resolve_targets
from sentinel.discovery.scanner import Scanner, ScannerError
from sentinel.discovery.scope import ScopeValidator
from sentinel.foundation.errors import ScopeError
from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import PortInfo

__all__ = ["MAX_PROBE_WORKERS", "run_cycle"]

if TYPE_CHECKING:  # sin import runtime de client (evita ciclo de imports)
    from sentinel.discovery.client import IngestClient


_log = get_logger("discovery.worker")

#: Pool acotado por fase (P4/Q3=A): nunca más hilos que esto escaneando.
MAX_PROBE_WORKERS = 32


def run_cycle(
    settings: DiscoverySettings,
    scanner: Scanner,
    ingest_client: IngestClient,
    timeout_seconds: int,
    hosts: Sequence[str] | None = None,
) -> CycleResult:
    """Ejecuta un ciclo completo: scope → fases → fusión → ingesta única.

    - Fuera de alcance ⇒ ``ScopeError`` **antes** de cualquier paquete (BR-U4-07).
    - Deadline excedido ⇒ ingiere parciales con ``reconcile=false`` y devuelve
      ``status="timeout"`` (BR-U4-15); el runner lo traduce a excepción.
    - Errores de escáner/ingesta propagan (⇒ ``failed``, sin lote — BR-U4-25).
    """
    targets = (
        list(hosts)
        if hosts is not None
        else resolve_targets(
            settings.hosts_list(),
            mode=settings.scope_mode,
            cidrs=settings.cidrs_list(),
        )
    )

    validator = ScopeValidator(settings)
    scope = validator.validate_scope(targets)
    if not scope.ok:
        _log.warning(
            "target out of scope; no packets sent",
            extra={
                "event": "scope_violation",
                "detail": scope.errors[0] if scope.errors else "host fuera de alcance",
                "targets": len(targets),
            },
        )
        raise ScopeError(scope.errors[0] if scope.errors else "host fuera de alcance")

    ports = parse_ports(settings.ports)
    target_set = set(targets)
    started = monotonic()
    deadline = started + timeout_seconds
    arp_end = started + timeout_seconds * PHASE_BUDGET_FRACTIONS["arp"]
    icmp_end = arp_end + timeout_seconds * PHASE_BUDGET_FRACTIONS["icmp"]
    tcp_end = icmp_end + timeout_seconds * PHASE_BUDGET_FRACTIONS["tcp"]

    findings: list[HostFinding] = []
    expired = False
    status: Literal["completed", "timeout", "failed"] = "completed"

    # --- Fase ARP: tabla del sistema filtrada a targets (BR-U4-19) ---------
    if monotonic() < deadline:
        table = scanner.arp_neighbors()
        for ip in sorted(target_set):
            mac = table.get(ip)
            if mac:
                findings.append(HostFinding(ip=ip, mac=mac, method="arp"))

    # --- Fase ICMP: pool con timeout de fase y de deadline global ----------
    if not expired and monotonic() < deadline:
        alive, expired = _probe_phase(
            scanner.ping,
            targets,
            phase_end=min(icmp_end, deadline),
            deadline=deadline,
            workers=MAX_PROBE_WORKERS,
        )
        for ip in sorted(alive):
            findings.append(HostFinding(ip=ip, method="icmp"))

    # --- Fase TCP: connect por target×puerto (pool, normalizado por IP) ----
    if not expired and monotonic() < deadline:
        open_by_ip, expired = _tcp_phase(
            scanner,
            targets,
            ports,
            phase_end=min(tcp_end, deadline),
            deadline=deadline,
            workers=MAX_PROBE_WORKERS,
        )
        for ip in sorted(open_by_ip):
            findings.append(
                HostFinding(
                    ip=ip,
                    ports=sorted(open_by_ip[ip], key=lambda info: info.port),
                    method="tcp",
                )
            )

    # --- Fase Nmap: solo con targets vivos y tiempo restante ---------------
    if not expired and monotonic() < deadline:
        alive_ips = sorted({f.ip for f in findings} & target_set)
        if alive_ips:
            remaining = max(0.0, deadline - monotonic())
            try:
                nmap_findings = scanner.nmap_scan(
                    alive_ips, ports, settings.nmap_args, timeout=remaining
                )
            except ScannerError:
                if monotonic() >= deadline:
                    expired = True  # timeout de nmap contra el deadline
                else:
                    raise  # error de escáner ⇒ ciclo failed (FD §3.6)
            else:
                findings.extend(f for f in nmap_findings if f.ip in target_set)

    merged = merge_findings([f for f in findings if f.ip in target_set])
    partial = expired or monotonic() >= deadline
    status = "timeout" if partial else "completed"
    observed_at = datetime.now(UTC)

    # --- Ingesta única (BR-U4-21/23): reconcile según estado ---------------
    ingest_client.post_ingest(to_observations(merged, observed_at), reconcile=status == "completed")

    return CycleResult(
        status=status,
        hosts_seen=len(merged),
        hosts_targeted=len(targets),
        findings=merged,
        partial=partial,
        error="timeout" if partial else None,
    )


def _probe_phase(  # type: ignore[no-untyped-def]
    probe,  # callable(host) -> bool
    targets: Sequence[str],
    *,
    phase_end: float,
    deadline: float,
    workers: int,
) -> tuple[list[str], bool]:
    """Ejecuta ``probe`` por target en paralelo; devuelve (vivos, deadline_hit)."""
    if not targets or monotonic() >= deadline:
        return [], monotonic() >= deadline
    pool = ThreadPoolExecutor(max_workers=min(workers, len(targets)))
    futures = {pool.submit(_safe_probe, probe, ip): ip for ip in targets}
    alive: list[str] = []
    deadline_hit = False
    try:
        remaining = max(0.0, min(phase_end, deadline) - monotonic())
        try:
            for future in as_completed(futures, timeout=remaining):
                if future.result():
                    alive.append(futures[future])
        except FuturesTimeout:
            deadline_hit = monotonic() >= deadline
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return alive, deadline_hit


def _safe_probe(probe: Callable[[str], bool], host: str) -> bool:
    try:
        return bool(probe(host))
    except Exception:  # noqa: BLE001 - una sonda caída no tumba el ciclo
        return False


def _tcp_phase(
    scanner: Scanner,
    targets: Sequence[str],
    ports: Sequence[int],
    *,
    phase_end: float,
    deadline: float,
    workers: int,
) -> tuple[dict[str, list[PortInfo]], bool]:
    """Connect target×puerto en parallelo; resultados normalizados por IP."""
    pairs = [(ip, port) for ip in targets for port in ports]
    if not pairs or monotonic() >= deadline:
        return {}, monotonic() >= deadline
    pool = ThreadPoolExecutor(max_workers=min(workers, len(pairs)))
    futures = {pool.submit(_safe_tcp, scanner, ip, port): (ip, port) for ip, port in pairs}
    open_by_ip: dict[str, list[PortInfo]] = {}
    deadline_hit = False
    try:
        remaining = max(0.0, min(phase_end, deadline) - monotonic())
        try:
            for future in as_completed(futures, timeout=remaining):
                ip, port = futures[future]
                if future.result():
                    open_by_ip.setdefault(ip, []).append(
                        PortInfo(port=port, protocol="tcp", state="open", confidence="probable")
                    )
        except FuturesTimeout:
            deadline_hit = monotonic() >= deadline
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return open_by_ip, deadline_hit


def _safe_tcp(scanner: Scanner, host: str, port: int) -> bool:
    try:
        return bool(scanner.tcp_open(host, port))
    except Exception:  # noqa: BLE001 - sonda caída ⇒ puerto tratado como cerrado
        return False
