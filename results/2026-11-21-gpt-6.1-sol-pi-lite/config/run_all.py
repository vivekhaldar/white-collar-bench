"""Run the lite suite (Tracks A and B) for GPT-6.1 Sol (copied from the Claude 5.5 run; only the
model list, output directory and upstream variable differ), in independent world shards, then score.

Each shard is `wcb run --world W --max-days 2 --meter`, the per-world piece of
`wcb run --suite lite`. Shards are assembled into one run per model and track, recorded as a
lite-suite run, and scored as lite and as micro (micro is a subset of lite's worlds and days, so
its score comes from the same sessions). Refuses to overwrite earlier measured work.

    python results/2026-11-21-gpt-6.1-sol-pi-lite/config/run_all.py
"""

import concurrent.futures
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from wcb.suites import SUITES  # noqa: E402

BASE = ROOT / "runs/gpt-6.1-sol-pi-lite"
CONFIG = Path(__file__).resolve().parent
WCB = ROOT / ".venv/bin/wcb"
MODELS = ["sol"]
LITE = SUITES["lite"]
# Longest-running worlds first, so the slow ones do not start last.
ORDER = ["pilot", "gen-s9-large", "gen-s8-w4", "gen-s4-w2", "gen-s7-w2", "gen-s1-w1",
         "gen-s2-w1", "gen-s3-w1", "gen-s6-w1", "gen-s10-w2-small", "gen-s5-small"]  # fmt: skip
WORLDS = sorted(LITE.worlds, key=lambda w: ORDER.index(Path(w).name))
WORKERS = int(os.environ.get("WCB_WORKERS", "8"))
LITELLM = "https://brk-litellm.centralus.cloudapp.azure.com"


def now():
    return datetime.now(timezone.utc).isoformat()


def shard_dir(model, track, world):
    return BASE / model / f"track-{track.lower()}" / "shards" / Path(world).name


def run_world(model, track, world):
    shard = shard_dir(model, track, world)
    shard.parent.mkdir(parents=True, exist_ok=True)
    cmd = [str(WCB), "run", "--adapter", str(CONFIG / "adapter.yaml"), "--world", world,
           "--track", track, "--max-days", str(LITE.max_days), "--meter", "--no-build",
           "--out", str(shard)]  # fmt: skip
    print(f"{now()} START {model} {track} {world}", flush=True)
    with shard.with_suffix(".log").open("w") as log:
        p = subprocess.run(cmd, cwd=ROOT, env=dict(os.environ, OPENAI_BASE_URL=LITELLM),
                           stdout=log, stderr=subprocess.STDOUT)  # fmt: skip
    outcome = dict(model=model, track=track, world=world, returncode=p.returncode, finished_at=now())
    with (BASE / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(outcome) + "\n")
    print(f"{now()} FINISH {model} {track} {world}: {p.returncode}", flush=True)
    return outcome


def assemble(model, track):
    base = BASE / model / f"track-{track.lower()}"
    combined = base / "measured"
    combined.mkdir()
    metas = []
    for world in WORLDS:
        name = Path(world).name
        shard = base / "shards" / name
        meta = json.loads((shard / "run.json").read_text())
        if meta["status"] != "completed":
            raise RuntimeError(f"Incomplete shard: {shard}")
        metas.append(meta)
        shutil.copytree(shard / name, combined / name, symlinks=True)
    meta = dict(metas[0])
    meta.update(
        worlds=[w for m in metas for w in m["worlds"]],
        started_at=min(m["started_at"] for m in metas),
        finished_at=max(m["finished_at"] for m in metas),
        options={**meta["options"], "suite": LITE.name},
        aggregation=dict(method="Independent world shards (--world W --max-days 2); copied "
                         "without modifying outputs", workers=WORKERS, assembled_at=now()),
    )  # fmt: skip
    (combined / "run.json").write_text(json.dumps(meta, indent=2) + "\n")
    with (combined / "meter.jsonl").open("wb") as out:
        for world in WORLDS:
            with (base / "shards" / Path(world).name / "meter.jsonl").open("rb") as f:
                shutil.copyfileobj(f, out)
    for suite in ("lite", "micro"):
        with (base / f"score-{suite}.log").open("w") as log:
            subprocess.run([str(WCB), "score", str(combined), "--suite", suite,
                            "--out", str(base / f"scores-{suite}")],
                           cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)  # fmt: skip
    print(f"{now()} SCORED {model} {track}", flush=True)


def main():
    if (BASE / "started.json").exists():
        raise RuntimeError("Refusing to overwrite or replay measured work")
    BASE.mkdir(parents=True, exist_ok=True)
    rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    (BASE / "started.json").write_text(json.dumps(
        dict(started_at=now(), workers=WORKERS, benchmark_revision=rev), indent=2) + "\n")
    jobs = [(m, t, w) for w in WORLDS for t in ("B", "A") for m in MODELS]
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        outcomes = [f.result() for f in concurrent.futures.as_completed(
            [pool.submit(run_world, *j) for j in jobs])]  # fmt: skip
    failed = [o for o in outcomes if o["returncode"]]
    if failed:
        (BASE / "infrastructure-failures.json").write_text(json.dumps(failed, indent=2) + "\n")
        raise RuntimeError(f"Infrastructure failures; retained all shards: {failed}")
    for model in MODELS:
        for track in ("A", "B"):
            assemble(model, track)
    (BASE / "completed.json").write_text(
        json.dumps(dict(finished_at=now(), outcomes=outcomes), indent=2) + "\n")


if __name__ == "__main__":
    main()
