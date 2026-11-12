"""Run both tracks in independent world shards; retain shards and assemble untouched outputs."""

import concurrent.futures
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "runs/pi-deepseek-v41-flash-1017"
CONFIG = Path(__file__).resolve().parent
WCB = ROOT / ".venv/bin/wcb"
WORLDS = [
    "dev/gen-s8-w4",
    "dev/gen-s4-w2",
    "dev/gen-s7-w2",
    "dev/gen-s10-w2-small",
    "pilot",
    "dev/gen-s9-large",
    "dev/gen-s1-w1",
    "dev/gen-s2-w1",
    "dev/gen-s3-w1",
    "dev/gen-s5-small",
    "dev/gen-s6-w1",
]
WORKERS = 8


def now():
    return datetime.now(timezone.utc).isoformat()


def run_world(track, world):
    name = world.split("/")[-1]
    shard = BASE / f"track-{track.lower()}" / "shards" / name
    shard.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(WCB),
        "run",
        "--adapter",
        str(CONFIG / "adapter.yaml"),
        "--world",
        world,
        "--track",
        track,
        "--repeats",
        "1",
        "--meter",
        "--no-build",
        "--out",
        str(shard),
    ]
    if track == "A":
        cmd.append("--oracle")
    print(f"{now()} START {track} {world}", flush=True)
    with shard.with_suffix(".log").open("w") as log:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            env=dict(os.environ, OPENAI_BASE_URL="https://api.tokenfactory.nebius.com/v1"),
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    outcome = dict(track=track, world=world, returncode=p.returncode, finished_at=now())
    with (BASE / "outcomes.jsonl").open("a") as f:
        f.write(json.dumps(outcome) + "\n")
    print(f"{now()} FINISH {track} {world}: {p.returncode}", flush=True)
    return outcome


def assemble(track):
    base = BASE / f"track-{track.lower()}"
    combined = base / "measured"
    combined.mkdir()
    metas = []
    for world in WORLDS:
        name = world.split("/")[-1]
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
        aggregation=dict(
            method="Independent world shards; copied without modifying outputs",
            workers=WORKERS,
            assembled_at=now(),
        ),
    )
    (combined / "run.json").write_text(json.dumps(meta, indent=2) + "\n")
    with (combined / "meter.jsonl").open("wb") as out:
        for world in WORLDS:
            source = base / "shards" / world.split("/")[-1] / "meter.jsonl"
            with source.open("rb") as f:
                shutil.copyfileobj(f, out)
    with (base / "score.log").open("w") as log:
        subprocess.run(
            [str(WCB), "score", str(combined)],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
        )
    print(f"{now()} SCORED {track}", flush=True)


def main():
    if (BASE / "started.json").exists():
        raise RuntimeError("Refusing to overwrite or replay measured work")
    BASE.mkdir(parents=True, exist_ok=True)
    (BASE / "started.json").write_text(
        json.dumps(
            dict(
                started_at=now(),
                workers=WORKERS,
                benchmark_revision=subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
            ),
            indent=2,
        )
        + "\n"
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
        jobs = [pool.submit(run_world, track, world) for world in WORLDS for track in ("A", "B")]
        outcomes = [f.result() for f in concurrent.futures.as_completed(jobs)]
    failed = [o for o in outcomes if o["returncode"]]
    if failed:
        (BASE / "infrastructure-failures.json").write_text(json.dumps(failed, indent=2) + "\n")
        raise RuntimeError(f"Infrastructure failures; retained all shards: {failed}")
    for track in ("A", "B"):
        assemble(track)
    (BASE / "completed.json").write_text(
        json.dumps(dict(finished_at=now(), outcomes=outcomes), indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
