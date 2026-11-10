"""Parse and write Markdown files with YAML front matter.

A record file looks like::

    ---
    id: people/marisol-teague
    type: person
    ---
    Body text...
"""

from __future__ import annotations

from typing import Any

import yaml

DELIM = "---"


class FrontMatterError(ValueError):
    pass


def split(text: str) -> tuple[str | None, str]:
    """Return (yaml_text, body). yaml_text is None when the file has no front matter."""
    if text.startswith("﻿"):
        text = text[1:]
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != DELIM:
        return None, text
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == DELIM:
            return "".join(lines[1:i]), "".join(lines[i + 1 :])
    raise FrontMatterError("front matter opened with '---' but never closed")


def parse(text: str) -> tuple[dict[str, Any] | None, str]:
    """Return (metadata, body). metadata is None when the file has no front matter."""
    raw, body = split(text)
    if raw is None:
        return None, body
    try:
        meta = yaml.safe_load(raw) if raw.strip() else {}
    except (yaml.YAMLError, ValueError) as e:  # ValueError: impossible dates such as 2027-02-30
        raise FrontMatterError(f"invalid YAML front matter: {e}") from e
    if meta is None:
        meta = {}
    if not isinstance(meta, dict):
        raise FrontMatterError("front matter must be a YAML mapping")
    return _stringify_dates(meta), body


def dump(meta: dict[str, Any], body: str) -> str:
    y = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=100).rstrip("\n")
    body = body if body.startswith("\n") else "\n" + body
    if not body.endswith("\n"):
        body += "\n"
    return f"{DELIM}\n{y}\n{DELIM}{body}"


def _stringify_dates(obj: Any) -> Any:
    """YAML parses bare 2027-03-01 as a date; normalize to ISO strings."""
    import datetime as _dt

    if isinstance(obj, dict):
        return {k: _stringify_dates(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify_dates(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj
