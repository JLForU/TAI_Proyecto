"""Repositorio de activos + correlación IP→activo (Q5 FD, BR-U2-11/13..17/21)."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from ._common import iso_now

__all__ = ["AssetRepository"]


class AssetRepository:
    """CRUD de ``assets``/``asset_ips``; recibe la ``conn`` de la transacción."""

    def find_asset_id_by_ip(self, conn: sqlite3.Connection, ip: str) -> str | None:
        row = conn.execute("SELECT asset_id FROM asset_ips WHERE ip = ?", (ip,)).fetchone()
        return str(row["asset_id"]) if row else None

    def get(self, conn: sqlite3.Connection, asset_id: str) -> sqlite3.Row | None:
        return conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()

    def get_by_ip(self, conn: sqlite3.Connection, ip: str) -> sqlite3.Row | None:
        row = conn.execute("SELECT asset_id FROM asset_ips WHERE ip = ?", (ip,)).fetchone()
        if row is None:
            return None
        return self.get(conn, str(row["asset_id"]))

    def create(
        self,
        conn: sqlite3.Connection,
        *,
        ip: str,
        mac: str | None,
        hostname: str | None,
        os_name: str | None,
        os_provenance: str,
        source: str,
        sensor_id: str | None,
        now: str | None = None,
    ) -> str:
        """Crea activo + binding de IP; devuelve ``asset_id``."""
        ts = now or iso_now()
        asset_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO assets (asset_id, mac, hostname, os_name, os_provenance, status,"
            " miss_count, first_seen, last_seen, source, sensor_id)"
            " VALUES (?, ?, ?, ?, ?, 'present', 0, ?, ?, ?, ?)",
            (asset_id, mac, hostname, os_name, os_provenance, ts, ts, source, sensor_id),
        )
        conn.execute(
            "INSERT INTO asset_ips (ip, asset_id, first_seen, last_seen) VALUES (?, ?, ?, ?)",
            (ip, asset_id, ts, ts),
        )
        return asset_id

    def touch(
        self,
        conn: sqlite3.Connection,
        *,
        asset_id: str,
        ip: str,
        mac: str | None,
        hostname: str | None,
        os_name: str | None,
        now: str | None = None,
    ) -> bool:
        """Actualiza last_seen/status y detecta cambio de MAC.

        Devuelve ``True`` si la MAC cambió (BR-U2-17).
        """
        ts = now or iso_now()
        row = conn.execute("SELECT mac FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
        old_mac = row["mac"] if row else None
        mac_changed = bool(mac and old_mac and mac != old_mac)
        conn.execute(
            "UPDATE assets SET last_seen = ?, status = 'present', miss_count = 0,"
            " mac = COALESCE(?, mac), hostname = COALESCE(?, hostname),"
            " os_name = COALESCE(?, os_name)"
            " WHERE asset_id = ?",
            (ts, mac, hostname, os_name, asset_id),
        )
        conn.execute(
            "INSERT INTO asset_ips (ip, asset_id, first_seen, last_seen) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(ip) DO UPDATE SET last_seen = excluded.last_seen",
            (ip, asset_id, ts, ts),
        )
        return mac_changed

    def mark_absent(self, conn: sqlite3.Connection, asset_id: str) -> None:
        conn.execute(
            "UPDATE assets SET status = 'absent' WHERE asset_id = ? AND status = 'present'",
            (asset_id,),
        )

    def bump_miss(self, conn: sqlite3.Connection, asset_id: str) -> int:
        """Incrementa ``miss_count``; devuelve el nuevo valor."""
        conn.execute(
            "UPDATE assets SET miss_count = miss_count + 1 WHERE asset_id = ? AND status = 'present'",
            (asset_id,),
        )
        row = conn.execute(
            "SELECT miss_count FROM assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        return int(row["miss_count"]) if row else 0

    def present_assets(self, conn: sqlite3.Connection) -> list[sqlite3.Row]:
        return list(conn.execute("SELECT * FROM assets WHERE status = 'present'"))

    def ips_for_asset(self, conn: sqlite3.Connection, asset_id: str) -> list[str]:
        rows = conn.execute(
            "SELECT ip FROM asset_ips WHERE asset_id = ? ORDER BY ip", (asset_id,)
        ).fetchall()
        return [str(r["ip"]) for r in rows]

    def list(
        self,
        conn: sqlite3.Connection,
        *,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[sqlite3.Row], int]:
        where, params = ("", [])
        if status:
            where, params = " WHERE status = ?", [status]
        total = int(conn.execute(f"SELECT COUNT(*) FROM assets{where}", params).fetchone()[0])
        rows = list(
            conn.execute(
                f"SELECT * FROM assets{where} ORDER BY last_seen DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            )
        )
        return rows, total

    def count(self, conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT COUNT(*) FROM assets").fetchone()[0])

    def summary(self, conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
        """Fila → dict de ``AssetSummary`` (ips resueltas desde ``asset_ips``)."""
        return {
            "asset_id": row["asset_id"],
            "mac": row["mac"],
            "ips": self.ips_for_asset(conn, row["asset_id"]),
            "hostname": row["hostname"],
            "os_name": row["os_name"],
            "os_provenance": row["os_provenance"] or "unknown",
            "status": row["status"],
            "first_seen": row["first_seen"],
            "last_seen": row["last_seen"],
        }
