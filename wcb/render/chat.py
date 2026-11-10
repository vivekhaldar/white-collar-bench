"""Chat renderer: JSON thread exports (docs/formats.md §1.6).

One chat communication becomes one export: a DM between two people or a channel such as
`#heron-core`. Messages carry the acts in the author's chat voice (terse, lowercase, chatty or
formal), with acknowledgements, threaded replies (`thread_of`), reactions, and now and then an
edit that changes a fact (`"edited": true` with the earlier text in `"original"`). Social
channels (`#random`, `#general`, `#coffee`) carry noise only.
"""

from __future__ import annotations

import datetime as dt
import json
import random
import re

from wcb.render.context import RenderContext, Rendered, day_words
from wcb.render.phrases import (
    CHAT_ACKS,
    REACTIONS,
    SOCIAL_CHAT,
    Line,
    Namer,
    Phraser,
    act_lines,
    coverage_gaps,
    gap_lines,
    lower_first,
    style_chat,
)
from wcb.util.dates import parse_dt
from wcb.world.comms import Communication


def render(ctx: RenderContext, comm: Communication) -> list[Rendered]:
    rng = ctx.rng(comm.id)
    aid = comm.artifacts[0]
    if comm.kind == "chat_dm":
        other = comm.to[0] if comm.to else ctx.worker
        people = [comm.sender, other]
        channel = "dm-" + "-".join(sorted(_slug(ctx.first(p)) for p in people))
        kind = "dm"
        title = f"DM: {ctx.full(comm.sender)} / {ctx.full(other)}"
    else:
        people = list(dict.fromkeys([comm.sender, *comm.participants, ctx.worker]))
        channel = comm.subject if comm.subject.startswith("#") else "#" + _slug(comm.subject or "general")
        kind = "channel"
        title = channel
    if comm.noise:
        messages, people = _social(ctx, comm, rng)
    else:
        messages = _messages(ctx, comm, rng, people)
    doc = {
        "workspace": ctx.workspace,
        "channel": channel,
        "kind": kind,
        "participants": [_display(ctx, p, comm) for p in people if p],
        "messages": messages,
    }
    text = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    if comm.extra.get("away") and kind == "channel":
        title += " (catch-up)"
    return [Rendered(aid, ".json", title, content=text, text=text)]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def _display(ctx: RenderContext, pid: str, comm: Communication) -> str:
    """Display name: a planted nickname or bare first name (aliases, collisions), else the full name."""
    return ctx.display_name(pid, comm)


class _Clock:
    """Message timestamps: increasing seconds, never after the export time."""

    def __init__(self, start: dt.datetime, end: dt.datetime, rng: random.Random):
        self.t = start
        self.end = end
        self.rng = rng

    def at(self, t: dt.datetime | None = None, gap: tuple[int, int] = (20, 240)) -> str:
        if t is not None and t > self.t:
            self.t = t
        else:
            self.t = self.t + dt.timedelta(seconds=self.rng.randint(*gap))
        if self.t > self.end:
            self.t = self.end
        return self.t.isoformat()


def _msg(ctx: RenderContext, comm: Communication, pid: str, ts: str, text: str, **extra) -> dict:
    m = {"ts": ts, "user": _display(ctx, pid, comm), "handle": ctx.handle(pid), "text": text}
    m.update({k: v for k, v in extra.items() if v is not None})
    return m


def _counterpart(ctx: RenderContext, e: dict, speaker: str) -> str | None:
    """The other party of a loop event, from the speaker's side (None for other events)."""
    if e["type"] == "commitment.create":
        D, Cr = e["debtor"], e["creditor"]
    elif e["type"] in ("commitment.update", "commitment.resolve"):
        lp = ctx.loop_before.get(e["id"]) or {}
        D, Cr = lp.get("debtor"), lp.get("creditor")
    else:
        return None
    if speaker == D:
        return Cr
    if speaker == Cr:
        return D
    return None


def _messages(ctx: RenderContext, comm: Communication, rng: random.Random, people: list[str]) -> list[dict]:
    S = comm.sender or ctx.worker
    others = [p for p in people if p != S]
    dm = comm.kind == "chat_dm"
    namer = Namer(ctx, comm, S, [others[0]] if dm and others else [])
    ph = Phraser(ctx, comm, rng)
    keep = list(comm.secrets)
    lines: list[tuple[Line, str]] = []  # (line, prefix)
    for a in comm.acts:
        e = ctx.events[a.event]
        prefix = ""
        nm = namer
        if not dm:
            cp = _counterpart(ctx, e, S)
            if cp and cp in people and cp != S and a.how in ("direct", "hedged", "implied"):
                nm = namer.view(S, [cp])
                prefix = ctx.handle(cp) + " "
        for ln in act_lines(ctx, comm, ph, nm, "written", acts=[a]):
            lines.append((ln, prefix))
    end = max(parse_dt(comm.received_at), parse_dt(comm.t))
    times = [parse_dt(ctx.events[ln.act]["t"]) for ln, _ in lines if ln.act]
    first = min(times) if times else parse_dt(comm.t)
    start = first - dt.timedelta(seconds=rng.randint(90, 400))
    clock = _Clock(start, end, rng)
    out: list[dict] = []
    voice = ctx.voice(S)
    if rng.random() < 0.45 and dm:
        greet = rng.choice(["morning!", "hey", "hi!", "quick q", "got a sec?", "hello"])
        out.append(_msg(ctx, comm, S, clock.at(start), style_chat(greet, voice, keep, rng)))
    if comm.extra.get("away"):
        out.append(_msg(ctx, comm, S, clock.at(start), style_chat("catching people up since a few of us are out today", voice, keep, rng)))
    gaps = coverage_gaps(ctx, comm, " ".join(ln.text for ln, _ in lines) + " " + " ".join(ctx.full(p) for p in people))
    for g in gap_lines(ctx, gaps, rng, "written"):
        lines.append((Line(S, g), ""))
    parent_idx: int | None = None
    for ln, prefix in lines:
        speaker = ln.speaker if ln.speaker in people else S
        ev = ctx.events.get(ln.act or "")
        t_ev = parse_dt(ev["t"]) if ev else None
        txt = style_chat(prefix + (lower_first(ln.text) if prefix else ln.text), ctx.voice(speaker), keep, rng)
        extra: dict = {}
        if not dm and parent_idx is not None and rng.random() < 0.35:
            extra["thread_of"] = parent_idx
        edited = _edit(ctx, ev, txt, rng)
        if edited:
            extra["edited"] = True
            extra["original"] = edited
        if rng.random() < 0.25:
            reactors = [p for p in people if p != speaker][:3]
            if reactors:
                extra["reactions"] = [{"emoji": rng.choice(REACTIONS),
                                       "users": [ctx.handle(p) for p in rng.sample(reactors, rng.randint(1, len(reactors)))]}]
        anchor = t_ev - dt.timedelta(seconds=rng.randint(30, 90)) if t_ev is not None else None
        out.append(_msg(ctx, comm, speaker, clock.at(anchor, gap=(10, 60)), txt, **extra))
        if parent_idx is None and not dm:
            parent_idx = len(out) - 1
        if others and rng.random() < 0.45:
            replier = rng.choice([p for p in people if p != speaker] or [S])
            ack = style_chat(rng.choice(CHAT_ACKS), ctx.voice(replier), keep, rng)
            th = len(out) - 1 if not dm and rng.random() < 0.6 else None
            out.append(_msg(ctx, comm, replier, clock.at(gap=(5, 25)), ack, thread_of=th))
    for sec in comm.secrets:
        if not any(sec in m["text"] for m in out):
            out.append(_msg(ctx, comm, S, clock.at(), f"link for later: {sec}"))
    return out


def _edit(ctx: RenderContext, ev: dict | None, text: str, rng: random.Random) -> str | None:
    """The earlier version of an edited message, or None.

    A message that states a date is sometimes edited to fix it (the fact changed after
    posting: the original names a different day); other messages occasionally fix a typo."""
    if ev is None:
        return None
    due = ev.get("due") if ev["type"] == "commitment.create" else (ev.get("changes") or {}).get("due")
    if due and rng.random() < 0.45:
        from wcb.util.dates import add_days

        low = text.lower()
        for style in range(4):
            w = day_words(due, style)
            i = low.find(w.lower())
            if i >= 0:
                wrong = day_words(add_days(due, rng.choice([-1, 1, 2])), style)
                if text[i:i + len(w)].islower():
                    wrong = wrong.lower()
                return text[:i] + wrong + text[i + len(w):]
    if rng.random() < 0.07:
        words = text.split(" ")
        cands = [k for k, w in enumerate(words) if len(w) >= 5 and w.isalpha()]
        if cands:
            k = rng.choice(cands)
            w = words[k]
            j = rng.randint(1, len(w) - 2)
            words[k] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
            typo = " ".join(words)
            return typo if typo != text else None
    return None


def _social(ctx: RenderContext, comm: Communication, rng: random.Random) -> tuple[list[dict], list[str]]:
    S = comm.sender
    day = comm.t[:10]
    pool = sorted(p for p, d in ctx.entity_known.items()
                  if p.startswith("p-") and d < day and p not in (S, ctx.worker)
                  and ctx.person(p).get("group") in ("central", "functional"))
    repliers = rng.sample(pool, min(len(pool), rng.randint(1, 3))) if pool else [ctx.worker]
    opener, replies = rng.choice(SOCIAL_CHAT)
    start = parse_dt(comm.t) - dt.timedelta(minutes=rng.randint(1, 12))
    clock = _Clock(start, parse_dt(comm.received_at) + dt.timedelta(minutes=30), rng)
    out = [_msg(ctx, comm, S, clock.at(start), style_chat(opener, ctx.voice(S), [], rng))]
    for p, r in zip(repliers, [x for x in replies if x], strict=False):
        out.append(_msg(ctx, comm, p, clock.at(gap=(30, 400)), style_chat(r, ctx.voice(p), [], rng), thread_of=0 if rng.random() < 0.5 else None))
    if rng.random() < 0.5:
        out[0]["reactions"] = [{"emoji": rng.choice(REACTIONS), "users": [ctx.handle(p) for p in repliers[:2]]}]
    # The export closes when the conversation does.
    end = parse_dt(comm.received_at)
    for m in out:
        if parse_dt(m["ts"]) > end:
            m["ts"] = end.isoformat()
    return out, [S, *repliers]
