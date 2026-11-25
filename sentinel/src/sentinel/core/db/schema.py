"""Esquema SQLite idempotente de U2 (OQ-02, BR-U2-20, P1 base).

DDL de las 7 tablas + índices según ``domain-entities.md`` §1.
Ejecutado en el arranque con ``CREATE TABLE IF NOT EXISTS`` (sin Alembic — TS-U2-03).
"""

from __future__ import annotations

import sqlite3

__all__ = ["DDL", "apply_schema"]

DDL = """
CREATE TABLE IF NOT EXISTS assets (
    asset_id      TEXT PRIMARY KEY,
    mac           TEXT,
    hostname      TEXT,
    os_name       TEXT,
    os_provenance TEXT NOT NULL DEFAULT 'unknown',
    status        TEXT NOT NULL,
    miss_count    INTEGER NOT NULL DEFAULT 0,
    first_seen    TEXT NOT NULL,
    last_seen     TEXT NOT NULL,
    source        TEXT NOT NULL,
    sensor_id     TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_status ON assets (status);
CREATE INDEX IF NOT EXISTS idx_assets_last_seen ON assets (last_seen);

CREATE TABLE IF NOT EXISTS asset_ips (
    ip         TEXT PRIMARY KEY,
    asset_id   TEXT NOT NULL REFERENCES assets (asset_id),
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_asset_ips_asset ON asset_ips (asset_id);

CREATE TABLE IF NOT EXISTS observations (
    dedup_key   TEXT PRIMARY KEY,
    asset_id    TEXT REFERENCES assets (asset_id),
    source      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    sensor_id   TEXT,
    observed_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    payload     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_obs_asset_time ON observations (asset_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_sensor ON observations (sensor_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_obs_source ON observations (source, observed_at);

CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    asset_id    TEXT REFERENCES assets (asset_id),
    severity    TEXT NOT NULL DEFAULT 'info',
    rule        TEXT,
    occurred_at TEXT NOT NULL,
    details     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events (occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_asset ON events (asset_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events (type, occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_rule ON events (rule);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id       TEXT PRIMARY KEY,
    condition_id   TEXT NOT NULL,
    rule           TEXT NOT NULL,
    metric_key     TEXT,
    asset_id       TEXT,
    state          TEXT NOT NULL,
    measured_value REAL,
    threshold      REAL,
    fired_at       TEXT NOT NULL,
    resolved_at    TEXT,
    evidence       TEXT,
    updated_at     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_state ON alerts (state, fired_at);
CREATE INDEX IF NOT EXISTS idx_alerts_asset ON alerts (asset_id, fired_at);

CREATE TABLE IF NOT EXISTS baselines (
    metric_key       TEXT PRIMARY KEY,
    interval_seconds INTEGER NOT NULL,
    samples          TEXT NOT NULL,
    mean             REAL,
    variance         REAL,
    established      INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discovery_runs (
    run_id          TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    "trigger"       TEXT NOT NULL,
    hosts_targeted  TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    hosts_seen      INTEGER,
    error           TEXT
);
CREATE INDEX IF NOT EXISTS idx_runs_status ON discovery_runs (status, started_at);
"""


def apply_schema(conn: sqlite3.Connection) -> None:
    """Aplica el DDL idempotente (BR-U2-20). Safe llamar en cada arranque."""
    conn.executescript(DDL)
