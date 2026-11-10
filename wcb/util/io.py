"""File IO helpers with stable, diff-friendly output."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

import yaml


def read_json(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, data: Any, *, sort_keys: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=sort_keys)
        f.write("\n")


def iter_jsonl(path: str | Path) -> Iterator[dict]:
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:  # pragma: no cover - error path
                raise ValueError(f"{path}:{lineno}: invalid JSON: {e}") from e


def read_jsonl(path: str | Path) -> list[dict]:
    return list(iter_jsonl(path))


def write_jsonl(path: str | Path, rows: Iterable[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def read_yaml(path: str | Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)


def write_yaml(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
