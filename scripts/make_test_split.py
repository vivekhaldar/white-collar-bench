#!/usr/bin/env python3
"""Generate a private test split for a leaderboard release, with published commitments.

Maintainers only. Test worlds are generated from secret seeds and kept outside the public
repository (or in worlds/test/, which is git-ignored). The script writes:

  <out>/<world-id>/            generated, built worlds (inputs, hidden truth, gold)
  <out>/SEEDS.private.json     seeds and salts: keep secret until the release is retired
  <out>/commitments.json       publish this with the release: per world, its generation
                               parameters (without the seed), a salted hash of the seed and the
                               SHA-256 of world.jsonl and questions.yaml

After the release is retired, publishing SEEDS.private.json lets anyone regenerate the worlds
and check them against the commitments (`--verify`), which shows the test worlds were fixed
before submissions were scored.

Examples:
  python scripts/make_test_split.py --release 2027.1 --out ~/wcb-private/test-2027.1
  python scripts/make_test_split.py --release 2027.1 --out worlds/test --mix 1w:3,2w:1,4w:1
  python scripts/make_test_split.py --verify ~/wcb-private/test-2027.1
  wcb run --adapter submission.yaml --split ~/wcb-private/test-2027.1 --repeats 3 --out runs/x
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from pathlib import Path

DEFAULT_MIX = "1w:4,2w:1,small:1"
# Mix entries: <weeks>w (standard size) or small/large (1 week), each with a count.
KINDS = {
    "1w": {"weeks": 1, "size": "standard"},
    "2w": {"weeks": 2, "size": "standard"},
    "4w": {"weeks": 4, "size": "standard"},
    "small": {"weeks": 1, "size": "small"},
    "large": {"weeks": 1, "size": "large"},
}


def parse_mix(text: str) -> list[dict]:
    out = []
    for part in text.split(","):
        kind, _, n = part.strip().partition(":")
        if kind not in KINDS or not n.isdigit():
            raise SystemExit(f"bad --mix entry {part!r}; use e.g. {DEFAULT_MIX} (kinds: {', '.join(KINDS)})")
        out += [dict(KINDS[kind]) for _ in range(int(n))]
    return out


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def seed_commitment(seed: int, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{seed}".encode()).hexdigest()


def generate(spec: dict, out: Path) -> dict:
    from wcb.world.generate import generate_world

    d = generate_world(
        seed=spec["seed"], weeks=spec["weeks"], size=spec["size"], world_id=spec["id"],
        out_dir=out / spec["id"], build=True,
    )
    return {
        "id": spec["id"],
        "weeks": spec["weeks"],
        "size": spec["size"],
        "seed_sha256": seed_commitment(spec["seed"], spec["salt"]),
        "world_jsonl_sha256": sha256_file(d / "world.jsonl"),
        "questions_yaml_sha256": sha256_file(d / "questions.yaml"),
    }


def make(args) -> int:
    from wcb import __version__

    out = Path(args.out).expanduser().resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} is not empty; choose a new directory")
    out.mkdir(parents=True, exist_ok=True)
    specs = []
    for i, kind in enumerate(parse_mix(args.mix), start=1):
        specs.append({
            "id": f"test-{args.release}-{i:02d}".replace(".", "-"),
            "seed": secrets.randbelow(2**31),
            "salt": secrets.token_hex(16),
            **kind,
        })
    worlds = []
    for spec in specs:
        print(f"generating {spec['id']} ({spec['size']}, {spec['weeks']} week(s))", file=sys.stderr)
        worlds.append(generate(spec, out))
    common = {"release": args.release, "wcb_version": __version__}
    (out / "SEEDS.private.json").write_text(
        json.dumps({**common, "worlds": specs}, indent=2) + "\n", encoding="utf-8"
    )
    (out / "commitments.json").write_text(
        json.dumps({**common, "worlds": worlds}, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(worlds)} world(s) to {out}")
    print(f"publish {out / 'commitments.json'}; keep {out / 'SEEDS.private.json'} secret")
    return 0


def verify(args) -> int:
    import tempfile

    src = Path(args.verify).expanduser().resolve()
    seeds = json.loads((src / "SEEDS.private.json").read_text(encoding="utf-8"))
    commitments = json.loads((src / "commitments.json").read_text(encoding="utf-8"))
    want = {w["id"]: w for w in commitments["worlds"]}
    bad = 0
    with tempfile.TemporaryDirectory(prefix="wcb-verify-") as tmp:
        for spec in seeds["worlds"]:
            got = generate(spec, Path(tmp))
            ok = got == want.get(spec["id"])
            bad += not ok
            print(f"{spec['id']}: {'ok' if ok else 'MISMATCH'}")
    if seeds.get("wcb_version") != commitments.get("wcb_version"):
        print("note: SEEDS and commitments name different wcb versions", file=sys.stderr)
    print(f"{len(seeds['worlds']) - bad} of {len(seeds['worlds'])} world(s) match their commitments")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--release", help="release label, e.g. 2027.1")
    p.add_argument("--out", help="output directory (new or empty)")
    p.add_argument("--mix", default=DEFAULT_MIX, help=f"world mix (default {DEFAULT_MIX})")
    p.add_argument("--verify", metavar="DIR", help="regenerate a split from its seeds and check it")
    args = p.parse_args(argv)
    if args.verify:
        return verify(args)
    if not (args.release and args.out):
        p.error("--release and --out are required (or use --verify DIR)")
    return make(args)


if __name__ == "__main__":
    sys.exit(main())
