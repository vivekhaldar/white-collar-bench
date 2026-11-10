"""Communications: the unit the simulator hands to the renderers (docs/generator.md, "Simulator").

A **communication** is one email, chat thread, meeting, document, note or calendar item. It
names the world events it reveals as **acts**, each with a `how` that controls the phrasing,
and the artifact IDs the renderers will write for it. A meeting can yield a transcript, notes
or both, according to its coverage.

`to_dict` / `from_dict` round-trip losslessly, so communications can be cached as JSON.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

KINDS = (
    "email",
    "chat_dm",
    "chat_channel",
    "meeting",
    "document",
    "note",
    "voice_memo",
    "calendar_invite",
    "calendar_update",
    "calendar_cancel",
    "calendar_reply",
)

# Medium of a communication kind. Meetings become transcript and/or meeting_notes artifacts.
CHANNEL_OF_KIND = {
    "email": "email",
    "chat_dm": "chat",
    "chat_channel": "chat",
    "meeting": "meeting",
    "document": "document",
    "note": "note",
    "voice_memo": "note",
    "calendar_invite": "calendar",
    "calendar_update": "calendar",
    "calendar_cancel": "calendar",
    "calendar_reply": "calendar",
}

HOWS = ("direct", "hedged", "implied", "indirect", "second_hand", "correction")

# Meeting coverage (docs/calibration.md "Meeting coverage"): which artifacts a meeting yields.
COVERAGE_PREFIXES = {
    "transcript": ["mt"],
    "transcript+recap": ["mt", "mn"],
    "recap": ["mn"],
    "debrief": ["mn"],  # the worker's own written notes after an unrecorded meeting
    "voice_debrief": ["nt"],  # a spoken brain-dump, transcribed into a worker note
}

KIND_PREFIX = {
    "email": "em",
    "chat_dm": "ch",
    "chat_channel": "ch",
    "document": "dc",
    "note": "nt",
    "voice_memo": "nt",
    "calendar_invite": "ca",
    "calendar_update": "ca",
    "calendar_cancel": "ca",
    "calendar_reply": "ca",
}

# Artifact channel (docs/formats.md) for each artifact ID prefix.
PREFIX_CHANNEL = {
    "em": "email",
    "ch": "chat",
    "mt": "transcript",
    "mn": "meeting_notes",
    "dc": "document",
    "nt": "note",
    "ca": "calendar",
}


def artifact_prefixes(kind: str, coverage: str | None = None) -> list[str]:
    """Artifact ID prefixes a communication of `kind` produces, in file order."""
    if kind == "meeting":
        return list(COVERAGE_PREFIXES[coverage or "transcript"])
    return [KIND_PREFIX[kind]]


@dataclass
class Act:
    """One revealed world event and how the communication conveys it.

    `by` optionally names the person who conveys it (a meeting speaker, or the reporter of a
    second-hand account). Omitted from `to_dict` when unset.
    """

    event: str
    how: str = "direct"
    by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"event": self.event, "how": self.how}
        if self.by:
            d["by"] = self.by
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Act:
        return cls(event=str(d["event"]), how=str(d.get("how", "direct")), by=d.get("by"))


@dataclass
class Communication:
    """An email, chat thread, meeting, document, note or calendar item (docs/generator.md).

    Beyond the documented fields, `parent` names the carrying communication of an attachment
    and `extra` holds renderer hints (meeting coverage and times, name forms to use, version
    labels, noise category, allusions to unobservable facts...). Times are ISO strings with the
    world's offset; `received_at` differs from `t` only for batch catch-up deliveries.
    """

    id: str
    t: str
    channel: str
    kind: str
    sender: str | None = None
    to: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)
    project: str | None = None
    thread: str | None = None
    subject: str = ""
    acts: list[Act] = field(default_factory=list)
    noise: bool = False
    draft: bool = False
    secrets: list[str] = field(default_factory=list)
    received_at: str = ""
    artifacts: list[str] = field(default_factory=list)
    challenges: list[str] = field(default_factory=list)
    parent: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------ helpers
    @property
    def date(self) -> str:
        """Delivery date (the inbox directory the artifacts land in)."""
        return (self.received_at or self.t)[:10]

    def reveals(self) -> list[str]:
        """Event IDs carried by the acts, in act order, without duplicates."""
        out: list[str] = []
        for a in self.acts:
            if a.event not in out:
                out.append(a.event)
        return out

    def people(self) -> list[str]:
        """Sender, recipients and participants, in that order, without duplicates."""
        out: list[str] = []
        for p in [self.sender, *self.to, *self.cc, *self.participants]:
            if p and p not in out:
                out.append(p)
        return out

    def tag(self, *tags: str) -> None:
        for t in tags:
            if t not in self.challenges:
                self.challenges.append(t)

    def prefixes(self) -> list[str]:
        return artifact_prefixes(self.kind, self.extra.get("coverage"))

    # ------------------------------------------------------------ (de)serialization
    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "t": self.t,
            "channel": self.channel,
            "kind": self.kind,
            "sender": self.sender,
            "to": list(self.to),
            "cc": list(self.cc),
            "participants": list(self.participants),
            "project": self.project,
            "thread": self.thread,
            "subject": self.subject,
            "acts": [a.to_dict() for a in self.acts],
            "noise": self.noise,
            "draft": self.draft,
            "secrets": list(self.secrets),
            "received_at": self.received_at,
            "artifacts": list(self.artifacts),
            "challenges": list(self.challenges),
            "parent": self.parent,
            "extra": _plain(self.extra),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Communication:
        return cls(
            id=str(d["id"]),
            t=str(d["t"]),
            channel=str(d.get("channel") or CHANNEL_OF_KIND.get(str(d.get("kind")), "")),
            kind=str(d["kind"]),
            sender=d.get("sender"),
            to=list(d.get("to") or []),
            cc=list(d.get("cc") or []),
            participants=list(d.get("participants") or []),
            project=d.get("project"),
            thread=d.get("thread"),
            subject=str(d.get("subject") or ""),
            acts=[Act.from_dict(a) for a in d.get("acts") or []],
            noise=bool(d.get("noise", False)),
            draft=bool(d.get("draft", False)),
            secrets=list(d.get("secrets") or []),
            received_at=str(d.get("received_at") or d["t"]),
            artifacts=list(d.get("artifacts") or []),
            challenges=list(d.get("challenges") or []),
            parent=d.get("parent"),
            extra=dict(d.get("extra") or {}),
        )


def _plain(obj: Any) -> Any:
    """Copy nested dicts/lists so serialized output never aliases internal state."""
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj
