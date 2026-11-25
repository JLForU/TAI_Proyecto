"""Entrypoint del Core: ``python -m sentinel.core`` ⇒ uvicorn 0.0.0.0:8080.

Imágenes: ``docker run --rm sentinel python -m sentinel.core`` (Dockerfile U1).
1 worker (TS-U2-01/Q3): SQLite + ``write_lock`` en proceso.
"""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run(
        "sentinel.core.api.app:app",
        host="0.0.0.0",
        port=8080,
        workers=1,
    )


if __name__ == "__main__":
    main()
