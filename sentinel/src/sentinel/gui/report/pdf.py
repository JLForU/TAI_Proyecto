"""Renderizado MD → PDF con WeasyPrint (BR-U3-24, P5).

Camino: Markdown (ya escapado con ``esc()`` en los builders) → HTML vía la
lib ``markdown`` → template Jinja con autoescape ON → WeasyPrint → bytes.
Import de ``weasyprint`` **perezoso**: ``format=md`` no lo necesita
(mismo criterio que TS-U3-02/03).
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["render_pdf", "render_html"]

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "report_pdf.html"


def render_html(markdown_text: str) -> str:
    """MD → fragmento HTML → página intermedia con autoescape ON (P5)."""
    import markdown as md_lib  # type: ignore[import-untyped]

    from ..templates import get_templates

    fragment = md_lib.markdown(markdown_text, extensions=["tables", "fenced_code"])
    template = get_templates().get_template("report_pdf.html")
    return template.render(body=fragment)


def render_pdf(markdown_text: bytes | str) -> bytes:
    """MD → HTML → WeasyPrint → ``application/pdf`` bytes (BR-U3-24)."""
    from weasyprint import HTML  # type: ignore[import-untyped]

    text = markdown_text.decode("utf-8") if isinstance(markdown_text, bytes) else markdown_text
    html = render_html(text)
    return HTML(string=html, base_url=str(_TEMPLATE_PATH.parent)).write_pdf()
