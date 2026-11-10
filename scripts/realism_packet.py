#!/usr/bin/env python3
"""Draw a realism-review packet: a random sample of input artifacts, one readable file to grade.

    python scripts/realism_packet.py --world pilot --world dev/gen-s1-w1 --per-channel 2 --out review/

Writes `<out>/packet.md` (each sampled artifact as the agent would read it, documents as
extracted text) and `<out>/scores.csv` (one row per artifact to fill in). Artifact IDs are
shown, but not whether a world is hand-authored or generated, so reviewers grade blind; the
mapping is in `<out>/key.json`. Grading guide (also in the packet):

    realism   1 = obviously synthetic ... 5 = indistinguishable from real work mail/chat/notes
    issues    free text: wrong tone, impossible timing, odd phrasing, repeated templates, etc.

Use it for the practitioner review before a release (docs/privacy.md, "Release gate").
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from email import policy
from email.parser import BytesParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.paths import resolve_world  # noqa: E402
from wcb.world.model import World  # noqa: E402

GUIDE = """For each artifact, give **realism** 1-5 and note any **issues**:

| Score | Meaning |
|---|---|
| 5 | Indistinguishable from real work communication |
| 4 | Real, with a small tell (a stock phrase, slightly too tidy) |
| 3 | Plausible but clearly templated or flat |
| 2 | Odd: wrong tone, strange phrasing, timing or roles that do not fit |
| 1 | Obviously synthetic or broken |

Useful issue tags: `tone`, `phrasing`, `template`, `timing`, `roles`, `too-tidy`, `too-thin`,
`inconsistent` (contradicts something else you read), `leak` (resembles a real person, org or event).
Record scores in `scores.csv` next to this file.
"""


def render(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".eml":
        msg = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
        head = "\n".join(f"{h}: {msg[h]}" for h in ("From", "To", "Cc", "Date", "Subject") if msg[h])
        body = msg.get_body(preferencelist=("plain",))
        return head + "\n\n" + (body.get_content() if body else "")
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        lines = [f"#{data.get('channel', '')} ({data.get('kind', '')})"]
        for m in data.get("messages", []):
            lines.append(f"[{m.get('ts', '')[11:16]}] {m.get('user', '')}: {m.get('text', '')}")
        return "\n".join(lines)
    if suffix in (".pdf", ".docx", ".xlsx", ".pptx"):
        from wcb.render.office import extract_text

        return "(document; extracted text)\n\n" + extract_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--world", action="append", required=True)
    ap.add_argument("--per-channel", type=int, default=2, help="artifacts per channel per world")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-chars", type=int, default=6000, help="truncate long artifacts")
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    picks = []
    for spec in a.world:
        w = World.load(resolve_world(spec))
        by_channel: dict[str, list] = {}
        for art in w.artifacts.values():
            if not getattr(art, "noise", False):
                by_channel.setdefault(art.channel, []).append(art)
        for channel, arts in sorted(by_channel.items()):
            arts = sorted(arts, key=lambda x: x.id)
            for art in rng.sample(arts, min(a.per_channel, len(arts))):
                picks.append((w, art))
    rng.shuffle(picks)
    a.out.mkdir(parents=True, exist_ok=True)
    parts = ["# Realism review packet\n", GUIDE]
    key = {}
    for n, (w, art) in enumerate(picks, 1):
        label = f"R{n:02d}"
        key[label] = {"world": w.id, "artifact": art.id, "path": art.path}
        text = render(w.dir / art.path)
        if len(text) > a.max_chars:
            text = text[: a.max_chars] + "\n[... truncated ...]"
        parts.append(f"\n---\n\n## {label} · {art.channel} · received {art.received_at}\n\n```text\n{text.strip()}\n```\n")
    (a.out / "packet.md").write_text("\n".join(parts), encoding="utf-8")
    (a.out / "key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    with (a.out / "scores.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["item", "realism_1_to_5", "issues", "notes"])
        for label in key:
            wr.writerow([label, "", "", ""])
    print(f"wrote {len(picks)} artifacts to {a.out / 'packet.md'} (score sheet: scores.csv, key: key.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
