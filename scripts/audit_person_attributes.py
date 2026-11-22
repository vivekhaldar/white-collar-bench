#!/usr/bin/env python3
"""Print the delivered evidence for every person attribute queried at each checkpoint."""

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wcb.questions.build import build_questions  # noqa: E402
from wcb.questions.person_evidence import attribute_sources  # noqa: E402
from wcb.world.model import World  # noqa: E402
from wcb.world.state import state_at  # noqa: E402


def main():
    writer = csv.writer(sys.stdout)
    writer.writerow(["world", "checkpoint", "question", "person", "attribute", "value", "required", "sources"])
    missing = 0
    for path in sorted((ROOT / "worlds").rglob("world.yaml")):
        world = World.load(path.parent)
        for cp, doc in build_questions(world, {}).items():
            state = state_at(world, doc["date"])
            for q in doc["questions"]:
                if q["template"] not in {"person_attr", "person_brief"}:
                    continue
                person = q["params"]["person"]
                attrs = state["entities"].get(person, {}).get("attrs", {})
                role = next((r for r in q["gold"].get("rubric", []) if r["aspect"] == "role"), None)
                fields = [q["params"]["attribute"]] if q["template"] == "person_attr" else ["role", "org"]
                for field in fields:
                    if field not in {"role", "org", "relationship"}:
                        continue
                    sources = attribute_sources(world, state, person, field) if field in attrs else []
                    if q["template"] == "person_attr":
                        required = q["answerable"] and not q["gold"].get("uncertain", False)
                    else:
                        required = bool(role and (field == "role" or " at " in role["text"]))
                    writer.writerow([world.id, cp, q["id"], person, field, attrs.get(field), required, " ".join(sources)])
                    missing += int(required and not sources)
    print(f"{missing} required attributes without a delivered source", file=sys.stderr)
    return int(bool(missing))


if __name__ == "__main__":
    sys.exit(main())
