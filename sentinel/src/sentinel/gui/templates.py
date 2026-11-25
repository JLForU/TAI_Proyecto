"""Entorno Jinja de la GUI: único por proceso, ``auto_reload=False`` (P3).

Los templates van baked en la imagen (TECH-03): solo cambian con redeploy,
así que la compilación se cachea desde el primer render (Q3=NFR=A).
"""

from __future__ import annotations

from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

__all__ = ["TEMPLATES_DIR", "get_templates"]

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_templates: Jinja2Templates | None = None


def get_templates() -> Jinja2Templates:
    """Singleton por proceso (los tests comparten el entorno)."""
    global _templates
    if _templates is None:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=True,
            auto_reload=False,
        )
        _templates = Jinja2Templates(env=env)
    return _templates
