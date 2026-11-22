"""Notes renderer: meeting notes, AI recaps, the worker's own notes and voice memos.

- **AI recap** (`mn`, coverage `recap` or `transcript+recap`): a notetaker's summary with
  attendees, summary bullets, decisions and action items. Recaps sometimes state one thing
  confidently and wrongly: an attendee who was not there, a misspelled name repeated from the
  transcript, or a follow-up meeting nobody booked.
- **Debrief** (`mn`, coverage `debrief`): the worker's terse notes after an unrecorded meeting.
- **Worker notes** (`nt`, kinds `note` and `voice_memo`, coverage `voice_debrief`): shorthand,
  one-line directives, and transcribed spoken brain-dumps.
- **Portfolio map** (`nt`, the first seed day): the worker's map of projects, people and
  long-running items, which introduces the world.
"""

from __future__ import annotations

import random
import re
from pathlib import Path

from wcb.render.context import RenderContext, Rendered, day_words, time_words
from wcb.render.phrases import (
    Namer,
    Phraser,
    act_lines,
    coverage_gaps,
    gap_lines,
    lower_first,
    lowercase_keep,
    upper_first,
)
from wcb.render.transcript import attendee_list, participants
from wcb.world.comms import Communication
from wcb.world.simulator import phase_phrase


# ---------------------------------------------------------------- meeting notes
def render_meeting_notes(ctx: RenderContext, comm: Communication, aid: str) -> Rendered:
    cov = comm.extra.get("coverage")
    if cov == "debrief":
        return _debrief(ctx, comm, aid)
    return _recap(ctx, comm, aid)


def _recap(ctx: RenderContext, comm: Communication, aid: str) -> Rendered:
    rng = ctx.rng(aid)
    people = participants(ctx, comm)
    title = comm.subject or "Meeting"
    namer = Namer(ctx, comm, None, [], third_person=True)
    ph = Phraser(ctx, comm, rng)
    tool = f"{ctx.umbrella['short']} Meeting Assistant"
    summary, decisions, actions = [], [], []
    for a in comm.acts:
        e = ctx.events[a.event]
        if e["type"] == "entity.create" and e["kind"] != "project":
            continue
        if e["type"] == "commitment.create":
            due = f" (due {day_words(e['due'], 1)})" if e.get("due") else ""
            who = ctx.full(e["debtor"])
            done = any(ctx.events[b.event]["type"] == "commitment.resolve"
                       and ctx.events[b.event]["commitment"] == e["commitment"] for b in comm.acts)
            box = "[x]" if done else "[ ]"
            accepted = ctx.accepted_at(e["commitment"], comm)
            if not accepted:
                actions.append(f"- {box} (suggested) {who}: {e['what']}{due}")
            else:
                actions.append(f"- {box} {who}: {e['what']}{due}{' (done during the meeting)' if done else ''}")
            summary.append("- " + _topic_line(ctx, e, accepted, rng))
            continue
        if e["type"] == "commitment.resolve" and any(
                ctx.events[b.event]["type"] == "commitment.create"
                and ctx.events[b.event]["commitment"] == e["commitment"] for b in comm.acts):
            continue
        lines = ph.lines(a, namer, "recap")
        for ln in lines:
            if not ln.text:
                continue
            (decisions if e["type"] in ("decision.make", "decision.reverse") else summary).append("- " + upper_first(ln.text))
    shown = list(people)
    wrong = ""
    mangled = ctx.mangled.get(comm.id, {})
    r = rng.random()
    if r < 0.25 and mangled:
        f, m = sorted(mangled.items())[0]
        # repeat the transcript's misspelling, confidently
        for i, s in enumerate(summary):
            if re.search(rf"\b{re.escape(f)}\b", s):
                summary[i] = re.sub(rf"\b{re.escape(f)}\b", m, s, count=1)
                break
        else:
            wrong = f"- {m} raised a question about timelines."
    elif r < 0.45:
        extra = [p for p in sorted(ctx.entity_known) if p.startswith("p-") and p not in people
                 and ctx.entity_known[p] <= comm.date and ctx.person(p).get("group") in ("central", "unit")]
        if extra:
            shown.append(rng.choice(extra))
    elif r < 0.6:
        wrong = f"- Next meeting: {rng.choice(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])} at the usual time."
    proj = ctx.pname(comm.project)
    if not summary:
        summary.append(rng.choice([f"- Round of updates{' on ' + proj if proj else ''}; see action items.",
                                   "- Short status check-in."])
                       if actions or decisions else "- General discussion; no new items.")
    if proj and rng.random() < 0.6:
        summary.insert(0, rng.choice([f"- The meeting focused on {proj}.", f"- Mostly {proj} updates.",
                                      f"- Check-in on {proj}."]))
    date = day_words(comm.t[:10], 0) + " " + comm.t[:4]
    lines = [f"# {title}", "",
             f"{date}, {time_words(comm.extra.get('start') or comm.t)} to {time_words(comm.t)}. Summarized by {tool}.", "",
             f"**Attendees:** {attendee_list(ctx, shown)}", "", "## Summary", "", *summary]
    if wrong:
        lines.append(wrong)
    if decisions:
        lines += ["", "## Decisions", "", *decisions]
    lines += ["", "## Action items", "", *(actions or ["- None captured."])]
    text = "\n".join(lines)
    gaps = coverage_gaps(ctx, comm, text)
    extra_lines = gap_lines(ctx, gaps, rng, "note")
    if extra_lines:
        text += "\n\n## Context\n\n" + "\n".join(extra_lines)
    text += "\n\n_This summary was generated automatically and may contain errors._\n"
    return Rendered(aid, ".md", f"Recap: {title}", content=text, text=text)


def _topic_line(ctx: RenderContext, e: dict, accepted: bool, rng: random.Random) -> str:
    """A summary bullet for a loop the meeting raised (the action item carries the details)."""
    from wcb.render.phrases import subject_with_keywords

    subj = subject_with_keywords(ctx, e["what"], list(e.get("keywords") or []))
    D, Cr = ctx.full(e["debtor"]), ctx.full(e["creditor"])
    if not accepted:
        return rng.choice([f"{Cr} raised {subj}; whether {D} picks it up is still open.",
                           f"Discussed {subj}. No owner agreed yet."])
    if e.get("kind") == "ask":
        return rng.choice([f"{Cr} raised {subj}; {D} is picking it up.", f"Discussed {subj}; {D} is picking it up."])
    return rng.choice([f"{D} offered to handle {subj}.", f"Discussed {subj}; {D} has it."])


def _debrief(ctx: RenderContext, comm: Communication, aid: str) -> Rendered:
    rng = ctx.rng(aid)
    people = participants(ctx, comm)
    title = comm.subject or "Meeting"
    namer = Namer(ctx, comm, ctx.worker, [])
    ph = Phraser(ctx, comm, rng)
    lines = [ln.text for ln in act_lines(ctx, comm, ph, namer, "note")]
    who = ", ".join(ctx.full(p) if p in namer.fresh else ctx.form(p, comm) for p in people if p != ctx.worker)
    out = [f"{title.lower() if rng.random() < 0.5 else title} - {day_words(comm.t[:10], 1)}", f"w/ {who}", ""]
    out += lines or ["- nothing new, mostly status"]
    text = "\n".join(out)
    gaps = coverage_gaps(ctx, comm, text)
    text += "\n" + "\n".join(gap_lines(ctx, gaps, rng, "note")) if any(gaps.values()) else ""
    text = text.rstrip() + "\n"
    return Rendered(aid, ".md", f"Notes: {title}", content=text, text=text)


# ---------------------------------------------------------------- worker notes
def render_note(ctx: RenderContext, comm: Communication, aid: str) -> Rendered:
    rng = ctx.rng(aid)
    if comm.subject == "Portfolio map":
        return _portfolio(ctx, comm, aid, rng)
    spoken = comm.kind == "voice_memo" or comm.extra.get("coverage") == "voice_debrief"
    namer = Namer(ctx, comm, ctx.worker, [])
    ph = Phraser(ctx, comm, rng)
    lines = [ln.text for ln in act_lines(ctx, comm, ph, namer, "written" if spoken else "note")]
    gaps = coverage_gaps(ctx, comm, "\n".join(lines))
    lines += gap_lines(ctx, gaps, rng, "written" if spoken else "note")
    keep = list(comm.secrets)
    if comm.kind == "meeting":
        title = f"Voice debrief: {comm.subject}"
        intro = f"ok, quick debrief from the {comm.subject.lower()}."
    elif spoken:
        title = comm.subject or "Voice memo"
        intro = rng.choice(["ok, few things before I forget.", "right, brain dump.", "notes to self, um,"])
    else:
        title = comm.subject or "Notes"
    if spoken:
        fillers = ["um,", "uh,", "so", "and", "also", "", "", "okay so", "then", "oh and"]
        parts = [intro]
        for k, ln in enumerate(lines):
            s = ln[2:] if ln.startswith("- ") else ln
            # The first thought never opens with a connective ("and decided...").
            f = rng.choice(["", "", "so", "first,", "okay,"] if k == 0 else fillers)
            parts.append((f + " " + lower_first(s) if f else s).rstrip(".") + ".")
        speech = " ".join(p.strip() for p in parts if p.strip())
        speech = lowercase_keep(speech, keep)
        text = f"Voice memo, transcribed {day_words(comm.t[:10], 1)} {time_words(comm.t)}\n\n{speech}\n"
    else:
        head = rng.choice([f"{day_words(comm.t[:10], 1).lower()}", f"# {title}", f"{title.lower()}"])
        body = lines or ["- nothing urgent"]
        if rng.random() < 0.5:
            body = [lowercase_keep(b, keep) for b in body]
        text = head + "\n\n" + "\n".join(body) + "\n"
    return Rendered(aid, ".md", title, content=text, text=text)


def _portfolio(ctx: RenderContext, comm: Communication, aid: str, rng: random.Random) -> Rendered:
    namer = Namer(ctx, comm, ctx.worker, [])
    namer.fresh = set()
    ph = Phraser(ctx, comm, rng)
    revealed = [ctx.events[a.event] for a in comm.acts]
    projects = [e for e in revealed if e["type"] == "entity.create" and e["kind"] == "project"]
    persons = [e for e in revealed if e["type"] == "entity.create" and e["kind"] == "person"]
    orgs = [e for e in revealed if e["type"] == "entity.create" and e["kind"] == "org"]
    loops = [a for a in comm.acts if ctx.events[a.event]["type"] == "commitment.create"]
    out = [f"# Portfolio map ({day_words(comm.t[:10], 3)})", "",
           f"Where things stand across my projects. Org: {ctx.umbrella['name']}; my team: "
           f"{ctx.central['name']} ({ctx.central['short']}).", ""]
    for e in projects:
        a = e.get("attrs") or {}
        forms = [f for f in e.get("surface_forms") or [] if not f.startswith("@")]
        out.append(f"## {e['name']}")
        if forms:
            out.append(f"aka {', '.join(forms[:3])}")
        out.append("")
        out.append(str(a.get("summary", "")))
        out.append("")
        def who(pid: str | None) -> str:
            return "me" if pid == ctx.worker else ctx.full(pid)

        bits = [f"owner: {who(a.get('owner'))}"]
        if a.get("sponsor"):
            bits.append(f"sponsor: {who(a['sponsor'])}")
        if a.get("phase"):
            bits.append(f"stage: {phase_phrase(a['phase']).lower()}")
        if a.get("target_date"):
            bits.append(f"target: {day_words(a['target_date'], 3)}")
        out.append("- " + "; ".join(bits))
        mem = [ctx.full(m) for m in a.get("members") or [] if m != ctx.worker]
        if mem:
            out.append("- people: " + ", ".join(mem))
        if a.get("orgs"):
            out.append("- orgs: " + ", ".join(ctx.orgs[o]["name"] for o in a["orgs"] if o in ctx.orgs))
        out.append("")
    if loops:
        out += ["## Long-running items", ""]
        out += [ln.text for ln in act_lines(ctx, comm, ph, namer, "note", acts=loops)]
        out.append("")
    if persons:
        out += ["## Who's who", ""]
        for e in persons:
            a = e.get("attrs") or {}
            org = ctx.orgs.get(a.get("org") or "")
            nick = ctx.person(e["entity"]).get("nickname")
            aka = f" (goes by {nick})" if nick and rng.random() < 0.5 else ""
            out.append(f"- {e['name']}{aka}: {ctx.short_role(e['entity'])}{', ' + org['name'] if org else ''}")
        out.append("")
    named = "\n".join(out)
    missing = [e for e in orgs if e["name"] not in named]
    if missing:
        out += ["## Organizations", ""] + [f"- {e['name']} ({ctx.orgs[e['entity']]['kind']})" for e in missing] + [""]
    text = "\n".join(out).rstrip() + "\n"
    return Rendered(aid, ".md", "Portfolio map", content=text, text=text)


def write_contact_updates(ctx: RenderContext, world_dir: Path, emits: list[dict], last_event: int) -> list[dict]:
    """Deliver contact entries on the day each contact is first introduced, never before."""
    seen = set()
    days = {}
    for artifact in sorted(emits, key=lambda a: (a["received_at"], a["id"])):
        for eid in artifact["reveals"]:
            event = ctx.events[eid]
            if eid in seen or event.get("kind") != "person" or event["type"] != "entity.create":
                continue
            seen.add(eid)
            day = artifact["received_at"][:10]
            days.setdefault(day, []).append((artifact["received_at"], event))
    last_note = max((int(a["artifact"][3:]) for a in emits if a["artifact"].startswith("nt-")), default=0)
    updates = []
    for number, (day, contacts) in enumerate(sorted(days.items()), 1):
        aid = f"nt-{last_note + number:04d}"
        title = "Contact directory updates"
        lines = [f"# {title}", ""]
        for _, e in contacts:
            attrs = e.get("attrs", {})
            org = ctx.orgs.get(attrs.get("org"), {})
            fields = [attrs.get("role"), org.get("name"), attrs.get("relationship")]
            lines.append(f"- {e['name']}: " + " | ".join(v for v in fields if v))
        path = f"inbox/{day}/{aid}.md"
        (world_dir / path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        received = max(time for time, _ in contacts)
        updates.append({"id": f"e-{last_event + number:04d}", "type": "artifact.emit",
                        "t": received, "received_at": received, "artifact": aid, "path": path,
                        "channel": "note", "title": title, "reveals": [e["id"] for _, e in contacts],
                        "parent": None, "secrets": [], "noise": False, "challenges": []})
    return updates
