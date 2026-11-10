"""Calendar renderer: iCalendar `.ics` items (docs/formats.md §1.6).

Invites and updates are `METHOD:REQUEST` (updates carry `SEQUENCE:1`), cancellations
`METHOD:CANCEL` and responses `METHOD:REPLY` with `PARTSTAT=ACCEPTED`. Times are written in UTC.
Invites carry a video join link and passcode in `DESCRIPTION`; both are planted secrets and are
written on unfolded lines so they occur literally in the file. An accepted invite is not
evidence that the meeting happened.
"""

from __future__ import annotations

import datetime as dt
import hashlib

from wcb.render.context import RenderContext, Rendered
from wcb.render.email import clean_subject
from wcb.render.phrases import Namer, Phraser, act_lines, coverage_gaps, gap_lines, sentence
from wcb.util.dates import next_business_day, parse_dt
from wcb.world.comms import Communication

METHOD = {"calendar_invite": "REQUEST", "calendar_update": "REQUEST", "calendar_cancel": "CANCEL",
          "calendar_reply": "REPLY"}


def _utc(t: str) -> str:
    return parse_dt(t).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _strip_prefix(subject: str) -> str:
    for p in ("Invite: ", "Updated: ", "Cancelled: ", "Accepted: ", "Declined: "):
        if subject.startswith(p):
            return subject[len(p):]
    return subject


def render(ctx: RenderContext, comm: Communication) -> list[Rendered]:
    aid = comm.artifacts[0]
    rng = ctx.rng(aid)
    meeting = dict(comm.extra.get("meeting") or {})
    title = meeting.get("title") or clean_subject(ctx, _strip_prefix(comm.subject or "Meeting"))
    if not meeting.get("start"):
        day = comm.t[:10]
        for _ in range(rng.randint(1, 3)):
            day = next_business_day(day)
        hh = rng.choice([9, 10, 11, 13, 14, 15, 16])
        start = f"{day}T{hh:02d}:{rng.choice(['00', '30'])}:00{ctx.tz}"
        end_dt = parse_dt(start) + dt.timedelta(minutes=rng.choice([30, 30, 45, 60]))
        meeting["start"], meeting["end"] = start, end_dt.isoformat()
    method = METHOD[comm.kind]
    organizer = meeting.get("organizer") or comm.sender or ctx.worker
    if comm.kind == "calendar_reply":
        attendees = [comm.sender or ctx.worker]
    else:
        attendees = [p for p in dict.fromkeys([*comm.to, *comm.cc]) if p and p != organizer] or [ctx.worker]
    # One UID per meeting (or meeting series): its invite, updates, cancellation and replies share it.
    uid_src = f"{ctx.seed}:{meeting['uid']}" if meeting.get("uid") else f"{ctx.seed}:{title}:{meeting['start']}:{organizer}"
    uid = hashlib.sha1(uid_src.encode()).hexdigest()[:16] + "@" + ctx.umbrella["domain"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", f"PRODID:-//{ctx.umbrella['short']}//Calendar//EN",
             f"METHOD:{method}", "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_utc(comm.t)}",
             f"DTSTART:{_utc(meeting['start'])}", f"DTEND:{_utc(meeting.get('end') or meeting['start'])}"]
    prefix = {"calendar_update": "Updated: ", "calendar_cancel": "Cancelled: ", "calendar_reply": "Accepted: "}.get(comm.kind, "")
    lines.append(f"SUMMARY:{_esc(prefix + title)}")
    lines.append(f"ORGANIZER;CN={_esc(ctx.full(organizer))}:mailto:{ctx.email(organizer)}")
    for p in attendees:
        part = "ACCEPTED" if comm.kind == "calendar_reply" else "NEEDS-ACTION"
        lines.append(f"ATTENDEE;CN={_esc(ctx.full(p))};ROLE=REQ-PARTICIPANT;PARTSTAT={part}:mailto:{ctx.email(p)}")
    if meeting.get("recurrence_id"):
        lines.append(f"RECURRENCE-ID:{_utc(meeting['recurrence_id'])}")
    seq = meeting.get("sequence")
    if comm.kind == "calendar_update":
        lines.append(f"SEQUENCE:{seq if seq else 1}")
    elif comm.kind == "calendar_cancel":
        lines += [f"SEQUENCE:{seq if seq else 1}", "STATUS:CANCELLED"]
    elif seq is not None:
        lines.append(f"SEQUENCE:{seq}")
    desc: list[str] = []
    if comm.acts:
        namer = Namer(ctx, comm, organizer, attendees[:1] if len(attendees) == 1 else [])
        ph = Phraser(ctx, comm, rng)
        agenda = []
        for a in comm.acts:
            e = ctx.events[a.event]
            if e["type"] in ("commitment.create", "decision.make"):
                agenda.append(sentence(e["what"]))
            else:
                agenda += [sentence(ln.text) for ln in act_lines(ctx, comm, ph, namer, "written", acts=[a])]
        desc.append("Agenda: " + " ".join(agenda))
        gaps = coverage_gaps(ctx, comm, title + " " + desc[0] + " " + " ".join(ctx.full(p) for p in [organizer, *attendees]))
        desc += gap_lines(ctx, gaps, rng, "written")
    elif comm.kind == "calendar_invite":
        desc.append(rng.choice(["Catch-up.", "Placeholder, agenda to follow.", "Quick sync, 30 minutes.", ""]))
    elif comm.kind == "calendar_update":
        desc.append(rng.choice(["Moved to accommodate a conflict.", "New time, same agenda.",
                                "Shifted to fit around another meeting."]))
    elif comm.kind == "calendar_cancel":
        desc.append(rng.choice(["Cancelling this one, nothing to discuss this week.", "Cancelling, a few people are out.",
                                "Not needed this time, covered in the leads call.", "Skipping today, back to normal next time."]))
    link, code = comm.extra.get("join_link"), comm.extra.get("passcode")
    if link:
        desc.append(f"Join video meeting: {link}")
    if code:
        desc.append(f"Passcode: {code}")
    desc = [d for d in desc if d]
    if desc:
        lines.append("DESCRIPTION:" + "\\n".join(_esc_keep(d, comm.secrets) for d in desc))
    if link:
        lines.append(f"LOCATION:{link}")
    lines += ["END:VEVENT", "END:VCALENDAR"]
    text = "\r\n".join(lines) + "\r\n"
    shown = (comm.subject.split(": ", 1)[0] + ": " + title) if ": " in (comm.subject or "") else (prefix + title)
    return [Rendered(aid, ".ics", shown, content=text, text=text)]


def _esc_keep(s: str, secrets: list[str]) -> str:
    """Escape for iCalendar but leave secret strings untouched (they have no special characters)."""
    out = _esc(s)
    for sec in secrets:
        if _esc(sec) != sec and _esc(sec) in out:
            out = out.replace(_esc(sec), sec)
    return out
