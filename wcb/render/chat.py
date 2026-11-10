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
    CHAT_CHIME,
    CHAT_SMALL,
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
        # Handles are unique, first names are not (two Jurgens must not share a DM).
        channel = "dm-" + "-".join(sorted(_slug(ctx.handle(p).lstrip("@")) for p in people))
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
    anchors = [_anchor(ctx, comm, ln.act, rng) for ln, _ in lines if ln.act]
    first = min(anchors) if anchors else parse_dt(comm.t)
    start = first - dt.timedelta(seconds=rng.randint(90, 400))
    clock = _Clock(start, end, rng)
    out: list[dict] = []
    voice = ctx.voice(S)
    if rng.random() < 0.45 and dm:
        greet = rng.choice(["morning!", "hey", "hi!", "quick q", "got a sec?", "hello"])
        if parse_dt(comm.t).hour >= 12 and greet == "morning!":
            greet = "hey"
        out.append(_msg(ctx, comm, S, clock.at(start), style_chat(greet, voice, keep, rng)))
        if others and rng.random() < 0.5:
            out.append(_msg(ctx, comm, others[0], clock.at(gap=(20, 90)),
                            style_chat(rng.choice(["hey", "hi", "yep, go ahead", "sure, what's up?"]),
                                       ctx.voice(others[0]), keep, rng)))
    if comm.extra.get("away"):
        out.append(_msg(ctx, comm, S, clock.at(start), style_chat("catching people up since a few of us are out today", voice, keep, rng)))
    gaps = coverage_gaps(ctx, comm, " ".join(ln.text for ln, _ in lines) + " " + " ".join(ctx.full(p) for p in people))
    for g in gap_lines(ctx, gaps, rng, "written"):
        lines.append((Line(S, g), ""))
    parent_idx: int | None = None
    for ln, prefix in lines:
        speaker = ln.speaker if ln.speaker in people else S
        ev = ctx.events.get(ln.act or "")
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
        # A message is never earlier than what it reports; a restatement is posted when the thread is.
        anchor = _anchor(ctx, comm, ln.act, rng) if ln.act else None
        out.append(_msg(ctx, comm, speaker, clock.at(anchor, gap=(10, 60)), txt, **extra))
        idx = len(out) - 1
        if parent_idx is None and not dm:
            parent_idx = idx
        if others and rng.random() < 0.85:
            replier = rng.choice([p for p in people if p != speaker] or [S])
            ack = style_chat(rng.choice(_acks(ctx, comm, ev, speaker, replier)), ctx.voice(replier), keep, rng)
            th = idx if not dm and rng.random() < 0.6 else None
            out.append(_msg(ctx, comm, replier, clock.at(gap=(5, 90)), ack, thread_of=th))
        if not dm and len(people) > 2 and rng.random() < 0.65:
            # Other channel members chime in under the post.
            for p in rng.sample([x for x in people if x != speaker], min(len(people) - 1, rng.randint(1, 3))):
                out.append(_msg(ctx, comm, p, clock.at(gap=(30, 600)),
                                style_chat(rng.choice(CHAT_CHIME), ctx.voice(p), keep, rng), thread_of=idx))
    if dm and others and rng.random() < 0.6:
        a, b = rng.choice(CHAT_SMALL)
        first_sp = rng.choice([S, others[0]])
        second = others[0] if first_sp == S else S
        out.append(_msg(ctx, comm, first_sp, clock.at(gap=(30, 300)), style_chat(a, ctx.voice(first_sp), keep, rng)))
        out.append(_msg(ctx, comm, second, clock.at(gap=(20, 240)), style_chat(b, ctx.voice(second), keep, rng)))
    for sec in comm.secrets:
        if not any(sec in m["text"] for m in out):
            out.append(_msg(ctx, comm, S, clock.at(), f"link for later: {sec}"))
    return out


def _anchor(ctx: RenderContext, comm: Communication, eid: str | None, rng: random.Random) -> dt.datetime:
    """When the message conveying `eid` is posted: at the event, or, for a restatement of an event
    from an earlier day, shortly before the thread's own time on its own day."""
    t_ev = parse_dt(ctx.events[eid]["t"]) if eid else parse_dt(comm.t)
    if eid and ctx.events[eid]["t"][:10] < comm.t[:10]:
        own = parse_dt(comm.t) - dt.timedelta(seconds=rng.randint(60, 900))
        day_start = parse_dt(comm.t[:10] + "T07:30:00" + comm.t[19:])
        return max(own, day_start, t_ev)
    return t_ev


def _acks(ctx: RenderContext, comm: Communication, ev: dict | None, speaker: str, replier: str) -> tuple[str, ...]:
    """Acknowledgements that fit the message: only a debtor agrees to do something, and only
    when the loop counts as agreed."""
    if ev is None:
        return CHAT_ACKS["fyi"]
    et = ev["type"]
    if et == "commitment.create":
        D, Cr = ev["debtor"], ev["creditor"]
        if replier == D and speaker != D:
            return CHAT_ACKS["asked_yes"] if ctx.accepted_at(ev["commitment"], comm) else CHAT_ACKS["asked_maybe"]
        if replier == Cr:
            return CHAT_ACKS["promised_to"]
        return CHAT_ACKS["fyi"]
    if et == "commitment.resolve":
        lp = ctx.loop_before.get(ev["id"]) or {}
        if ev.get("status") == "done" and replier == lp.get("creditor"):
            return CHAT_ACKS["done_for"]
        return CHAT_ACKS["fyi"]
    if et in ("decision.make", "decision.reverse"):
        return CHAT_ACKS["decision"]
    return CHAT_ACKS["fyi"]


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
    start = parse_dt(comm.t) - dt.timedelta(minutes=rng.randint(1, 12))
    minute, wd = start.hour * 60 + start.minute, start.weekday()
    fits = [x for x in SOCIAL_CHAT if x[2] <= minute <= x[3] and (x[4] is None or wd in x[4])]
    fits = fits or [x for x in SOCIAL_CHAT if x[4] is None]
    opener, replies = rng.choice(fits)[:2]
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
