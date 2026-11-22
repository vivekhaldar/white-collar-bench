"""Renderer tests: files, formats, phrasing helpers and the keyword/secret verifier.

These render simulations without building gold, so they are fast. End-to-end checks (world
check, build, questions, oracle stores) are in test_generate.py.
"""

from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

import pytest

from wcb.render import RenderError, render_world, verify_artifacts
from wcb.render.context import RenderContext, day_words, time_words
from wcb.render.phrases import Namer, has_keywords, lowercase_keep, subject_of, vp
from wcb.render.transcript import mangle
from wcb.world.comms import Communication
from wcb.world.planner import make_plan
from wcb.world.simulator import simulate


def _render(out: Path, seed: int = 3, size: str = "standard"):
    plan = make_plan(seed, size=size)
    sim = simulate(plan, seed)
    emits, ctx = render_world(plan, sim, out, seed=seed)
    return plan, sim, emits, ctx


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    out = tmp_path_factory.mktemp("render") / "w"
    plan, sim, emits, ctx = _render(out)
    return out, plan, sim, emits, ctx


def test_every_communication_becomes_files(rendered):
    out, _plan, sim, emits, _ctx = rendered
    expected = [a for c in sim.comms for a in c.artifacts]
    actual = [e["artifact"] for e in emits]
    assert actual[:len(expected)] == expected
    directory = emits[len(expected):]
    assert directory and all(e["title"] == "Contact directory updates" for e in directory)
    assert len(set(actual)) == len(actual)
    ids = [int(e["id"][2:]) for e in emits]
    assert ids == list(range(len(sim.events) + 1, len(sim.events) + 1 + len(emits)))
    for e in emits:
        p = out / e["path"]
        assert p.is_file() and p.stat().st_size > 0
        assert e["path"].startswith(f"inbox/{e['received_at'][:10]}/{e['artifact']}.")
        assert e["title"].strip()
    on_disk = sorted(p.relative_to(out).as_posix() for p in (out / "inbox").rglob("*") if p.is_file())
    assert on_disk == sorted(e["path"] for e in emits)


def test_attachments_follow_their_email(rendered):
    _out, _plan, sim, emits, _ctx = rendered
    by_id = {e["artifact"]: e for e in emits}
    docs = [e for e in emits if e["channel"] == "document"]
    assert docs and [d["artifact"] for d in docs] == [f"dc-{i:04d}" for i in range(1, len(docs) + 1)]
    for d in docs:
        parent = by_id[d["parent"]]
        assert parent["channel"] == "email" and parent["received_at"] == d["received_at"]
        assert set(d["reveals"]) <= set(parent["reveals"])


def test_rendering_is_deterministic(rendered, tmp_path):
    out, *_ = rendered
    _render(tmp_path / "again")
    a = {p.relative_to(out).as_posix(): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    b = {p.relative_to(tmp_path / "again").as_posix(): p.read_bytes() for p in (tmp_path / "again").rglob("*") if p.is_file()}
    assert a == b


def test_keywords_and_secrets_are_verified(rendered, tmp_path):
    out, _plan, sim, emits, _ctx = rendered
    copy = tmp_path / "copy"
    shutil.copytree(out, copy)
    verify_artifacts(copy, sim.events, emits)
    ev = {e["id"]: e for e in sim.events}
    # Remove one keyword from a text artifact that reveals a commitment.
    target = next(e for e in emits if e["path"].endswith((".eml", ".md", ".vtt")) and any(
        ev[r]["type"] == "commitment.create" for r in e["reveals"]))
    create = next(ev[r] for r in target["reveals"] if ev[r]["type"] == "commitment.create")
    p = copy / target["path"]
    text = p.read_text()
    for kw in create["keywords"]:
        text = text.replace(kw, "").replace(kw.title(), "").replace(kw.capitalize(), "").replace(kw.upper(), "")
    p.write_text(text)
    with pytest.raises(RenderError, match="lacks keywords"):
        verify_artifacts(copy, sim.events, emits)
    # A secret that is not in its file.
    shutil.rmtree(copy)
    shutil.copytree(out, copy)
    sec = next(e for e in emits if e["secrets"])
    (copy / sec["path"]).write_text("nothing here")
    with pytest.raises(RenderError, match="secret"):
        verify_artifacts(copy, sim.events, emits)


def test_secrets_only_where_declared(rendered):
    out, _plan, sim, emits, _ctx = rendered
    secrets = {s for c in sim.comms for s in c.secrets}
    assert secrets
    for e in emits:
        raw = (out / e["path"]).read_bytes().decode("utf-8", "replace")
        assert {s for s in secrets if s in raw} <= set(e["secrets"]) | {s for s in secrets if s not in raw}
        for s in e["secrets"]:
            assert s in raw


def test_email_texture(rendered):
    out, *_ = rendered
    emls = sorted(out.glob("inbox/*/em-*.eml"))
    texts = [p.read_text() for p in emls]
    assert all("\nDate: " in t and "\nMessage-ID: <" in t for t in texts)
    assert sum("\n> " in t for t in texts) >= 5  # quoted replies
    assert any("X-Draft: true" in t for t in texts)
    assert any("Unsubscribe" in t or "UNSUBSCRIBE" in t for t in texts)
    signoffs = ("Kind regards,", "Best regards,", "Regards,", "With thanks,", "Cheers,", "Thanks,", "Best,", "Talk soon,")
    assert sum(any(s in t for s in signoffs) for t in texts) >= 10


def test_chat_texture(rendered):
    out, *_ = rendered
    docs = [json.loads(p.read_text()) for p in sorted(out.glob("inbox/*/ch-*.json"))]
    msgs = [m for d in docs for m in d["messages"]]
    assert {d["kind"] for d in docs} == {"dm", "channel"}
    assert any(m.get("reactions") for m in msgs)
    assert any("thread_of" in m for m in msgs)
    assert any(d["channel"] in ("#random", "#general", "#coffee") for d in docs)
    for d in docs:
        ts = [m["ts"] for m in d["messages"]]
        assert ts == sorted(ts)


def test_transcript_texture(rendered):
    out, *_ = rendered
    vtts = [p.read_text() for p in sorted(out.glob("inbox/*/mt-*.vtt"))]
    assert vtts
    joined = "\n".join(vtts)
    assert "Mm-hmm." in joined or "Yeah." in joined or "Right." in joined  # backchannels
    assert "—" in joined  # cut-offs or a missing opening
    for t in vtts:
        cues = [ln for ln in t.splitlines() if "-->" in ln]
        starts = [c.split(" --> ")[0] for c in cues]
        assert starts == sorted(starts)


def test_recaps_and_notes(rendered):
    out, _plan, sim, _emits, _ctx = rendered
    mns = [p.read_text() for p in sorted(out.glob("inbox/*/mn-*.md"))]
    assert any("## Action items" in t and "may contain errors" in t for t in mns)
    nts = [p.read_text() for p in sorted(out.glob("inbox/*/nt-*.md"))]
    assert any(t.startswith("# Portfolio map") for t in nts)
    # Voice memos are drawn at random (tests/generator/test_generate.py checks that they occur).
    if any(c.kind == "voice_memo" for c in sim.comms):
        assert any(t.startswith("Voice memo") for t in nts)


def test_noise_is_marked_and_varied(rendered):
    out, _plan, sim, emits, _ctx = rendered
    noise = [e for e in emits if e["noise"]]
    assert noise and all("noise" in e["challenges"] for e in noise)
    kinds = {c.extra.get("noise_kind") for c in sim.comms if c.noise}
    assert len(kinds) >= 5


# ---------------------------------------------------------------- helpers
def test_vp_pronouns_and_keywords(rendered):
    _out, plan, sim, _emits, ctx = rendered
    create = next(e for e in sim.events if e["type"] == "commitment.create" and e["what"].startswith("Send ")
                  and e["creditor"] == ctx.worker)
    comm = Communication(id="cm-test", t=create["t"], channel="email", kind="email", sender=ctx.worker,
                         to=[create["debtor"]], received_at=create["t"])
    roles = [create["debtor"], create["creditor"], ctx.worker]
    asker = Namer(ctx, comm, ctx.worker, [create["debtor"]])
    text = vp(ctx, asker, create["what"], create["keywords"], roles)
    assert text.startswith("send me ") and has_keywords(text, create["keywords"])
    third = Namer(ctx, comm, create["debtor"], [], third_person=True)
    text3 = vp(ctx, third, create["what"], create["keywords"], roles)
    assert ctx.first(ctx.worker) in text3


def test_subject_of_strips_people():
    names = {"Ana", "Bo"}
    assert subject_of(names, "Send Ana the Heron risk register") == "the Heron risk register"
    assert subject_of(names, "Share the Heron plan with Bo") == "the Heron plan"
    assert subject_of(names, "Review Ana's Heron spec") == "Ana's Heron spec"
    assert subject_of(names, "Introduce Ana to Bo") == "introduce Ana to Bo"


def test_lowercase_keeps_secrets_and_words():
    secret = "https://meet.x.example/j/1?pwd=AbC9"
    assert lowercase_keep(f"Join HERE: {secret} Now", [secret]) == f"join here: {secret} now"
    assert day_words("2027-04-08", 0) == "Thursday 8 April"
    assert day_words("2027-04-08", 1) == "Thu 8 Apr"
    assert time_words("2027-04-08T14:30:00-07:00") == "2:30pm"


def test_mangle_is_deterministic_and_different():
    for name in ("Svetlana", "Thandiwe", "Dewi", "Salma", "Tariq", "Bo"):
        a = mangle(name, random.Random(1))
        assert a == mangle(name, random.Random(1)) and a != name


def test_context_indexes(rendered):
    _out, _plan, sim, _emits, ctx = rendered
    assert isinstance(ctx, RenderContext)
    for e in sim.events:
        if e["type"] in ("commitment.update", "commitment.resolve"):
            assert e["id"] in ctx.loop_before
    assert ctx.injection_artifact and ctx.injection_artifact.startswith("em-")


# ---------------------------------------------------------------- optional LLM rewrite
class _FakeClient:
    spec = "fake:test"

    def __init__(self, rewrite, verdict="NO"):
        self.rewrite, self.verdict, self.calls = rewrite, verdict, 0

    def complete(self, prompt, *, system=None, temperature=0.0, max_tokens=512):
        self.calls += 1
        if prompt.startswith("Compare ORIGINAL"):
            return self.verdict
        body = prompt.split("<<<\n", 1)[1].rsplit("\n>>>", 1)[0]
        return self.rewrite(body)


def test_rewriter_accepts_verified_rewrites_and_caches(tmp_path):
    from wcb.render.llm import Rewriter

    client = _FakeClient(lambda body: "Quick note: " + body)
    rw = Rewriter(client=client, cache_dir=tmp_path)
    text = "I'll send you the Heron risk register by Thursday 8 April."
    out = rw.rewrite(text, keywords=["risk register", "heron"], secrets=[])
    assert out == "Quick note: " + text and client.calls == 2
    assert rw.rewrite(text, keywords=["risk register", "heron"], secrets=[]) == out
    assert client.calls == 2 and rw.stats["cached"] == 2


@pytest.mark.parametrize("rewrite,verdict", [
    (lambda b: b.replace("risk register", "list"), "NO"),        # drops a keyword
    (lambda b: b + " Also by Friday 9 April.", "NO"),            # adds a date
    (lambda b: b + " Looping in Ysolde.", "NO"),               # adds a person
    (lambda b: b.replace("pwd=AbC9", "pwd=x"), "NO"),            # breaks a secret
    (lambda b: "Sure. " + b, "YES"),                              # verifier objects
])
def test_rewriter_keeps_template_text_when_verification_fails(tmp_path, rewrite, verdict):
    from wcb.render.llm import Rewriter

    rw = Rewriter(client=_FakeClient(rewrite, verdict), cache_dir=tmp_path)
    text = "I'll send you the Heron risk register by Thursday 8 April. Join: https://m.example/j/1?pwd=AbC9"
    assert rw.rewrite(text, keywords=["risk register", "heron"], secrets=["https://m.example/j/1?pwd=AbC9"]) == text
    assert rw.stats["rejected"] == 1


def test_render_world_with_rewriter(tmp_path):
    from wcb.render.llm import Rewriter

    plan = make_plan(4, size="small")
    sim = simulate(plan, 4)
    rw = Rewriter(client=_FakeClient(lambda b: b + "\n\nThanks for bearing with me."), cache_dir=tmp_path / "cache")
    emits, _ctx = render_world(plan, sim, tmp_path / "w", seed=4, rewriter=rw)
    texts = [(tmp_path / "w" / e["path"]).read_text() for e in emits if e["channel"] == "email" and not e["noise"]]
    assert rw.stats["accepted"] > 0 and any("Thanks for bearing with me." in t for t in texts)
