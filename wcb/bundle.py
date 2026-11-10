"""`wcb bundle`: pack a scored run into one archive for reporting results.

The archive holds what a reader needs to check a self-reported result: run.json, the score
report, the adapter file, every session's session.json and usage.json, and the answers. Logs,
agent transcripts and store snapshots are left out unless asked for, because they are large and
logs can contain environment details. MANIFEST.json lists every file with its SHA-256.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from wcb import __version__
from wcb.util.io import read_json

_SESSION_FILES = ("session.json", "usage.json")
_LOG_SUFFIXES = (".log", ".jsonl", ".md")


def bundle_run(
    run_dir: Path, out: Path, *, logs: bool = False, snapshots: bool = False
) -> dict:
    """Write `out` (a .tar.gz) from `run_dir` and return its manifest."""
    run_dir = Path(run_dir).resolve()
    run_json = run_dir / "run.json"
    if not run_json.is_file():
        raise FileNotFoundError(f"{run_dir} has no run.json; is it a run directory from wcb run?")
    report = run_dir / "scores" / "report.json"
    if not report.is_file():
        raise FileNotFoundError(f"{run_dir} has not been scored; run: wcb score {run_dir}")
    meta = read_json(run_json)
    files: dict[str, Path] = {"run.json": run_json}
    for name in ("report.json", "report.md"):
        if (run_dir / "scores" / name).is_file():
            files[f"scores/{name}"] = run_dir / "scores" / name

    notes: list[str] = []
    ad = meta.get("adapter") or {}
    ad_path = Path(ad.get("path", ""))
    if ad_path.is_file():
        if hashlib.sha256(ad_path.read_bytes()).hexdigest() == ad.get("sha256"):
            files[f"adapter/{ad_path.name}"] = ad_path
        else:
            notes.append(f"adapter file {ad_path} changed since the run; not included")
    else:
        notes.append("adapter file not found; not included")

    for ep in sorted(p for p in run_dir.glob("*/r*") if p.is_dir()):
        rel = ep.relative_to(run_dir)
        for f in sorted((ep / "answers").glob("*.json")):
            files[f"{rel}/answers/{f.name}"] = f
        for sd in sorted(p for p in (ep / "sessions").glob("*") if p.is_dir()):
            for f in sorted(sd.iterdir()):
                if not f.is_file():
                    continue
                keep = f.name in _SESSION_FILES or (
                    logs and f.suffix in _LOG_SUFFIXES and f.name != "prompt.md"
                )
                if keep:
                    files[f"{rel}/sessions/{sd.name}/{f.name}"] = f
        if snapshots and (ep / "snapshots").is_dir():
            for f in _regular_files(ep / "snapshots"):
                if ".git" in f.relative_to(ep / "snapshots").parts:
                    continue
                files[f"{rel}/snapshots/{f.relative_to(ep / 'snapshots')}"] = f

    manifest = {
        "wcb_version": __version__,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "adapter": {k: ad.get(k) for k in ("name", "version", "model", "sha256")},
        "track": meta.get("track"),
        "worlds": [w.get("id") for w in meta.get("worlds", [])],
        "headline": _headline(read_json(report)),
        "includes": {"logs": logs, "snapshots": snapshots},
        "notes": notes,
        "files": {
            name: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size}
            for name, p in sorted(files.items())
        },
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    top = out.name.removesuffix(".tar.gz").removesuffix(".tgz") or "wcb-results"
    with tarfile.open(out, "w:gz") as tar:
        data = (json.dumps(manifest, indent=2) + "\n").encode()
        info = tarfile.TarInfo(f"{top}/MANIFEST.json")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        for name, p in sorted(files.items()):
            tar.add(p, arcname=f"{top}/{name}", recursive=False)
    return manifest


def _regular_files(root: Path) -> list[Path]:
    """Regular files under `root`, without following symbolic links (an agent's store may
    contain links to files elsewhere on the machine)."""
    out = []
    for dirpath, _dirs, names in os.walk(root):  # does not descend into linked directories
        for n in names:
            p = Path(dirpath) / n
            if not p.is_symlink() and p.is_file():
                out.append(p)
    return sorted(out)


def _headline(report: dict) -> dict:
    """The headline block of report.json, plus the judge used."""
    return {"judge": report.get("judge"), **(report.get("headline") or {})}
