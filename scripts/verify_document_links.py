#!/usr/bin/env python3
"""Verify relative Markdown links and GitHub-style heading anchors."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$", re.MULTILINE)
CUSTOM_ANCHOR_RE = re.compile(r'<a\s+(?:name|id)=["\']([^"\']+)["\']', re.I)


def strip_code_fences(text: str) -> str:
    return re.sub(r"```.*?```|~~~.*?~~~", "", text, flags=re.S)


def heading_slug(title: str) -> str:
    """Approximate GitHub's documented heading-anchor behavior.

    Spaces become hyphens; punctuation/symbols are removed; letters are
    lowercased; existing ASCII hyphens and underscores are retained.
    Consecutive spaces remain consecutive hyphens, as on GitHub.
    """
    title = re.sub(r"`([^`]*)`", r"\1", title)
    title = re.sub(r"!?\[([^]]*)\]\([^)]*\)", r"\1", title)
    out: list[str] = []
    for char in title.lower():
        category = unicodedata.category(char)
        if char.isspace():
            out.append("-")
        elif char in "-_" or char.isalnum() or category.startswith("M"):
            out.append(char)
        elif category.startswith(("P", "S")):
            continue
        else:
            continue
    return "".join(out).strip("-")


def heading_ids(text: str) -> set[str]:
    ids: set[str] = set(CUSTOM_ANCHOR_RE.findall(text))
    counts: dict[str, int] = {}
    for heading in HEADING_RE.findall(text):
        base = heading_slug(heading)
        count = counts.get(base, 0)
        candidate = base if count == 0 else f"{base}-{count}"
        counts[base] = count + 1
        ids.add(candidate)
    return ids


def main() -> int:
    errors: list[str] = []
    checked = 0
    for source in sorted(ROOT.rglob("*.md")):
        raw = source.read_text(encoding="utf-8")
        text = strip_code_fences(raw)
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip().strip("<>")
            if target.startswith(("https://", "http://", "mailto:", "tel:")):
                continue
            path_part, separator, fragment = target.partition("#")
            destination = (source.parent / unquote(path_part)).resolve() if path_part else source.resolve()
            checked += 1
            if not destination.is_file():
                errors.append(f"{source.relative_to(ROOT)}: missing target {target}")
                continue
            if separator and fragment and destination.suffix.lower() == ".md":
                dest_text = destination.read_text(encoding="utf-8")
                if unquote(fragment) not in heading_ids(dest_text):
                    errors.append(f"{source.relative_to(ROOT)}: missing anchor {target}")

    if errors:
        for error in errors:
            print("ERROR:", error)
        print(f"FAILED: {len(errors)} broken links/anchors among {checked} local links")
        return 1
    print(f"OK: {checked} local Markdown links resolve; 0 broken files or anchors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
