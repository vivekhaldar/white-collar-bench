"""End-to-end generator tests: `generate_world` for several seeds and sizes, with build.

Each world is generated twice into separate directories (determinism) and built, then checked
with the repository's own tools: `wcb world check`, the gold question builder, calibration
statistics and the store-contract validator on the oracle stores.
"""

from __future__ import annotations

import email
import json
import zipfile
from email import policy
from pathlib import Path

import pytest
import yaml

from wcb.questions.build import build_questions
from wcb.questions.templates import TEMPLATES
from wcb.render import verify_artifacts
from wcb.render.email import INJECTION_LINES
from wcb.world.check import check_world, raw_text
from wcb.world.generate import generate_world
from wcb.world.model import World
from wcb.world.names import HARD_DENYLIST
from wcb.world.planner import CHALLENGE_TAGS
from wcb.world.state import state_at

SEEDS = (0, 1, 2)
SIZES = ("small", "standard")
WORLDS = [(s, z) for s in SEEDS for z in SIZES]
# Names from the hand-authored pilot world that generated worlds must never reuse.
PILOT_NAMES = ("tarrow", "kestrow", "saltmarren", "kettleyard", "tinderbox", "scrivelo", "penmarq",
               "huddlescribe", "eskerfield", "renwick", "ilves")
TEXT_SUFFIXES = {".eml", ".json", ".vtt", ".md", ".ics", ".yaml", ".jsonl"}


@pytest.fixture(scope="session")
def generated(tmp_path_factory) -> dict[tuple[int, str], tuple[Path, Path]]:
    out = {}
    for seed, size in WORLDS:
        a = generate_world(seed=seed, size=size, out_dir=tmp_path_factory.mktemp(f"g{seed}{size}a") / "w")
        b = generate_world(seed=seed, size=size, out_dir=tmp_path_factory.mktemp(f"g{seed}{size}b") / "w")
        out[(seed, size)] = (a, b)
    return out


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def _emits(world_dir: Path) -> list[dict]:
    rows = [json.loads(x) for x in (world_dir / "world.jsonl").read_text().splitlines() if x.strip()]
    return [r for r in rows if r["type"] == "artifact.emit"]


@pytest.mark.parametrize("seed,size", WORLDS)
def test_world_check_is_clean(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    issues = check_world(world_dir)
    assert not issues, "\n".join(i.format() for i in issues[:20])


@pytest.mark.parametrize("seed,size", WORLDS)
def test_generation_is_byte_deterministic(generated, seed, size):
    a, b = generated[(seed, size)]
    fa, fb = _files(a), _files(b)
    assert sorted(fa) == sorted(fb)
    diff = [k for k in fa if fa[k] != fb[k]]
    assert not diff, diff[:10]


def test_different_seeds_differ(generated):
    a, _ = generated[(0, "standard")]
    b, _ = generated[(1, "standard")]
    assert (a / "world.jsonl").read_bytes() != (b / "world.jsonl").read_bytes()


@pytest.mark.parametrize("seed,size", WORLDS)
def test_every_challenge_tag_is_planted(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    tags = {t for e in _emits(world_dir) for t in e["challenges"]}
    assert set(CHALLENGE_TAGS) <= tags, sorted(set(CHALLENGE_TAGS) - tags)


@pytest.mark.parametrize("seed,size", WORLDS)
def test_questions_cover_templates_and_gold_builds(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    world = World.load(world_dir)
    specs = yaml.safe_load((world_dir / "questions.yaml").read_text())
    assert {s["template"] for s in specs} == set(TEMPLATES)
    states = {c["date"]: state_at(world, c["date"]) for c in world.checkpoints()}
    docs = build_questions(world, states)
    qs = [q for d in docs.values() for q in d["questions"]]
    assert len(qs) == len(specs)
    for q in qs:
        assert q["text"] and q["type"]
        assert q["answerable"] == bool(q["gold"]) or q["template"] in ("i_owe", "owed_to_me", "project_loops",
                                                                         "project_changes")
    unanswerable = sum(1 for q in qs if not q["answerable"])
    assert 0.05 <= unanswerable / len(qs) <= 0.2
    per_cp = {"small": 11, "standard": 15}[size]
    for cp, d in docs.items():
        templates = [q["template"] for q in d["questions"]]
        assert len(templates) == per_cp, (cp, templates)
        assert {"focus_tomorrow", "project_status", "project_changes", "i_owe", "owed_to_me"} <= set(templates)
    entity_qs = [s for s in specs if {"person", "project"} & set(s["params"])]
    aliased = sum(1 for s in entity_qs if "name_form" in s["params"])
    assert 0.15 <= aliased / len(entity_qs) <= 0.5
    # the built gold matches what build_questions computes now
    built = json.loads((world_dir / "gold" / "questions" / "cp1.json").read_text())
    assert [q["id"] for q in built["questions"]] == [q["id"] for q in docs["cp1"]["questions"]]


@pytest.mark.parametrize("seed,size", WORLDS)
def test_calibration_within_tolerance(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    stats = json.loads((world_dir / "gold" / "calibration.json").read_text())
    arts = stats["artifacts"]
    lo, hi = {"small": (9, 18), "standard": (14, 23)}[size]
    assert lo <= arts["per_episode_day_mean"] <= hi
    assert set(arts["by_channel"]) == {"email", "chat", "transcript", "meeting_notes", "document", "note", "calendar"}
    emails = [e for e in _emits(world_dir) if e["channel"] == "email"]
    noise = sum(e["noise"] for e in emails) / len(emails)
    assert 0.35 <= noise <= 0.7
    per_wd = stats["commitments"]["created_per_workday_mean"]
    assert {"small": (3.0, 7.5), "standard": (4.5, 9.5)}[size][0] <= per_wd <= {"small": (3.0, 7.5), "standard": (4.5, 9.5)}[size][1]
    loops = stats["loops"]
    assert 0.3 <= loops["final_status"]["shares"].get("done", 0) <= 0.6
    assert 0.75 <= loops["accepted_share"] <= 0.97
    assert stats["questions"]["unanswerable_share"] <= 0.2


@pytest.mark.parametrize("seed,size", WORLDS)
def test_oracle_stores_validate(generated, seed, size):
    from wcb.contract.validate import validate_store

    world_dir, _ = generated[(seed, size)]
    world = World.load(world_dir)
    for store in sorted((world_dir / "gold" / "oracle-store").iterdir()):
        state = state_at(world, store.name)
        issues = [i for i in validate_store(store, delivered=set(state["delivered"]))
                  if i.severity == "error" and "CONTRACT.md" not in f"{i.path or ''} {i.message}"]
        assert not issues, [i.format() for i in issues[:10]]
        text = "\n".join(p.read_text() for p in store.rglob("*.md"))
        assert not [s for s in state["secrets"] if s in text]


@pytest.mark.parametrize("seed,size", [(1, "standard"), (2, "small")])
def test_artifact_formats(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    emits = _emits(world_dir)
    seen = {"draft": 0, "reply": 0, "edit": 0, "thread": 0, "drift": 0, "methods": set()}
    for e in emits:
        path = world_dir / e["path"]
        data = path.read_bytes()
        if path.suffix == ".eml":
            msg = email.message_from_bytes(data, policy=policy.default)
            assert msg["Date"] and msg["From"] and msg["To"] and msg["Subject"] and msg["Message-ID"]
            body = msg.get_content()
            seen["draft"] += msg["X-Draft"] == "true"
            seen["reply"] += bool(msg["In-Reply-To"]) and "\n> " in body
        elif path.suffix == ".json":
            doc = json.loads(data)
            assert {"workspace", "channel", "kind", "participants", "messages"} <= set(doc)
            assert doc["kind"] in ("dm", "channel") and doc["messages"]
            for m in doc["messages"]:
                assert m["ts"] and m["user"] and isinstance(m["text"], str)
                seen["edit"] += bool(m.get("edited")) and m.get("original") not in (None, m["text"])
                seen["thread"] += "thread_of" in m
        elif path.suffix == ".vtt":
            text = data.decode()
            assert text.startswith("WEBVTT\n\nNOTE\n") and "-->" in text and "<v " in text
            attendees = next(ln for ln in text.splitlines() if ln.startswith("Attendees:"))
            labels = {ln[3:].split(">", 1)[0] for ln in text.splitlines() if ln.startswith("<v ")}
            seen["drift"] += any(lb not in attendees for lb in labels)
        elif path.suffix == ".ics":
            text = data.decode()
            method = next(ln for ln in text.splitlines() if ln.startswith("METHOD:"))[7:]
            seen["methods"].add(method)
            assert "DTSTART:" in text and "ORGANIZER" in text
        elif path.suffix in (".docx", ".xlsx"):
            assert zipfile.ZipFile(path).testzip() is None
        elif path.suffix == ".pdf":
            assert data.startswith(b"%PDF")
        assert e["path"].split("/")[1] == e["received_at"][:10]
        if e["parent"]:
            assert e["parent"].startswith("em-")
    assert seen["draft"] >= 1 and seen["reply"] >= 3 and seen["edit"] >= 1 and seen["thread"] >= 1
    assert seen["drift"] >= 1
    assert {"REQUEST", "REPLY"} <= seen["methods"]


def test_calendar_methods_across_worlds(generated):
    methods = set()
    for world_dir, _ in generated.values():
        for p in world_dir.glob("inbox/*/*.ics"):
            methods.add(next(ln for ln in p.read_text().splitlines() if ln.startswith("METHOD:"))[7:])
    assert methods == {"REQUEST", "CANCEL", "REPLY"}


@pytest.mark.parametrize("seed,size", WORLDS)
def test_secrets_keywords_and_injection(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    emits = _emits(world_dir)
    events = [json.loads(x) for x in (world_dir / "world.jsonl").read_text().splitlines()]
    verify_artifacts(world_dir, [e for e in events if e["type"] != "artifact.emit"], emits)
    assert any(e["secrets"] for e in emits)
    for e in emits:
        raw = raw_text(world_dir / e["path"])
        for s in e["secrets"]:
            assert raw is not None and s in raw
    injected = [e for e in emits if (raw := raw_text(world_dir / e["path"])) and any(x in raw for x in INJECTION_LINES)]
    assert len(injected) == 1 and injected[0]["noise"] and not injected[0]["reveals"]
    plan = yaml.safe_load((world_dir / "plan.yaml").read_text())
    assert plan["audit"]["instruction_injection"] == injected[0]["artifact"]


@pytest.mark.parametrize("seed,size", WORLDS)
def test_no_denylisted_or_pilot_names(generated, seed, size):
    world_dir, _ = generated[(seed, size)]
    for p in world_dir.rglob("*"):
        if p.is_file() and p.suffix in TEXT_SUFFIXES:
            low = p.read_text(encoding="utf-8").lower()
            bad = [w for w in (*HARD_DENYLIST, *PILOT_NAMES) if w in low]
            assert not bad, (p, bad)


def test_world_yaml_and_plan(generated):
    world_dir, _ = generated[(1, "standard")]
    meta = yaml.safe_load((world_dir / "world.yaml").read_text())
    gen = meta["generator"]
    assert gen["kind"] == "wcb-gen" and gen["seed"] == 1 and gen["weeks"] == 1 and gen["size"] == "standard"
    assert meta["id"] == "gen-s1-w1" and meta["split"] == "dev"
    plan = yaml.safe_load((world_dir / "plan.yaml").read_text())
    voices = {p["voice"] for p in plan["people"] if p["tier"] == "core"}
    assert voices == {"formal", "terse", "chatty", "lowercase"}
    assert plan["audit"]["unrevealed"]
    # noise artifacts carry nothing but their (minor) sender; documents hang off emails
    emits = _emits(world_dir)
    events = {e["id"]: e for e in map(json.loads, (world_dir / "world.jsonl").read_text().splitlines())}
    for e in emits:
        if e["noise"]:
            assert all(events[r]["type"] == "entity.create" and events[r]["kind"] == "person" for r in e["reveals"])
    assert any(e["channel"] == "document" and e["parent"] for e in emits)


def test_regenerating_into_the_same_directory_replaces_it(tmp_path):
    out = tmp_path / "w"
    generate_world(seed=5, size="small", out_dir=out, build=False)
    (out / "inbox" / "stray.txt").write_text("x")
    keep = out / "README.local"
    keep.write_text("mine")
    generate_world(seed=5, size="small", out_dir=out, build=False)
    assert not (out / "inbox" / "stray.txt").exists() and keep.read_text() == "mine"
    assert not (out / "gold").exists()
    assert not [i for i in check_world(out) if i.severity == "error"]
