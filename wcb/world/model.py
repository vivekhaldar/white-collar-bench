"""World model: load `world.yaml` + `world.jsonl` and index events, entities and artifacts.

See docs/formats.md §1. The world is hidden ground truth; agents never see it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.util.dates import date_of
from wcb.util.io import read_jsonl, read_yaml
from wcb.util.text import normalize, tokens

EVENT_TYPES = {
    "entity.create",
    "fact.set",
    "commitment.create",
    "commitment.update",
    "commitment.resolve",
    "decision.make",
    "decision.reverse",
    "project.split",
    "project.merge",
    "artifact.emit",
}

CHANNEL_PREFIX = {
    "email": "em",
    "chat": "ch",
    "transcript": "mt",
    "meeting_notes": "mn",
    "document": "dc",
    "note": "nt",
    "calendar": "ca",
}
PREFIX_CHANNEL = {v: k for k, v in CHANNEL_PREFIX.items()}

ACTIVE_STATUSES = ("open", "waiting", "blocked")
CLOSED_STATUSES = ("done", "dropped")


@dataclass
class Artifact:
    id: str
    channel: str
    path: str  # relative to the world directory
    received_at: str
    reveals: list[str]
    noise: bool = False
    challenges: list[str] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    title: str = ""
    parent: str | None = None
    event_id: str = ""

    @property
    def date(self) -> str:
        return date_of(self.received_at)

    @property
    def filename(self) -> str:
        return Path(self.path).name

    def manifest_entry(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "channel": self.channel,
            "received_at": self.received_at,
            "path": self.filename,
            "title": self.title,
        }
        if self.parent:
            d["parent"] = self.parent
        return d


@dataclass
class World:
    dir: Path
    meta: dict[str, Any]
    events: list[dict[str, Any]]  # every event, in world order (t, then file order)
    artifacts: dict[str, Artifact]
    by_id: dict[str, dict[str, Any]]
    _cache: dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

    # ------------------------------------------------------------ loading
    @classmethod
    def load(cls, world_dir: str | Path) -> World:
        d = Path(world_dir).resolve()
        meta = read_yaml(d / "world.yaml") or {}
        meta = _stringify(meta)
        raw = read_jsonl(d / "world.jsonl") if (d / "world.jsonl").exists() else []
        # Stable sort by time; file order breaks ties.
        events = [e for _, e in sorted(enumerate(raw), key=lambda p: (_tkey(p[1]), p[0]))]
        by_id: dict[str, dict[str, Any]] = {}
        artifacts: dict[str, Artifact] = {}
        for e in events:
            eid = e.get("id")
            if eid:
                by_id.setdefault(eid, e)
            if e.get("type") == "artifact.emit":
                a = Artifact(
                    id=e["artifact"],
                    channel=e.get("channel", PREFIX_CHANNEL.get(e["artifact"][:2], "")),
                    path=e["path"],
                    received_at=e.get("received_at") or e["t"],
                    reveals=list(e.get("reveals", [])),
                    noise=bool(e.get("noise", False)),
                    challenges=list(e.get("challenges", [])),
                    secrets=list(e.get("secrets", [])),
                    title=e.get("title", ""),
                    parent=e.get("parent"),
                    event_id=eid or "",
                )
                artifacts.setdefault(a.id, a)
        return cls(dir=d, meta=meta, events=events, artifacts=artifacts, by_id=by_id)

    # ------------------------------------------------------------ metadata
    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.dir.name))

    @property
    def worker(self) -> str:
        return str(self.meta["worker"])

    @property
    def timezone(self) -> str:
        return str(self.meta.get("timezone", "+00:00"))

    @property
    def seed_start(self) -> str:
        return str(self.meta["seed"]["start"])

    @property
    def seed_end(self) -> str:
        return str(self.meta["seed"]["end"])

    def episode_days(self) -> list[str]:
        return [str(d) for d in self.meta.get("episode", {}).get("days", [])]

    def checkpoints(self) -> list[dict[str, Any]]:
        return [
            {**c, "id": str(c["id"]), "date": str(c["date"])} for c in self.meta.get("checkpoints", [])
        ]

    def checkpoint(self, cp_id: str) -> dict[str, Any]:
        for c in self.checkpoints():
            if c["id"] == cp_id:
                return c
        raise KeyError(f"unknown checkpoint {cp_id!r} in world {self.id}")

    def seed_dates(self) -> list[str]:
        """Dates within the seed window that have at least one artifact."""
        s, e = self.seed_start, self.seed_end
        return sorted({a.date for a in self.artifacts.values() if s <= a.date <= e})

    def all_dates(self) -> list[str]:
        """Seed dates followed by episode days (the dates gold state is built for)."""
        return sorted(set(self.seed_dates()) | set(self.episode_days()) | {self.seed_end})

    # ------------------------------------------------------------ artifacts
    def artifacts_on(self, date: str) -> list[Artifact]:
        return sorted(
            (a for a in self.artifacts.values() if a.date == date), key=lambda a: (a.received_at, a.id)
        )

    def artifacts_through(self, date: str) -> list[Artifact]:
        return sorted(
            (a for a in self.artifacts.values() if a.date <= date), key=lambda a: (a.received_at, a.id)
        )

    def known_on(self) -> dict[str, str]:
        """Event ID -> earliest date an artifact reveals it."""
        out: dict[str, str] = {}
        for a in self.artifacts.values():
            for eid in a.reveals:
                if eid not in out or a.date < out[eid]:
                    out[eid] = a.date
        return out

    def revealing_artifacts(self) -> dict[str, list[str]]:
        """Event ID -> artifact IDs that reveal it (sorted by delivery)."""
        out: dict[str, list[tuple[str, str]]] = {}
        for a in self.artifacts.values():
            for eid in a.reveals:
                out.setdefault(eid, []).append((a.received_at, a.id))
        return {k: [aid for _, aid in sorted(v)] for k, v in out.items()}

    # ------------------------------------------------------------ entities
    def entity_events(self) -> dict[str, dict[str, Any]]:
        return {e["entity"]: e for e in self.events if e.get("type") == "entity.create"}

    def entity_name(self, eid: str) -> str:
        e = self.entity_events().get(eid)
        return e["name"] if e else eid

    def alias_table(self) -> dict[str, set[str]]:
        """Normalized name or surface form -> entity IDs. Covers all entities, knowable or not."""
        table: dict[str, set[str]] = {}
        for eid, e in self.entity_events().items():
            forms = [e.get("name", "")] + list(e.get("surface_forms", []))
            email = (e.get("attrs") or {}).get("email")
            if isinstance(email, str):
                forms.append(email)
            for f in forms:
                key = normalize(f).lstrip("@")
                if key:
                    table.setdefault(key, set()).add(eid)
        return table

    def form_first_seen(self) -> dict[str, dict[str, str]]:
        """Entity ID -> {surface form -> date of the first artifact whose text uses it}.

        Surface forms carry no reveal record of their own, so this is how a form's first use
        in the inputs is found. A form is used when it occurs as whole words, case- and
        accent-insensitively, with a leading "the" optional; an email address, domain or
        `@handle` must occur literally. Text is read as `wcb world check` reads it (text
        files and the XML of Office files). Forms that no artifact uses are absent. Computed
        once per loaded world.
        """
        if "form_first_seen" in self._cache:
            return self._cache["form_first_seen"]
        from wcb.world.check import artifact_text  # check imports this module

        pending = {
            (eid, f)
            for eid, e in self.entity_events().items()
            for f in e.get("surface_forms") or []
            if isinstance(f, str) and f.strip()
        }
        out: dict[str, dict[str, str]] = {}
        for a in sorted(self.artifacts.values(), key=lambda a: (a.received_at, a.id)):
            if not pending:
                break
            text = artifact_text(self.dir / a.path)
            if not text:
                continue
            low = normalize(text)
            words = f" {' '.join(tokens(text, drop_stopwords=False))} "
            for eid, form in sorted(pending):
                if _uses_form(low, words, form):
                    out.setdefault(eid, {})[form] = a.date
                    pending.discard((eid, form))
        self._cache["form_first_seen"] = out
        return out


def _uses_form(low: str, words: str, form: str) -> bool:
    """Whether normalized text `low` (with its word string `words`) uses a surface form."""
    form = normalize(form)
    if " " not in form and ("@" in form or "." in form):
        return bool(re.search(rf"(?<![\w.-]){re.escape(form)}(?![\w-]|\.\w)", low))
    phrase = " ".join(tokens(form, drop_stopwords=False))
    if phrase.startswith("the "):
        phrase = phrase[4:]
    return bool(phrase) and f" {phrase} " in words


def _tkey(e: dict[str, Any]) -> str:
    """Sort key for event time. Times share one offset per world, so ISO strings sort correctly."""
    return str(e.get("t", ""))


def _stringify(obj: Any) -> Any:
    import datetime as _dt

    if isinstance(obj, dict):
        return {k: _stringify(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_stringify(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj
