"""Servidor HTTP de métricas en 9108 (FR-CORE-02, P7, IP7).

ThreadingHTTPServer en hilo daemon; ``GET /metrics`` responde el render de
``collect()``. Puerto fijo 9108 en producción; los tests usan puerto efímero
(``port=0``). U7 sustituye el ``collect`` sin tocar este servidor.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sentinel.foundation.logging import get_logger

from .collect import Sample, render_prometheus
from .collect import collect as default_collect

__all__ = ["MetricsServer"]

_log = get_logger("core.metrics")

METRICS_PORT = 9108


class _Handler(BaseHTTPRequestHandler):
    server_version = "sentinel-core/2.0"

    def do_GET(self) -> None:  # noqa: N802 - API de BaseHTTPRequestHandler
        if self.path.split("?")[0] not in {"/metrics", "/"}:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"not found\n")
            return
        try:
            body = self.server.render().encode()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - un scrape no debe tumbar el proceso
            _log.error("metrics render failed", extra={"event": "metrics_error"}, exc_info=True)
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: Any) -> None:  # silencia el log por defecto
        return


class MetricsServer:
    """``GET /metrics`` en un hilo daemon."""

    def __init__(
        self,
        *,
        port: int = METRICS_PORT,
        host: str = "0.0.0.0",
        collect_fn: Callable[[], list[Sample]] | None = None,
    ) -> None:
        self._collect_fn = collect_fn or default_collect
        self._httpd = ThreadingHTTPServer((host, port), _Handler)
        self._httpd.render = self._render  # type: ignore[attr-defined]
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        return int(self._httpd.server_address[1])

    def _render(self) -> str:
        return render_prometheus(self._collect_fn())

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._httpd.serve_forever,
            kwargs={"poll_interval": 0.2},
            name="sentinel-metrics",
            daemon=True,
        )
        self._thread.start()
        _log.info(
            "metrics server started",
            extra={"event": "metrics_started", "port": self.port},
        )

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
