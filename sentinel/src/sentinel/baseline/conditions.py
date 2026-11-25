"""ConditionService — condiciones deterministas R-01 (U6, C5, FD §3.2–3.6).

Orquestador sin I/O propio: todo efecto pasa por los ``Protocol``
duck-typing inyectados (``BaselineStore``/``AlertStore``/``Clock``) — la
frontera jamás importa ``sentinel.core`` ni ``sqlite3`` (BR-U6-01). Patrones:
degradación con log sin excepción propagada (P1), evaluación acotada a la
serie observada (P4), reloj inyectable (P11).
"""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, Protocol

from sentinel.foundation.logging import get_logger
from sentinel.foundation.models import ConditionState, Observation, TrafficObservation

from .config import BASELINE_SAMPLES, BaselineSettings
from .statistics import mean, sample_variance, select_threshold

__all__ = [
    "RULE_R01",
    "AlertStore",
    "BaselineState",
    "BaselineStore",
    "Clock",
    "Condition",
    "ConditionService",
    "SystemClock",
    "TrafficWindow",
    "alert_id_for",
    "condition_id_for",
    "metric_key_for",
]

#: Namespace determinista para condition_id/alert_id (patrón U5 window_id).
_CONDITION_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "sentinel.baseline.condition")

RULE_R01: Literal["R-01"] = "R-01"

_log = get_logger("baseline.conditions")


# --- identidad (BR-U6-17) ---------------------------------------------------


def condition_id_for(metric_key: str) -> str:
    """``condition_id`` estable por condición: uuid5("R-01|" + metric_key)."""
    return str(uuid.uuid5(_CONDITION_NAMESPACE, f"R-01|{metric_key}"))


def alert_id_for(condition_id: str, fired_at: str) -> str:
    """``alert_id`` por activación: uuid5(condition_id + "|" + fired_at)."""
    return str(uuid.uuid5(_CONDITION_NAMESPACE, f"{condition_id}|{fired_at}"))


def metric_key_for(metric: str, interface: str, protocol: str) -> str:
    """``<metric>|<interface>|<protocol>`` (FD §3.2)."""
    return f"{metric}|{interface}|{protocol}"


# --- Protocol de frontera (duck-typing, Q1 FD) ------------------------------


class BaselineStore(Protocol):
    def list(self) -> list[dict[str, Any]]: ...

    def upsert(self, baseline: dict[str, Any]) -> None: ...


class AlertStore(Protocol):
    def upsert(self, alert: dict[str, Any]) -> None: ...

    def list_firing(self) -> list[dict[str, Any]]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    """Reloj de pared UTC (la inyecta ``create_app``; tests usan FakeClock)."""

    def now(self) -> datetime:
        return datetime.now(UTC)


# --- dominio (slotted, sin Pydantic en el hot path — P5/P6) -----------------


@dataclass(slots=True)
class BaselineState:
    """Estado en memoria de una serie (FD §1.2)."""

    metric_key: str
    interval_seconds: int
    samples: list[float] = field(default_factory=list)
    mean: float = 0.0
    variance: float = 0.0
    established: bool = False
    t_first: datetime | None = None


@dataclass(slots=True)
class TrafficWindow:
    """Ventana de tráfico derivada de una ``TrafficObservation`` (FD §1.4)."""

    window_start: datetime
    window_end: datetime
    interface: str
    protocol: str
    bytes_per_second: float
    packets: int
    flows: int
    sensor_id: str


@dataclass(slots=True)
class Condition:
    """Resultado de ``evaluate`` (FD §1.5)."""

    rule: Literal["R-01"]
    metric_key: str
    state: ConditionState
    measured_value: float | None
    threshold: float | None
    suppressed: bool
    interface: str
    protocol: str
    sensor_id: str
    window_start: datetime | None


# --- servicio ---------------------------------------------------------------


class ConditionService:
    """Evaluador determinista R-01 con supresión de establecimiento (C5)."""

    def __init__(
        self,
        *,
        baselines: BaselineStore,
        alerts: AlertStore,
        settings: BaselineSettings,
        clock: Clock | None = None,
    ) -> None:
        self._baselines = baselines
        self._alerts = alerts
        self._settings = settings
        self._clock: Clock = clock if clock is not None else SystemClock()
        self._states: dict[str, BaselineState] = {}
        self._active: dict[str, dict[str, Any]] = {}  # condition_id → fila firing
        self._last_traffic_seen: datetime | None = None

    # --- propiedades de test/inspección ------------------------------------

    @property
    def states(self) -> Mapping[str, BaselineState]:
        return dict(self._states)

    @property
    def active_alerts(self) -> Mapping[str, dict[str, Any]]:
        return dict(self._active)

    # --- hidratación (FD §3.6; el wiring la envuelve en try — P2) ----------

    def hydrate(self) -> None:
        """Carga ``baselines``/``alerts`` desde los stores.

        Puede lanzar (fallo de BD): el llamador (``build_condition_service``)
        lo convierte en ``baseline_hydration_failed`` + servicio vacío.
        Baseline parcial ⇒ ``t_first = now`` (re-supresión conservadora,
        BR-U6-13); establecida ⇒ continúa sin supresión.
        """
        for row in self._baselines.list():
            raw = row.get("samples") or []
            if isinstance(raw, str):
                raw = json.loads(raw) if raw.strip() else []
            state = BaselineState(
                metric_key=str(row["metric_key"]),
                interval_seconds=int(
                    row.get("interval_seconds") or self._settings.interval_seconds
                ),
                samples=[float(x) for x in raw],
                mean=float(row.get("mean") or 0.0),
                variance=float(row.get("variance") or 0.0),
                established=bool(row.get("established")),
            )
            if not state.established and state.samples:
                state.t_first = self._clock.now()
            self._states[state.metric_key] = state
        for row in self._alerts.list_firing():
            self._active[str(row["condition_id"])] = dict(row)

    # --- estadística de serie (FR-BASE-01/02, P6) --------------------------

    def update_baseline(self, metric_key: str, sample: float, now: datetime) -> BaselineState:
        """Acumula una muestra; congelada a ``BASELINE_SAMPLES`` (no-op después)."""
        state = self._states.get(metric_key)
        if state is None:
            state = BaselineState(
                metric_key=metric_key,
                interval_seconds=self._settings.interval_seconds,
            )
            self._states[metric_key] = state
        if state.established:
            return state  # congelada (Q6 FD): sin recálculo ni append
        if state.t_first is None:
            state.t_first = now
        state.samples.append(float(sample))
        state.mean = mean(state.samples)
        state.variance = sample_variance(state.samples)
        if len(state.samples) >= BASELINE_SAMPLES:
            state.established = True
            _log.info(
                "baseline established",
                extra={
                    "event": "baseline_established",
                    "metric_key": metric_key,
                    "n": len(state.samples),
                    "mu": state.mean,
                    "sigma": math.sqrt(state.variance),
                },
            )
        return state

    # --- supresión y evaluación (FD §3.4) ----------------------------------

    def is_suppressed(self, metric_key: str, now: datetime) -> bool:
        """Ventana ``t_first + N·interval`` — prioridad sobre el umbral (Q7 FD)."""
        state = self._states.get(metric_key)
        if state is None or state.t_first is None:
            return False
        window = timedelta(seconds=BASELINE_SAMPLES * state.interval_seconds)
        return now < state.t_first + window

    def evaluate(self, window: TrafficWindow) -> Condition:
        """Evalúa R-01 (solo ``bytes_per_second``) contra el umbral efectivo."""
        now = self._clock.now()
        metric_key = metric_key_for("bytes_per_second", window.interface, window.protocol)
        base = Condition(
            rule=RULE_R01,
            metric_key=metric_key,
            state="no_data",
            measured_value=float(window.bytes_per_second),
            threshold=None,
            suppressed=False,
            interface=window.interface,
            protocol=window.protocol,
            sensor_id=window.sensor_id,
            window_start=window.window_start,
        )
        state = self._states.get(metric_key)
        if state is None:
            return base
        if self.is_suppressed(metric_key, now):
            # Supresión prioritaria (aunque el absoluto se supere — Q7 FD).
            return Condition(
                rule=RULE_R01,
                metric_key=metric_key,
                state="baseline_establishing",
                measured_value=base.measured_value,
                threshold=None,
                suppressed=True,
                interface=window.interface,
                protocol=window.protocol,
                sensor_id=window.sensor_id,
                window_start=window.window_start,
            )
        threshold = select_threshold(
            state.mean,
            math.sqrt(state.variance),
            self._settings.k,
            self._settings.absolute_bps,
            established=state.established,
        )
        if threshold is None:
            return base  # sin umbral disponible ⇒ no_data
        measured = float(window.bytes_per_second)
        fired = measured > threshold  # estricto (Q12 FD)
        return Condition(
            rule=RULE_R01,
            metric_key=metric_key,
            state="firing" if fired else "resolved",
            measured_value=measured,
            threshold=threshold,
            suppressed=False,
            interface=window.interface,
            protocol=window.protocol,
            sensor_id=window.sensor_id,
            window_start=window.window_start,
        )

    # --- hook push (FD §3.2, P1/P4) ----------------------------------------

    def on_accepted(self, observations: Sequence[Observation]) -> None:
        """Evaluación post-commit: jamás propaga excepciones (BR-U6-15)."""
        try:
            for obs in observations:
                if not isinstance(obs, TrafficObservation):
                    continue  # R-01 solo con series de tráfico
                now = self._clock.now()
                self._last_traffic_seen = now
                # ≤3 claves de ESTA observación (Q3 NFR-Design): O(1), sin re-fire ajeno.
                for metric, value in (
                    ("bytes_per_second", float(obs.bytes_per_second)),
                    ("packets", float(obs.packets)),
                    ("flows", float(obs.flows)),
                ):
                    key = metric_key_for(metric, obs.interface, str(obs.protocol))
                    self.update_baseline(key, value, now)
                    self._persist_baseline(key, now)
                condition = self.evaluate(
                    TrafficWindow(
                        window_start=obs.window_start,
                        window_end=obs.window_end,
                        interface=obs.interface,
                        protocol=str(obs.protocol),
                        bytes_per_second=float(obs.bytes_per_second),
                        packets=int(obs.packets),
                        flows=int(obs.flows),
                        sensor_id=obs.sensor_id,
                    )
                )
                self._apply_condition(condition, now)
        except Exception as exc:  # noqa: BLE001 — degradación total (P1)
            _log.error(
                "condition evaluation failed",
                extra={
                    "event": "condition_evaluation_failed",
                    "error": str(exc),
                },
            )

    # --- persistencia degradada (NFR-U6-AVAIL-01) --------------------------

    def _persist_baseline(self, metric_key: str, now: datetime) -> None:
        state = self._states[metric_key]
        row: dict[str, Any] = {
            "metric_key": metric_key,
            "interval_seconds": state.interval_seconds,
            "samples": list(state.samples),
            "mean": state.mean,
            "variance": state.variance,
            "established": state.established,
            "updated_at": now.isoformat(),
        }
        try:
            self._baselines.upsert(row)
        except Exception as exc:  # noqa: BLE001 — P1: log + reintento futuro
            _log.warning(
                "baseline persistence failed",
                extra={
                    "event": "condition_persistence_failed",
                    "metric_key": metric_key,
                    "error": str(exc),
                },
            )

    def _apply_condition(self, condition: Condition, now: datetime) -> None:
        """Transiciones firing/resolved → fila de alerta (BR-U6-17)."""
        if condition.state not in {"firing", "resolved"}:
            return  # establishing/no_data ⇒ métrica 0, sin alerta
        condition_id = condition_id_for(condition.metric_key)
        active = self._active.get(condition_id)
        if condition.state == "firing":
            fired_at = str(active["fired_at"]) if active else now.isoformat()
            row: dict[str, Any] = {
                "alert_id": alert_id_for(condition_id, fired_at),
                "condition_id": condition_id,
                "rule": RULE_R01,
                "metric_key": condition.metric_key,
                "asset_id": None,
                "state": "firing",
                "measured_value": condition.measured_value,
                "threshold": condition.threshold,
                "fired_at": fired_at,
                "resolved_at": None,
                "evidence": self._evidence(condition),
                "updated_at": now.isoformat(),
            }
            try:
                self._alerts.upsert(row)
            except Exception as exc:  # noqa: BLE001 — P1
                _log.warning(
                    "alert persistence failed",
                    extra={
                        "event": "condition_persistence_failed",
                        "condition_id": condition_id,
                        "error": str(exc),
                    },
                )
                return
            self._active[condition_id] = row
            if active is None:
                _log.info(
                    "condition firing",
                    extra={
                        "event": "condition_firing",
                        "metric_key": condition.metric_key,
                        "measured_value": condition.measured_value,
                        "threshold": condition.threshold,
                    },
                )
            return
        # resolved: solo actualiza la fila vigente; sin fila previa ⇒ nada.
        if active is None:
            return
        resolved = dict(active)
        resolved["state"] = "resolved"
        resolved["measured_value"] = condition.measured_value
        resolved["threshold"] = condition.threshold
        resolved["resolved_at"] = now.isoformat()
        resolved["updated_at"] = now.isoformat()
        try:
            self._alerts.upsert(resolved)
        except Exception as exc:  # noqa: BLE001 — P1
            _log.warning(
                "alert persistence failed",
                extra={
                    "event": "condition_persistence_failed",
                    "condition_id": condition_id,
                    "error": str(exc),
                },
            )
            return
        del self._active[condition_id]
        _log.info(
            "condition resolved",
            extra={
                "event": "condition_resolved",
                "metric_key": condition.metric_key,
                "measured_value": condition.measured_value,
                "threshold": condition.threshold,
            },
        )

    def _evidence(self, condition: Condition) -> dict[str, str | int | float]:
        state = self._states.get(condition.metric_key)
        return {
            "measured_value": float(condition.measured_value or 0.0),
            "threshold": float(condition.threshold or 0.0),
            "k": float(self._settings.k),
            "mu": float(state.mean) if state else 0.0,
            "sigma": float(math.sqrt(state.variance)) if state else 0.0,
            "window_start": condition.window_start.isoformat() if condition.window_start else "",
            "interface": condition.interface,
            "protocol": condition.protocol,
            "sensor_id": condition.sensor_id,
        }

    # --- indicadores (FD §3.5, R-04) ---------------------------------------

    def collector_up(self, traffic_last_seen: datetime | None) -> int:
        """``1`` si el heartbeat del sensor está fresco, ``0`` si no/None."""
        if traffic_last_seen is None:
            return 0
        age = (self._clock.now() - traffic_last_seen).total_seconds()
        return 1 if age <= self._settings.collector_timeout_seconds else 0

    def metric_samples(self) -> list[tuple[str, dict[str, str], float]]:
        """Proyección para U7 (bajo demanda, sin caché — Q7 NFR-Design)."""
        from .indicators import metric_samples as project

        return project(
            self._states.values(),
            self._active,
            collector_up=self.collector_up(self._last_traffic_seen),
        )
