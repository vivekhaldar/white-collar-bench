"""Tiny authoring DSL for the hand-authored pilot world.

Events are declared with symbolic keys; `build.py` sorts them by time, assigns the public IDs
(e-NNNN, c-NNN, d-NNN, <prefix>-NNNN) and writes world.jsonl, artifacts.plan.jsonl and
questions.yaml. Nothing here is visible to agents.
"""

from __future__ import annotations

from typing import Any

TZ = "-08:00"

EVENTS: list[dict[str, Any]] = []      # every event incl. artifact.emit, in declaration order
ARTS: dict[str, dict[str, Any]] = {}   # artifact sym -> artifact.emit event
KEYS: dict[str, dict[str, Any]] = {}   # event key -> event
COMMITS: dict[str, dict[str, Any]] = {}  # commitment sym -> create event
DECISIONS: dict[str, dict[str, Any]] = {}  # decision sym -> make event
PEOPLE: dict[str, dict[str, Any]] = {}  # entity id -> cast info for the bible
QUESTIONS: list[dict[str, Any]] = []
UNOBSERVABLE: dict[str, str] = {}      # event key -> why it is never revealed
UNREVEALED: dict[str, str] = {}        # event key -> resolution that happened but no artifact shows

EXT = {"email": "eml", "chat": "json", "transcript": "vtt", "meeting_notes": "md", "note": "md", "calendar": "ics"}
PREFIX = {"email": "em", "chat": "ch", "transcript": "mt", "meeting_notes": "mn", "document": "dc", "note": "nt", "calendar": "ca"}


def T(s: str) -> str:
    """'2027-03-01 09:15' -> '2027-03-01T09:15:00-08:00'."""
    d, hm = s.split(" ")
    if hm.count(":") == 1:
        hm += ":00"
    return f"{d}T{hm}{TZ}"


def _add(key: str, ev: dict[str, Any]) -> dict[str, Any]:
    if key in KEYS:
        raise ValueError(f"duplicate event key {key}")
    ev["_key"] = key
    ev["_seq"] = len(EVENTS)
    EVENTS.append(ev)
    KEYS[key] = ev
    return ev


# ------------------------------------------------------------------ entities
def person(pid, t, name, forms, *, org=None, role=None, email=None, rel=None, summary, voice="",
           minor=False, group="", note=""):
    attrs: dict[str, Any] = {}
    if minor:
        attrs = {"_minor": True}
        if note:
            attrs["_note"] = note
    else:
        if org:
            attrs["org"] = org
        if role:
            attrs["role"] = role
        if email:
            attrs["email"] = email
        if rel:
            attrs["relationship"] = rel
    ev = _add(pid, {"t": T(t), "type": "entity.create", "summary": summary, "entity": pid, "kind": "person",
                    "name": name, "surface_forms": forms, "attrs": attrs})
    PEOPLE[pid] = {"name": name, "forms": forms, "org": org, "role": role, "rel": rel, "minor": minor,
                   "voice": voice, "group": group, "email": email}
    return ev


def org(oid, t, name, forms, *, kind, domain=None, summary):
    attrs = {"kind": kind}
    if domain:
        attrs["domain"] = domain
    return _add(oid, {"t": T(t), "type": "entity.create", "summary": summary, "entity": oid, "kind": "org",
                      "name": name, "surface_forms": forms, "attrs": attrs})


def project(pid, t, name, forms, *, summary, state, **attrs):
    attrs = {k: v for k, v in attrs.items() if v is not None}
    attrs["summary"] = state
    ev = _add(pid, {"t": T(t), "type": "entity.create", "summary": summary, "entity": pid, "kind": "project",
                    "name": name, "surface_forms": forms, "attrs": attrs, "project": pid})
    return ev


def fact(key, t, subject, attribute, value, summary, *, project=None, unobservable=None):
    ev = {"t": T(t), "type": "fact.set", "summary": summary, "subject": subject, "attribute": attribute,
          "value": value}
    if project or subject.startswith("pr-"):
        ev["project"] = project or subject
    _add(key, ev)
    if unobservable:
        UNOBSERVABLE[key] = unobservable
    return ev


# ------------------------------------------------------------------ commitments
def commit(sym, t, kind, what, debtor, creditor, *, project, basis, keywords, summary, status="open",
           due=None, accepted=True, others=None):
    assert kind in ("task", "ask"), kind
    assert basis in ("sent", "received", "reported", "scheduled", "inferred"), basis
    assert status in ("open", "waiting", "blocked"), status
    assert len(keywords) >= 2, sym
    ev = _add("c:" + sym, {"t": T(t), "type": "commitment.create", "summary": summary, "commitment": sym,
                           "kind": kind, "what": what, "debtor": debtor, "creditor": creditor,
                           "others": list(others or []), "project": project, "status": status, "due": due,
                           "accepted": accepted, "basis": basis, "keywords": keywords})
    COMMITS[sym] = ev
    return ev


def cupd(key, t, sym, changes, summary, *, unrevealed=None):
    ev = _add(key, {"t": T(t), "type": "commitment.update", "summary": summary, "commitment": sym,
                    "changes": changes, "project": COMMITS[sym]["project"]})
    if unrevealed:
        UNREVEALED[key] = unrevealed
    return ev


def cres(key, t, sym, status, summary, *, unrevealed=None):
    assert status in ("done", "dropped")
    ev = _add(key, {"t": T(t), "type": "commitment.resolve", "summary": summary, "commitment": sym,
                    "status": status, "project": COMMITS[sym]["project"]})
    if unrevealed:
        UNREVEALED[key] = unrevealed
    return ev


# ------------------------------------------------------------------ decisions and restructuring
def decide(sym, t, what, by, *, project, keywords, summary):
    ev = _add("d:" + sym, {"t": T(t), "type": "decision.make", "summary": summary, "decision": sym,
                           "what": what, "by": by, "project": project, "keywords": keywords})
    DECISIONS[sym] = ev
    return ev


def reverse(key, t, sym, reason, summary):
    return _add(key, {"t": T(t), "type": "decision.reverse", "summary": summary, "decision": sym,
                      "reason": reason, "project": DECISIONS[sym]["project"]})


def split(key, t, project, into, moves, summary):
    return _add(key, {"t": T(t), "type": "project.split", "summary": summary, "project": project,
                      "into": into, "moves": moves})


def merge(key, t, projects, into, summary):
    return _add(key, {"t": T(t), "type": "project.merge", "summary": summary, "projects": projects,
                      "into": into, "project": into})


# ------------------------------------------------------------------ artifacts
def art(sym, channel, received, title, reveals, *, ext=None, challenges=(), secrets=(), noise=False,
        parent=None, sent=None, frm=None, to=None, cc=None, subject=None, participants=None, thread=(),
        length="short", must_not_say=(), noise_notes="", style="", fmt=None, low_value=None):
    """Declare an artifact. `reveals` items are event keys or (key, how, must_say) tuples."""
    ext = ext or EXT[channel]
    rev = []
    for r in reveals:
        if isinstance(r, str):
            rev.append({"key": r, "how": None, "say": None})  # default chosen in build.default_how
        else:
            k, how = r[0], r[1]
            say = r[2] if len(r) > 2 else None
            rev.append({"key": k, "how": how, "say": say})
    ev = _add("art:" + sym, {"t": T(received), "type": "artifact.emit", "artifact": sym, "channel": channel,
                             "_ext": ext, "received_at": T(received), "_reveals": rev, "noise": noise,
                             "challenges": list(challenges), "secrets": list(secrets), "title": title,
                             "parent": parent,
                             "_plan": {"sent_at": T(sent) if sent else None, "from": frm, "to": to, "cc": cc,
                                       "subject_or_title": subject or title, "participants": participants,
                                       "thread": list(thread), "length": length,
                                       "must_not_say": list(must_not_say), "noise_notes": noise_notes,
                                       "style": style, "format": fmt or ext,
                                       "low_value": bool(noise if low_value is None else low_value)}})
    ARTS[sym] = ev
    return ev


# ------------------------------------------------------------------ questions
def q(cp, template, params=None, *, text=None, challenges=(), name_form=None, note="", extra_rubric=None):
    """A question spec. `extra_rubric` items may cite artifacts by their authoring symbol in `support`."""
    QUESTIONS.append({"checkpoint": cp, "template": template, "params": dict(params or {}), "text": text,
                      "challenges": list(challenges), "name_form": name_form, "_note": note,
                      "extra_rubric": list(extra_rubric or [])})
