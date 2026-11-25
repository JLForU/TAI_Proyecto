"""Checks de estáticos y reglas de negocio estructurales (BR-U3-27..30, NFR-OPS-04)."""

from __future__ import annotations

import re
from pathlib import Path

GUI_DIR = Path(__file__).resolve().parents[3] / "src" / "sentinel" / "gui"


def test_static_assets_vendored_present() -> None:
    static = GUI_DIR / "static"
    for rel in (
        "js/htmx.min.js",
        "js/discovery.js",
        "css/tailwind.min.css",
        "css/daisyui.min.css",
        "css/styles.css",
        "favicon.svg",
    ):
        path = static / rel
        assert path.is_file(), f"missing static asset: {rel}"
        assert path.stat().st_size > 0


def test_templates_have_no_cdn_scripts() -> None:
    templates = GUI_DIR / "templates"
    assert templates.is_dir()
    for tpl in templates.glob("*.html"):
        text = tpl.read_text(encoding="utf-8")
        # BR-U3-27: sin CDN, sin SPA build
        assert 'src="http' not in text, f"CDN script in {tpl.name}"
        assert "cdn." not in text, f"cdn reference in {tpl.name}"
        assert "unpkg.com" not in text and "jsdelivr" not in text


def test_base_layout_links_local_static() -> None:
    base = (GUI_DIR / "templates" / "base.html").read_text(encoding="utf-8")
    assert "/static/css/tailwind.min.css" in base
    assert "/static/js/htmx.min.js" in base
    assert 'href="/ui/assets"' in base


def test_discovery_js_backoff_constants() -> None:
    js = (GUI_DIR / "static" / "js" / "discovery.js").read_text(encoding="utf-8")
    # P1: backoff 2→16 s con parada a los 5 fallos
    assert "2" in js and "16" in js
    assert re.search(r"(MAX_FAILURES|FAILURES)\s*=\s*5", js)
    assert "setTimeout" in js


def test_gui_does_not_import_core_persistence() -> None:
    """BR-U3-29: cero imports de core.db/repos/servicios de U2 en gui/."""
    import ast

    forbidden = (
        "sentinel.core.db",
        "sentinel.core.repos",
        "sentinel.core.query",
        "sentinel.core.export",
        "sentinel.core.ingestion",
        "sentinel.core.health",
        "sentinel.core.discovery",
    )
    for py in GUI_DIR.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                for needle in forbidden:
                    assert not name.startswith(needle), f"{py.name} imports {needle}"


def test_gui_has_no_new_env_keys() -> None:
    """BR-U3-30: sin claves SENTINEL_* nuevas ni loader de config en gui/."""
    for py in GUI_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "SENTINEL_" not in text, f"{py.name} references SENTINEL_ env"
        assert "load_core_settings" not in text, f"{py.name} loads config"
        assert "os.environ" not in text and "getenv" not in text


def test_requirements_pins_ui_stack() -> None:
    root = GUI_DIR.parents[2]
    reqs = (root / "requirements.txt").read_text(encoding="utf-8").lower()
    for pkg in ("jinja2", "markdown", "weasyprint", "httpx", "python-multipart"):
        assert pkg in reqs, f"{pkg} missing in requirements.txt"


def test_api_base_is_constant_loopback() -> None:
    client_src = (GUI_DIR / "client.py").read_text(encoding="utf-8")
    assert 'API_BASE = "http://127.0.0.1:8080"' in client_src


def test_jinja_env_auto_reload_false_and_singleton() -> None:
    """P3: ``auto_reload=False`` y Environment idéntico entre renders."""
    from sentinel.gui.templates import get_templates

    t1 = get_templates()
    t2 = get_templates()
    assert t1 is t2  # singleton por proceso
    env = t1.env
    assert env.auto_reload is False
    assert env.autoescape is True
    assert get_templates().env is env
