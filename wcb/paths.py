"""Locate repository resources (contract files, worlds) in a source checkout or an installed wheel."""

from __future__ import annotations

from pathlib import Path

_PKG = Path(__file__).resolve().parent


def repo_root() -> Path | None:
    root = _PKG.parent
    return root if (root / "contract").is_dir() and (root / "pyproject.toml").exists() else None


def contract_dir() -> Path:
    """Directory holding CONTRACT.md, schemas/ and answers/."""
    root = repo_root()
    if root is not None:
        return root / "contract"
    return _PKG / "_contract"


def worlds_dir() -> Path:
    root = repo_root()
    if root is None:
        raise FileNotFoundError(
            "worlds/ is only available in a source checkout; pass an explicit world path"
        )
    return root / "worlds"


def resolve_world(spec: str) -> Path:
    """Accept a path to a world directory, or a name like 'pilot' or 'dev/w01'."""
    p = Path(spec)
    if (p / "world.yaml").exists():
        return p.resolve()
    cand = worlds_dir() / spec
    if (cand / "world.yaml").exists():
        return cand.resolve()
    raise FileNotFoundError(f"no world found at {spec!r} (expected a directory with world.yaml)")


def resolve_split(split: str) -> list[Path]:
    """All worlds in a split: a name under worlds/ ('dev' -> worlds/dev/*/world.yaml) or a path.

    A path lets maintainers keep a private test split outside the repository.
    """
    p = Path(split).expanduser()
    if p.is_dir() and ((p / "world.yaml").exists() or any(p.glob("*/world.yaml"))):
        d = p
    else:
        d = worlds_dir() / split
    if (d / "world.yaml").exists():
        return [d.resolve()]
    return sorted(p.parent.resolve() for p in d.glob("*/world.yaml"))
