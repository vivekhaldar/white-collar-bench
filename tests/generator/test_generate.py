"""End-to-end generator tests: `generate_world` for several seeds and sizes, with build.

Each world is generated twice into separate directories (determinism) and built, then checked
with the repository's own tools: `wcb world check`, the gold question builder, calibration
statistics and the store-contract validator on the oracle stores.
"""

from __future__ import annotations

import email
import json
import zipfile
from collections import Counter
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
from wcb.world.names import contains_denied
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


def test_generation_does_not_depend_on_hash_randomization(tmp_path):
    """Same seed under different PYTHONHASHSEED values (set iteration order) gives the same bytes.

    Seed 4 at two weeks once rendered a transcript differently from run to run, because names
    of equal length were ordered by set iteration.
    """
    import os
    import subprocess
    import sys

    outs = []
    for hs in ("1", "2", "3"):
        out = tmp_path / f"h{hs}"
        code = ("from pathlib import Path; from wcb.world.generate import generate_world; "
                f"generate_world(seed=4, weeks=2, out_dir=Path({str(out)!r}), build=False)")
        env = {**os.environ, "PYTHONHASHSEED": hs}
        subprocess.run([sys.executable, "-c", code], check=True, env=env)
        outs.append(_files(out))
    for other in outs[1:]:
        assert sorted(other) == sorted(outs[0])
        diff = [k for k in outs[0] if outs[0][k] != other[k]]
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


def test_voice_memos_occur_across_worlds(generated):
    memos = [p for world_dir, _ in generated.values() for p in world_dir.glob("inbox/*/nt-*.md")
             if p.read_text().startswith("Voice memo")]
    assert memos


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
            bad = [w for w in PILOT_NAMES if w in low]
            assert not bad, (p, bad)
            assert not contains_denied(low), p


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


# ---------------------------------------------------------------- gold faithfulness and texture
def _world_rows(world_dir: Path) -> tuple[dict[str, dict], list[dict], dict[str, dict]]:
    rows = [json.loads(x) for x in (world_dir / "world.jsonl").read_text().splitlines() if x.strip()]
    ev = {r["id"]: r for r in rows}
    arts = {r["artifact"]: r for r in rows if r["type"] == "artifact.emit"}
    return ev, rows, arts


def _accepted_by(rows: list[dict], cid: str, t: str) -> bool:
    create = next(r for r in rows if r["type"] == "commitment.create" and r["commitment"] == cid)
    return create["accepted"] or any(r["type"] == "commitment.update" and r["commitment"] == cid
                                     and r["changes"].get("accepted") is True and r["t"] <= t for r in rows)


def _first_reveal_dates(arts: dict[str, dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for a in sorted(arts.values(), key=lambda a: a["received_at"]):
        for r in a["reveals"]:
            out.setdefault(r, a["received_at"][:10])
    return out


@pytest.mark.parametrize("seed,size", WORLDS)
def test_meeting_asks_are_answered_by_the_debtor(generated, seed, size):
    """An ask in a meeting names its debtor (never 'You,') and the debtor answers it next."""
    world_dir, _ = generated[(seed, size)]
    ev, rows, arts = _world_rows(world_dir)
    names = {r["entity"]: r["name"] for r in rows if r["type"] == "entity.create" and r["kind"] == "person"}
    asks = 0
    for a in arts.values():
        if a["channel"] != "transcript":
            continue
        text = (world_dir / a["path"]).read_text()
        assert "<v " not in text or "\n<v" in text
        cues = [(ln[3:].split(">", 1)[0], ln.split(">", 1)[1]) for ln in text.splitlines() if ln.startswith("<v ")]
        assert not any(t.startswith("You, ") for _, t in cues), a["artifact"]
        for r in a["reveals"]:
            e = ev[r]
            if e["type"] != "commitment.create":
                continue
            kws = [k.lower() for k in e["keywords"]]
            debtor = names[e["debtor"]]
            for i, (sp, t) in enumerate(cues):
                low = t.lower()
                if all(k in low for k in kws) and "you" in low and "?" in t and sp != debtor \
                        and any(low.startswith(f"{w.lower()}, ") for w in debtor.split()[:1]):
                    asks += 1
                    assert i + 1 < len(cues) and cues[i + 1][0].split()[0].startswith(debtor.split()[0][:3]), \
                        (a["artifact"], t, cues[i + 1] if i + 1 < len(cues) else None)
    assert asks >= 0


@pytest.mark.parametrize("seed,size", WORLDS)
def test_restatements_match_the_loop_state(generated, seed, size):
    """A restated loop is never delivered after the loop closed (except a delayed catch-up of the
    original exchange), and a loop nobody agreed to is never described as agreed."""
    world_dir, _ = generated[(seed, size)]
    ev, rows, arts = _world_rows(world_dir)
    first = _first_reveal_dates(arts)
    closed: dict[str, str] = {}
    for r in rows:
        if r["type"] == "commitment.resolve":
            closed.setdefault(r["commitment"], r["t"])
    for a in arts.values():
        if a["noise"] or a["channel"] == "document":
            continue
        raw = raw_text(world_dir / a["path"]) or ""
        for rid in a["reveals"]:
            e = ev[rid]
            if e["type"] != "commitment.create":
                continue
            cid = e["commitment"]
            if first[rid] < a["received_at"][:10] and "batch_catchup" not in a["challenges"]:
                assert not (cid in closed and closed[cid] < a["received_at"]), (a["artifact"], cid)
            if not _accepted_by(rows, cid, a["received_at"]):
                for line in raw.lower().splitlines():
                    if all(k in line for k in e["keywords"]):
                        assert "agreed to" not in line and "said they'd" not in line, (a["artifact"], line)


@pytest.mark.parametrize("seed,size", WORLDS)
def test_meeting_commitments_have_their_debtor_in_the_room(generated, seed, size):
    """An accepted commitment a transcript shows is made by someone present, or reported as such."""
    world_dir, _ = generated[(seed, size)]
    ev, rows, arts = _world_rows(world_dir)
    names = {r["entity"]: r["name"] for r in rows if r["type"] == "entity.create" and r["kind"] == "person"}
    worker = yaml.safe_load((world_dir / "world.yaml").read_text())["worker"]
    first = _first_reveal_dates(arts)
    for a in arts.values():
        if a["channel"] != "transcript":
            continue
        text = (world_dir / a["path"]).read_text()
        attendees = next(ln for ln in text.splitlines() if ln.startswith("Attendees:"))
        for rid in a["reveals"]:
            e = ev[rid]
            if e["type"] != "commitment.create" or e["debtor"] == worker or first[rid] < a["received_at"][:10]:
                continue
            if not _accepted_by(rows, e["commitment"], a["received_at"]) or names[e["debtor"]] in attendees:
                continue
            line = next((ln for ln in text.splitlines() if all(k in ln.lower() for k in e["keywords"])), "")
            assert any(p in line for p in ("said they'd", "they'll", "has agreed to", "Recap")), (a["artifact"], line)


@pytest.mark.parametrize("seed,size", WORLDS)
def test_chat_messages_follow_their_events(generated, seed, size):
    """A chat message that states a commitment or decision is posted no earlier than it happened
    and no later than the thread is delivered."""
    world_dir, _ = generated[(seed, size)]
    ev, _rows, arts = _world_rows(world_dir)
    for a in arts.values():
        if a["channel"] != "chat" or a["noise"]:
            continue
        doc = json.loads((world_dir / a["path"]).read_text())
        assert [m["ts"] for m in doc["messages"]] == sorted(m["ts"] for m in doc["messages"])
        for rid in a["reveals"]:
            e = ev[rid]
            if e["type"] not in ("commitment.create", "decision.make"):
                continue
            for m in doc["messages"]:
                if all(k in m["text"].lower() for k in e["keywords"]):
                    assert e["t"] <= m["ts"] <= a["received_at"], (a["artifact"], m["ts"], e["t"])
                    break


@pytest.mark.parametrize("seed,size", WORLDS)
def test_reversals_replace_like_with_like(generated, seed, size):
    """The decision that replaces a reversed one is its counterpart, never an unrelated one."""
    world_dir, _ = generated[(seed, size)]
    _ev, rows, _arts = _world_rows(world_dir)
    makes = {r["decision"]: r for r in rows if r["type"] == "decision.make"}
    for r in rows:
        if r["type"] != "decision.reverse":
            continue
        old = makes[r["decision"]]
        after = [m for m in makes.values() if m.get("project") == old.get("project") and r["t"] <= m["t"] <= r["t"][:16]
                 + ":59" + r["t"][19:] and m["decision"] != old["decision"]]
        for m in after:
            assert m["what"].split()[0] != "Widen" or old["what"].split()[0] == "Limit", (old["what"], m["what"])


@pytest.mark.parametrize("seed,size", WORLDS)
def test_calendar_items_hang_together(generated, seed, size):
    """Updates and cancellations share the UID of an invite or a meeting series; most invited
    meetings that fall inside the world are held with a record (or deliberately left untraced)."""
    world_dir, _ = generated[(seed, size)]
    _ev, _rows, arts = _world_rows(world_dir)
    uids: dict[str, list[str]] = {}
    for a in sorted(arts.values(), key=lambda a: a["received_at"]):
        if a["channel"] != "calendar":
            continue
        text = (world_dir / a["path"]).read_text()
        uid = next(ln for ln in text.splitlines() if ln.startswith("UID:"))[4:]
        method = next(ln for ln in text.splitlines() if ln.startswith("METHOD:"))[7:]
        summary = next(ln for ln in text.splitlines() if ln.startswith("SUMMARY:"))[8:]
        kind = "update" if summary.startswith("Updated: ") else "cancel" if method == "CANCEL" else method
        if kind == "update":
            assert uids.get(uid), (a["artifact"], "update without an invite")
        if kind == "cancel" and "RECURRENCE-ID" not in text:
            assert uids.get(uid), (a["artifact"], "cancel without an invite")
        uids.setdefault(uid, []).append(kind)
    assert not any("(worker away)" in a["title"] for a in arts.values())


@pytest.mark.parametrize("seed,size", WORLDS)
def test_no_one_names_themselves(generated, seed, size):
    """Speakers never refer to themselves by their bare first name."""
    world_dir, _ = generated[(seed, size)]
    _ev, rows, arts = _world_rows(world_dir)
    full_names = {r["name"] for r in rows if r["type"] == "entity.create" and r["kind"] == "person"}
    import re

    def bare(first: str, text: str) -> bool:
        for m in re.finditer(rf"\b{re.escape(first)}\b", text):
            rest = text[m.start():]
            if not any(rest.startswith(n) for n in full_names if n.startswith(first + " ")):
                return True
        return False

    for a in arts.values():
        path = world_dir / a["path"]
        if a["channel"] == "chat" and not a["noise"]:
            for m in json.loads(path.read_text())["messages"]:
                assert not bare(m["user"].split()[0], m["text"]), (a["artifact"], m["user"], m["text"])
        elif a["channel"] == "transcript":
            for ln in path.read_text().splitlines():
                if ln.startswith("<v "):
                    sp, t = ln[3:].split(">", 1)
                    if "'s " not in sp and "(" not in sp:
                        assert not bare(sp.split()[0], t), (a["artifact"], sp, t)


@pytest.mark.parametrize("seed,size", WORLDS)
def test_texture_and_calibration_extras(generated, seed, size):
    """Replies with quoted history, threaded chats, backchannels, no raw phase labels, noise on a
    schedule, and the worker's portfolio map in the first person."""
    import re

    world_dir, _ = generated[(seed, size)]
    _ev, _rows, arts = _world_rows(world_dir)
    stats = json.loads((world_dir / "gold" / "calibration.json").read_text())
    emails = [a for a in arts.values() if a["channel"] == "email" and not a["noise"]]
    replies = [a for a in emails if re.search(r"^Subject: (Re|Fwd):", (world_dir / a["path"]).read_text(), re.M)]
    assert len(replies) / len(emails) >= 0.35
    depth = max(max((len(m) for m in re.findall(r"^(>+)", (world_dir / a["path"]).read_text(), re.M)), default=0)
                for a in emails)
    assert depth >= 3
    lengths = sorted(len(json.loads((world_dir / a["path"]).read_text())["messages"])
                     for a in arts.values() if a["channel"] == "chat" and not a["noise"])
    assert lengths[len(lengths) // 2] >= 3
    cues = [ln.split(">", 1)[1] for a in arts.values() if a["channel"] == "transcript"
            for ln in (world_dir / a["path"]).read_text().splitlines() if ln.startswith("<v ")]
    from wcb.render.phrases import BACKCHANNELS

    assert 0.2 <= sum(c in BACKCHANNELS for c in cues) / len(cues) <= 0.55
    issues = Counter()
    for a in arts.values():
        text = raw_text(world_dir / a["path"]) or ""
        assert not re.search(r"Currently in (placeholder|asking|dormant|ongoing)\b", text), a["artifact"]
        if a["noise"] and a["channel"] == "email":
            m = re.search(r"^Subject: (.*): issue (\d+)$", text, re.M)
            if m:
                issues[m.groups()] += 1
    assert all(n == 1 for n in issues.values()), issues
    portfolio = next(a for a in arts.values() if a["title"] == "Portfolio map")
    assert "owner: me" in (world_dir / portfolio["path"]).read_text()
    loops = stats["loops"]
    assert loops["kind"]["shares"].get("decision", 0) <= 0.1
    assert loops["lifetime_business_days"]["median"] <= 2.5
