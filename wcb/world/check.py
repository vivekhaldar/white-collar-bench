"""Consistency checks for a world directory (`wcb world check`).

A world is hand-authored or generated data: `world.yaml`, `world.jsonl`, `questions.yaml` and
the artifact files under `inbox/` (docs/formats.md §1). Gold answers are derived from it
mechanically, so authoring mistakes turn directly into wrong gold. These checks catch the
mistakes that matter for grading:

- metadata: required `world.yaml` fields, a sane seed window, episode days and checkpoints;
- events: unique IDs, known types, required fields and allowed values per type (§1.2);
- references: every entity, commitment, decision and project an event names exists, and
  objects are created before they are changed;
- knowability (§1.3): an update is not revealed before the object it changes, and a loop is
  not revealed before the people and project it names;
- artifacts: ID prefix matches the channel, the file exists where `path` says, the inbox date
  matches `received_at`, deliveries fall on seed or episode days, planted secrets occur in the
  file, and no undeclared files sit in `inbox/`;
- grading aids (warnings): commitments carry at least two keywords, and each keyword occurs in
  an artifact that reveals the commitment;
- questions: unique IDs, known checkpoints and templates, and parameters naming real objects.

Each problem is an `Issue` with a stable `code`; docs/worlds.md lists them. Errors block
`wcb world build`; warnings do not.
"""

from __future__ import annotations

import html
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.util.dates import DATE_RE, parse_dt, text_variants
from wcb.util.io import read_jsonl, read_yaml
from wcb.util.issues import Issue, error, warning
from wcb.util.text import contains_phrase, normalize
from wcb.world.model import CHANNEL_PREFIX, EVENT_TYPES, World

# ---------------------------------------------------------------- vocabularies (docs/formats.md §1)
ENTITY_PREFIX = {"person": "p-", "org": "o-", "project": "pr-"}
LOOP_KINDS = ("task", "ask")
CREATE_STATUSES = ("open", "waiting", "blocked")
LOOP_STATUSES = ("open", "waiting", "blocked", "done", "dropped")
RESOLVE_STATUSES = ("done", "dropped")
BASES = ("sent", "received", "reported", "scheduled", "inferred")
UPDATE_KEYS = (
    "status",
    "due",
    "debtor",
    "creditor",
    "others",
    "what",
    "accepted",
    "project",
    "keywords",
)
# Mirrors the enums in contract/schemas/*.json, so that oracle stores validate.
RELATIONSHIPS = (
    "manager",
    "report",
    "peer",
    "stakeholder",
    "executive",
    "assistant",
    "vendor",
    "partner",
    "candidate",
    "advisor",
    "other",
)
ORG_KINDS = ("internal", "vendor", "customer", "partner", "other")
PROJECT_STATUSES = ("active", "paused", "dormant", "done", "cancelled", "merged")
CHALLENGE_TAGS = frozenset(
    """supersession reversal alias name_collision new_entity duplicate_signal implied_commitment
    weak_evidence transfer silent_closure noise unobservable draft_vs_sent acceptance_vs_occurrence
    correction restructuring endorsement worker_directive version_mismatch batch_catchup
    scattered_evidence privacy""".split()
)
CHANNEL_SUFFIXES = {
    "email": {".eml"},
    "chat": {".json"},
    "transcript": {".vtt", ".txt"},
    "meeting_notes": {".md"},
    "document": {".md", ".docx", ".xlsx", ".pptx", ".pdf"},
    "note": {".md"},
    "calendar": {".ics"},
}
# Entity-valued attributes: attribute -> kind of entity its value(s) name.
ENTITY_ATTRS = {
    "person": {"org": "org"},
    "project": {
        "owner": "person",
        "sponsor": "person",
        "members": "person",
        "orgs": "org",
        "parent": "project",
        "split_into": "project",
        "merged_into": "project",
    },
}
# Fields each event type must carry, with their JSON types (docs/formats.md §1.2).
REQUIRED_FIELDS: dict[str, dict[str, type]] = {
    "entity.create": {"entity": str, "kind": str, "name": str},
    "fact.set": {"subject": str, "attribute": str},
    "commitment.create": {
        "commitment": str,
        "kind": str,
        "what": str,
        "debtor": str,
        "creditor": str,
        "basis": str,
    },
    "commitment.update": {"commitment": str, "changes": dict},
    "commitment.resolve": {"commitment": str, "status": str},
    "decision.make": {"decision": str, "what": str, "by": list},
    "decision.reverse": {"decision": str},
    "project.split": {"project": str, "into": list},
    "project.merge": {"projects": list, "into": str},
    "artifact.emit": {
        "artifact": str,
        "channel": str,
        "path": str,
        "received_at": str,
        "reveals": list,
    },
}
MAY_BE_EMPTY = {"reveals"}  # an artifact may reveal nothing (noise, weak evidence)
# Optional fields whose type is still checked when present.
OPTIONAL_TYPES: dict[str, type] = {
    "surface_forms": list,
    "attrs": dict,
    "others": list,
    "keywords": list,
    "moves": dict,
    "challenges": list,
    "secrets": list,
    "noise": bool,
    "accepted": bool,
    "title": str,
}
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$")
ARTIFACT_ID_RE = re.compile(r"^[a-z]{2}-[a-z0-9-]+$")
OBJECT_ID_RE = {
    "commitment": re.compile(r"^c-[a-z0-9-]+$"),
    "decision": re.compile(r"^d-[a-z0-9-]+$"),
}
EVENT_ID_RE = re.compile(r"^e-[a-z0-9-]+$")
ALWAYS = ""  # known_on of the worker's entity.create: before every date


def check_world(world_dir: Path) -> list[Issue]:
    """Run every consistency check on a world directory and return the issues found.

    Structural problems (unreadable `world.yaml` or `world.jsonl`) stop the checks early;
    everything else is reported in one pass. Issues are ordered by check family, then by
    world order.
    """
    world_dir = Path(world_dir)
    issues: list[Issue] = []
    meta = _load_meta(world_dir, issues)
    if meta is None:
        return issues
    raw = _load_events(world_dir, issues)
    if raw is None:
        return issues
    _check_meta(meta, issues)
    _check_event_fields(raw, meta, issues)
    try:
        world = World.load(world_dir)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        issues.append(error("world.load", f"cannot load world.jsonl: {e!r}", "world.jsonl"))
        return issues
    ix = _Index.build(world)
    _check_ids(world, ix, issues)
    _check_references(world, ix, issues)
    _check_artifacts(world, ix, issues)
    _check_inbox_files(world, issues)
    _check_keywords(world, ix, issues)
    _check_project_summaries(world, ix, issues)
    _check_questions(world, ix, issues)
    return issues


# ---------------------------------------------------------------- loading
def _load_meta(world_dir: Path, issues: list[Issue]) -> dict[str, Any] | None:
    path = world_dir / "world.yaml"
    if not path.is_file():
        issues.append(error("meta.file", "world.yaml not found", str(path)))
        return None
    try:
        meta = _plain(read_yaml(path))
    except Exception as e:  # yaml.YAMLError and friends: report, do not crash
        issues.append(error("meta.file", f"cannot parse world.yaml: {e}", "world.yaml"))
        return None
    if not isinstance(meta, dict):
        issues.append(error("meta.file", "world.yaml must be a mapping", "world.yaml"))
        return None
    return meta


def _load_events(world_dir: Path, issues: list[Issue]) -> list[dict[str, Any]] | None:
    path = world_dir / "world.jsonl"
    if not path.is_file():
        issues.append(error("events.file", "world.jsonl not found", str(path)))
        return None
    try:
        rows = read_jsonl(path)
    except ValueError as e:
        issues.append(error("events.file", str(e), "world.jsonl"))
        return None
    bad = [i for i, r in enumerate(rows, 1) if not isinstance(r, dict)]
    if bad:
        issues.append(error("events.file", f"rows {bad[:5]} are not JSON objects", "world.jsonl"))
        return None
    return rows


# ---------------------------------------------------------------- world.yaml
def _check_meta(meta: dict[str, Any], issues: list[Issue]) -> None:
    def err(msg: str, code: str = "meta.missing") -> None:
        issues.append(error(code, msg, "world.yaml"))

    for key in ("id", "worker"):
        if not isinstance(meta.get(key), str) or not meta.get(key):
            err(f"'{key}' is required")
    seed = meta.get("seed") if isinstance(meta.get("seed"), dict) else {}
    start, end = seed.get("start"), seed.get("end")
    for name, value in (("seed.start", start), ("seed.end", end)):
        if not _is_date(value):
            err(f"'{name}' is required and must be YYYY-MM-DD")
    if _is_date(start) and _is_date(end) and start > end:
        err(f"seed.start {start} is after seed.end {end}", "meta.seed")

    episode = meta.get("episode") if isinstance(meta.get("episode"), dict) else {}
    days = episode.get("days")
    if not isinstance(days, list) or not days:
        err("'episode.days' is required and must be a non-empty list")
        days = []
    days = [str(d) for d in days]
    for d in days:
        if not _is_date(d):
            err(f"episode day {d!r} is not YYYY-MM-DD", "meta.episode")
    if days != sorted(set(days)):
        err("episode.days must be strictly increasing (sorted, no duplicates)", "meta.episode")
    if _is_date(end):
        for d in days:
            if _is_date(d) and d <= end:
                err(f"episode day {d} is not after seed.end {end}", "meta.episode")

    cps = meta.get("checkpoints")
    if not isinstance(cps, list) or not cps:
        err("'checkpoints' is required and must be a non-empty list")
        cps = []
    seen: set[str] = set()
    for cp in cps:
        if not isinstance(cp, dict) or not cp.get("id") or not cp.get("date"):
            err(f"checkpoint {cp!r} needs 'id' and 'date'", "meta.checkpoint")
            continue
        cid, cdate = str(cp["id"]), str(cp["date"])
        if cid in seen:
            err(f"duplicate checkpoint id {cid}", "meta.checkpoint")
        seen.add(cid)
        if cdate not in days:
            err(f"checkpoint {cid} date {cdate} is not an episode day", "meta.checkpoint")

    tz = meta.get("timezone")
    if tz is not None and not re.fullmatch(r"[+-]\d{2}:\d{2}", str(tz)):
        issues.append(
            warning("meta.timezone", f"timezone {tz!r} is not of the form -08:00", "world.yaml")
        )


# ---------------------------------------------------------------- per-event fields
def _check_event_fields(
    raw: list[dict[str, Any]], meta: dict[str, Any], issues: list[Issue]
) -> None:
    """Field presence, types and allowed values, one event at a time (no cross-references)."""
    tz = meta.get("timezone")
    prev_t = ""
    for lineno, e in enumerate(raw, 1):
        where = f"world.jsonl:{lineno}" + (f" {e['id']}" if isinstance(e.get("id"), str) else "")

        def err(code: str, msg: str, where: str = where) -> None:
            issues.append(error(code, msg, where))

        eid, etype, t = e.get("id"), e.get("type"), e.get("t")
        if not isinstance(eid, str) or not EVENT_ID_RE.match(eid):
            err("event.id", f"event id {eid!r} must look like e-NNNN")
        if not _is_time(t, tz):
            err(
                "event.time",
                f"'t' {t!r} must be an ISO datetime with the world's offset {tz or ''}".rstrip(),
            )
        elif t < prev_t:
            issues.append(
                warning(
                    "event.order",
                    f"t {t} is earlier than the previous line's {prev_t}; world.jsonl should be sorted by t",
                    where,
                )
            )
        if isinstance(t, str):
            prev_t = max(prev_t, t)
        if etype not in EVENT_TYPES:
            err("event.type", f"unknown event type {etype!r}")
            continue
        if etype != "artifact.emit" and not (
            isinstance(e.get("summary"), str) and e["summary"].strip()
        ):
            err("event.summary", f"{etype} needs a non-empty 'summary'")
        for key, typ in REQUIRED_FIELDS[etype].items():
            if not isinstance(e.get(key), typ) or (not e[key] and key not in MAY_BE_EMPTY):
                err("event.field", f"{etype} needs '{key}' (a non-empty {typ.__name__})")
        for key, typ in OPTIONAL_TYPES.items():
            if e.get(key) is not None and not isinstance(e[key], typ):
                err("event.field", f"'{key}' must be a {typ.__name__}")
        for code, problem in _value_problems(e, etype, tz):
            err(code, problem)


def _value_problems(e: dict[str, Any], etype: str, tz: str | None) -> list[tuple[str, str]]:
    """Allowed-value problems for one event, as (issue code, message) pairs."""
    out: list[str] = []
    codes: list[tuple[str, str]] = []
    if etype == "entity.create":
        kind, ent = e.get("kind"), e.get("entity")
        if kind not in ENTITY_PREFIX:
            out.append(f"entity kind {kind!r} must be person, org or project")
        elif isinstance(ent, str) and not re.fullmatch(
            re.escape(ENTITY_PREFIX[kind]) + r"[a-z0-9-]+", ent
        ):
            codes.append(
                (
                    "entity.prefix",
                    f"{kind} id {ent!r} must start with {ENTITY_PREFIX[kind]!r} (lowercase ASCII)",
                )
            )
        attrs = e.get("attrs") if isinstance(e.get("attrs"), dict) else {}
        out += [f"attrs.{p}" for p in _attr_problems(kind, attrs)]
        if kind == "project" and not attrs.get("owner"):
            out.append("a project needs attrs.owner (the contract requires an owner)")
    elif etype == "fact.set":
        if "value" not in e:
            out.append("fact.set needs 'value' (null clears the attribute)")
    elif etype == "commitment.create":
        if e.get("kind") not in LOOP_KINDS:
            out.append(f"commitment kind {e.get('kind')!r} must be task or ask")
        if e.get("status", "open") not in CREATE_STATUSES:
            out.append(
                f"create status {e.get('status')!r} must be one of {', '.join(CREATE_STATUSES)}"
            )
        if e.get("basis") is not None and e.get("basis") not in BASES:
            out.append(f"basis {e.get('basis')!r} must be one of {', '.join(BASES)}")
        if not _is_date_or_null(e.get("due")):
            out.append(f"due {e.get('due')!r} must be YYYY-MM-DD or null")
        if isinstance(e.get("commitment"), str) and not OBJECT_ID_RE["commitment"].match(
            e["commitment"]
        ):
            codes.append(("object.id", f"commitment id {e['commitment']!r} must look like c-NNN"))
    elif etype == "commitment.update":
        changes = e.get("changes") if isinstance(e.get("changes"), dict) else {}
        for k in changes:
            if k not in UPDATE_KEYS:
                out.append(f"changes.{k} is not updatable (allowed: {', '.join(UPDATE_KEYS)})")
        if "status" in changes and changes["status"] not in LOOP_STATUSES:
            out.append(
                f"changes.status {changes['status']!r} must be one of {', '.join(LOOP_STATUSES)}"
            )
        if "due" in changes and not _is_date_or_null(changes["due"]):
            out.append(f"changes.due {changes['due']!r} must be YYYY-MM-DD or null")
        if "accepted" in changes and not isinstance(changes["accepted"], bool):
            out.append("changes.accepted must be true or false")
        for k in ("others", "keywords"):
            if k in changes and not isinstance(changes[k], list):
                out.append(f"changes.{k} must be a list")
    elif etype == "commitment.resolve":
        if e.get("status") not in RESOLVE_STATUSES:
            out.append(f"resolve status {e.get('status')!r} must be done or dropped")
    elif etype == "decision.make":
        if isinstance(e.get("decision"), str) and not OBJECT_ID_RE["decision"].match(e["decision"]):
            codes.append(("object.id", f"decision id {e['decision']!r} must look like d-NNN"))
    elif etype == "artifact.emit":
        if not _is_time(e.get("received_at"), tz):
            out.append(
                f"received_at {e.get('received_at')!r} must be an ISO datetime with the world's offset"
            )
        if isinstance(e.get("artifact"), str) and not ARTIFACT_ID_RE.match(e["artifact"]):
            out.append(f"artifact id {e['artifact']!r} must look like em-0001")
        if not (isinstance(e.get("title"), str) and e["title"].strip()):
            out.append("artifact.emit needs a non-empty 'title' (shown in the manifest)")
        for s in e.get("secrets") or []:
            if not isinstance(s, str) or not s:
                out.append(f"secret {s!r} must be a non-empty string")
    return codes + [("event.field", m) for m in out]


def _attr_problems(kind: str | None, attrs: dict[str, Any]) -> list[str]:
    """Contract-enum and date problems in entity attributes (so oracle stores validate)."""
    out: list[str] = []
    for attr, value in attrs.items():
        out += _one_attr_problem(kind, attr, value)
    return out


def _one_attr_problem(kind: str | None, attr: str, value: Any) -> list[str]:
    if value is None:
        return []
    if kind == "person" and attr == "relationship" and value not in RELATIONSHIPS:
        return [f"relationship: {value!r} is not one of {', '.join(RELATIONSHIPS)}"]
    if kind == "org" and attr == "kind" and value not in ORG_KINDS:
        return [f"kind: {value!r} is not one of {', '.join(ORG_KINDS)}"]
    if kind == "project" and attr == "status" and value not in PROJECT_STATUSES:
        return [f"status: {value!r} is not one of {', '.join(PROJECT_STATUSES)}"]
    if kind == "project" and attr == "target_date" and not _is_date(value):
        return [f"target_date: {value!r} must be YYYY-MM-DD"]
    return []


# ---------------------------------------------------------------- index of world objects
@dataclass
class _Index:
    """Where each object is created, when it becomes knowable, and in which order."""

    worker: str
    entities: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> entity.create
    commitments: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> commitment.create
    decisions: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> decision.make
    events: dict[str, dict[str, Any]] = field(default_factory=dict)  # id -> first event with it
    position: dict[str, int] = field(default_factory=dict)  # event id -> index in world order
    known_on: dict[str, str] = field(default_factory=dict)  # event id -> date first revealed
    revealers: dict[str, list[str]] = field(default_factory=dict)  # event id -> artifact ids

    @classmethod
    def build(cls, world: World) -> _Index:
        ix = cls(worker=str(world.meta.get("worker", "")))
        ix.known_on = world.known_on()
        ix.revealers = world.revealing_artifacts()
        for i, e in enumerate(world.events):
            eid = e.get("id")
            if isinstance(eid, str) and eid not in ix.events:
                ix.events[eid] = e
                ix.position[eid] = i
            etype = e.get("type")
            if etype == "entity.create" and isinstance(e.get("entity"), str):
                ix.entities.setdefault(e["entity"], e)
            elif etype == "commitment.create" and isinstance(e.get("commitment"), str):
                ix.commitments.setdefault(e["commitment"], e)
            elif etype == "decision.make" and isinstance(e.get("decision"), str):
                ix.decisions.setdefault(e["decision"], e)
        return ix

    def creator(self, obj: str, kind: str) -> dict[str, Any] | None:
        """The event that creates `obj` if it exists with the expected kind."""
        if kind == "commitment":
            return self.commitments.get(obj)
        if kind == "decision":
            return self.decisions.get(obj)
        ev = self.entities.get(obj)
        return ev if ev is not None and ev.get("kind") == kind else None

    def object_known_on(self, obj: str, kind: str) -> str | None:
        """Date the object's creating event becomes knowable (the worker: always)."""
        if kind == "person" and obj == self.worker:
            return ALWAYS
        ev = self.creator(obj, kind)
        return self.known_on.get(ev["id"]) if ev and isinstance(ev.get("id"), str) else None


# ---------------------------------------------------------------- identity
def _check_ids(world: World, ix: _Index, issues: list[Issue]) -> None:
    seen: dict[str, str] = {}
    created: dict[tuple[str, str], str] = {}
    for e in world.events:
        eid = e.get("id")
        if isinstance(eid, str):
            if eid in seen:
                issues.append(
                    error("event.duplicate", f"event id {eid} is used more than once", eid)
                )
            seen[eid] = eid
        key = _created_object(e)
        if key is not None:
            if key in created:
                issues.append(
                    error(
                        "object.duplicate",
                        f"{key[0]} {key[1]} is created twice ({created[key]} and {eid})",
                        eid,
                    )
                )
            else:
                created[key] = str(eid)
    worker_ev = ix.entities.get(ix.worker)
    if worker_ev is None or worker_ev.get("kind") != "person":
        issues.append(
            error("meta.worker", f"worker {ix.worker!r} has no person entity.create", "world.yaml")
        )


def _created_object(e: dict[str, Any]) -> tuple[str, str] | None:
    etype = e.get("type")
    if etype == "entity.create":
        return ("entity", str(e.get("entity")))
    if etype == "commitment.create":
        return ("commitment", str(e.get("commitment")))
    if etype == "decision.make":
        return ("decision", str(e.get("decision")))
    if etype == "artifact.emit":
        return ("artifact", str(e.get("artifact")))
    return None


# ---------------------------------------------------------------- references and knowability
# A reference is (field label, target ID, expected kind, role). Roles:
#   object: the thing the event changes. It must be created earlier in world order and be
#           knowable no later than the event (else the change is silently dropped from gold).
#   loop:   a person or project a loop names. Must be knowable when the loop event is (error),
#           otherwise the loop names someone the agent cannot know about.
#   attr:   an entity named in attributes. Should be knowable when the event is (warning).
_Ref = tuple[str, str, str, str]


def _refs(e: dict[str, Any], ix: _Index) -> list[_Ref]:
    """Every reference an event makes, with the kind of object expected and its role."""
    etype = e.get("type")
    refs: list[_Ref] = []

    def add(label: str, value: Any, kind: str, role: str) -> None:
        for v in value if isinstance(value, list) else [value]:
            if isinstance(v, str) and v:
                refs.append((label, v, kind, role))

    loop_project_role = "loop" if etype in ("commitment.create", "decision.make") else "attr"
    if etype not in ("project.split", "project.merge"):
        add("project", e.get("project"), "project", loop_project_role)
    if etype == "entity.create":
        attrs = e.get("attrs") if isinstance(e.get("attrs"), dict) else {}
        for attr, kind in ENTITY_ATTRS.get(str(e.get("kind")), {}).items():
            add(f"attrs.{attr}", attrs.get(attr), kind, "attr")
    elif etype == "fact.set":
        subj = e.get("subject")
        subj_ev = ix.entities.get(subj) if isinstance(subj, str) else None
        subj_kind = str(subj_ev.get("kind")) if subj_ev else "entity"
        add("subject", subj, subj_kind, "object")
        val_kind = ENTITY_ATTRS.get(subj_kind, {}).get(str(e.get("attribute")))
        if val_kind:
            add(f"value ({e.get('attribute')})", e.get("value"), val_kind, "attr")
    elif etype == "commitment.create":
        for f in ("debtor", "creditor", "others"):
            add(f, e.get(f), "person", "loop")
    elif etype == "commitment.update":
        add("commitment", e.get("commitment"), "commitment", "object")
        changes = e.get("changes") if isinstance(e.get("changes"), dict) else {}
        for f in ("debtor", "creditor", "others"):
            add(f"changes.{f}", changes.get(f), "person", "loop")
        add("changes.project", changes.get("project"), "project", "loop")
    elif etype == "commitment.resolve":
        add("commitment", e.get("commitment"), "commitment", "object")
    elif etype == "decision.make":
        add("by", e.get("by"), "person", "loop")
    elif etype == "decision.reverse":
        add("decision", e.get("decision"), "decision", "object")
    elif etype == "project.split":
        add("project", e.get("project"), "project", "object")
        add("into", e.get("into"), "project", "object")
        moves = e.get("moves") if isinstance(e.get("moves"), dict) else {}
        add("moves (key)", list(moves), "commitment", "object")
        add("moves (value)", list(moves.values()), "project", "loop")
    elif etype == "project.merge":
        add("projects", e.get("projects"), "project", "object")
        add("into", e.get("into"), "project", "object")
    return refs


def _check_references(world: World, ix: _Index, issues: list[Issue]) -> None:
    for pos, e in enumerate(world.events):
        if e.get("type") == "artifact.emit":
            continue
        eid = str(e.get("id"))
        kd = ix.known_on.get(eid)
        for label, target, kind, role in _refs(e, ix):
            creator = ix.creator(target, kind)
            if creator is None:
                exists_as = _describe(target, ix)
                hint = f" (it is {exists_as})" if exists_as else ""
                issues.append(
                    error("ref.missing", f"{label} {target!r} is not an existing {kind}{hint}", eid)
                )
                continue
            if role == "object" and ix.position.get(str(creator.get("id")), -1) > pos:
                issues.append(
                    error(
                        "ref.order",
                        f"{e.get('type')} on {target} happens before {target} is created",
                        eid,
                    )
                )
            if kd is None:
                continue  # never revealed: it never reaches gold, so knowability does not matter
            target_kd = ix.object_known_on(target, kind)
            if target_kd is not None and target_kd <= kd:
                continue
            when = f"only on {target_kd}" if target_kd else "never"
            if role == "object":
                issues.append(
                    error(
                        "reveal.before_create",
                        f"{e.get('type')} is revealed on {kd} but {target} becomes knowable {when}; gold would drop the change",
                        eid,
                    )
                )
            else:
                sev = error if role == "loop" else warning
                issues.append(
                    sev(
                        "ref.unknowable",
                        f"{label} {target} becomes knowable {when}, after this event (revealed {kd}); reveal its entity.create in the same or an earlier artifact",
                        eid,
                    )
                )
        if e.get("type") in ("entity.create", "fact.set"):
            _check_fact_value(e, ix, issues)


def _check_fact_value(e: dict[str, Any], ix: _Index, issues: list[Issue]) -> None:
    """Contract enums for attributes set by fact.set (entity.create is checked per event)."""
    if e.get("type") != "fact.set":
        return
    subj = ix.entities.get(str(e.get("subject")))
    if subj is None:
        return
    for p in _one_attr_problem(str(subj.get("kind")), str(e.get("attribute")), e.get("value")):
        issues.append(error("event.field", p, str(e.get("id"))))


def _describe(target: str, ix: _Index) -> str:
    if target in ix.entities:
        return f"a {ix.entities[target].get('kind')}"
    if target in ix.commitments:
        return "a commitment"
    if target in ix.decisions:
        return "a decision"
    return ""


# ---------------------------------------------------------------- artifacts
def _check_artifacts(world: World, ix: _Index, issues: list[Issue]) -> None:
    meta = world.meta
    seed = meta.get("seed") or {}
    seed_start, seed_end = str(seed.get("start", "")), str(seed.get("end", ""))
    episode_days = set(world.episode_days())
    paths: dict[str, str] = {}
    for e in world.events:
        if e.get("type") != "artifact.emit":
            continue
        aid = str(e.get("artifact"))
        a = world.artifacts.get(aid)
        if a is None or a.event_id != e.get("id"):
            continue  # duplicate artifact id, reported by _check_ids
        loc = f"{aid} ({a.event_id})"
        prefix = CHANNEL_PREFIX.get(a.channel)
        if prefix is None:
            issues.append(error("artifact.channel", f"unknown channel {a.channel!r}", loc))
        elif not aid.startswith(prefix + "-"):
            issues.append(
                error(
                    "artifact.prefix",
                    f"id prefix does not match channel {a.channel} (expected {prefix}-)",
                    loc,
                )
            )
        _check_artifact_path(world, a, loc, issues)
        if a.path in paths:
            issues.append(
                error("artifact.path", f"path {a.path} is also used by {paths[a.path]}", loc)
            )
        paths[a.path] = aid
        d = a.date
        in_seed = bool(seed_start) and seed_start <= d <= seed_end
        if not in_seed and d not in episode_days:
            issues.append(
                error(
                    "artifact.schedule",
                    f"delivered on {d}, which is neither in the seed window nor an episode day",
                    loc,
                )
            )
        if a.parent and a.parent not in world.artifacts:
            issues.append(error("artifact.parent", f"parent {a.parent!r} is not an artifact", loc))
        for tag in a.challenges:
            if tag not in CHALLENGE_TAGS:
                issues.append(
                    warning(
                        "artifact.challenge",
                        f"unknown challenge tag {tag!r} (docs/formats.md §1.4)",
                        loc,
                    )
                )
        _check_reveals(a, ix, loc, issues)
        _check_secrets(world, a, loc, issues)


def _check_artifact_path(world: World, a: Any, loc: str, issues: list[Issue]) -> None:
    parts = Path(a.path).parts
    if len(parts) != 3 or parts[0] != "inbox" or Path(a.path).is_absolute():
        issues.append(error("artifact.path", f"path {a.path!r} must be inbox/<date>/<file>", loc))
        return
    if Path(parts[2]).stem != a.id:
        issues.append(
            error(
                "artifact.path",
                f"file name {parts[2]!r} must be the artifact id plus an extension",
                loc,
            )
        )
    if parts[1] != a.date:
        issues.append(
            error(
                "artifact.date",
                f"inbox date {parts[1]} differs from the date of received_at ({a.date})",
                loc,
            )
        )
    suffix = Path(parts[2]).suffix.lower()
    if a.channel in CHANNEL_SUFFIXES and suffix not in CHANNEL_SUFFIXES[a.channel]:
        allowed = ", ".join(sorted(CHANNEL_SUFFIXES[a.channel]))
        issues.append(
            warning(
                "artifact.format",
                f"{suffix or 'no extension'} is unusual for {a.channel} (expected {allowed})",
                loc,
            )
        )
    if not (world.dir / a.path).is_file():
        issues.append(error("artifact.missing_file", f"file {a.path} does not exist", loc))


def _check_reveals(a: Any, ix: _Index, loc: str, issues: list[Issue]) -> None:
    for rid in a.reveals:
        target = ix.events.get(rid)
        if target is None:
            issues.append(error("reveal.missing", f"reveals unknown event {rid!r}", loc))
        elif target.get("type") == "artifact.emit":
            issues.append(
                error(
                    "reveal.missing",
                    f"reveals {rid}, which is an artifact.emit (reveal world events only)",
                    loc,
                )
            )
        elif _later(str(target.get("t", "")), a.received_at):
            issues.append(
                error(
                    "reveal.future",
                    f"reveals {rid} (t {target.get('t')}) before it happens (received_at {a.received_at})",
                    loc,
                )
            )


def _check_secrets(world: World, a: Any, loc: str, issues: list[Issue]) -> None:
    if not a.secrets:
        return
    raw = raw_text(world.dir / a.path)
    if raw is None:
        return  # missing file (reported elsewhere) or binary format: skipped
    for s in a.secrets:
        if isinstance(s, str) and s and s not in raw:
            issues.append(
                error("secret.missing", f"secret {s!r} does not occur literally in {a.path}", loc)
            )


def _check_inbox_files(world: World, issues: list[Issue]) -> None:
    """Every file in inbox/ must be declared by an artifact.emit (manifests are generated)."""
    inbox = world.dir / "inbox"
    if not inbox.is_dir():
        return
    declared = {Path(a.path).as_posix() for a in world.artifacts.values()}
    for f in sorted(p for p in inbox.rglob("*") if p.is_file()):
        rel = f.relative_to(world.dir).as_posix()
        if f.name == "manifest.json" or rel in declared:
            continue
        issues.append(error("inbox.undeclared", "file is not declared by any artifact.emit", rel))


# ---------------------------------------------------------------- grading aids
def _check_keywords(world: World, ix: _Index, issues: list[Issue]) -> None:
    """Keywords let heuristic graders match free-text answers; they must be grounded in inputs."""
    texts: dict[str, str | None] = {}

    def text_of(aid: str) -> str | None:
        if aid not in texts:
            a = world.artifacts.get(aid)
            texts[aid] = artifact_text(world.dir / a.path) if a else None
        return texts[aid]

    objects = _keyword_objects(world)
    for obj, (keywords, event_ids) in objects.items():
        if obj.startswith("c-") and len(keywords) < 2:
            issues.append(
                warning(
                    "keyword.count",
                    f"has {len(keywords)} keyword(s); give at least two distinctive words or phrases",
                    obj,
                )
            )
        arts = _dedup([aid for eid in event_ids for aid in ix.revealers.get(eid, [])])
        corpus = [t for t in (text_of(aid) for aid in arts) if t is not None]
        if not corpus:
            continue
        for kw in keywords:
            if isinstance(kw, str) and not any(_mentions(t, kw) for t in corpus):
                issues.append(
                    warning(
                        "keyword.absent",
                        f"keyword {kw!r} occurs in none of the artifacts that reveal it ({', '.join(arts)})",
                        obj,
                    )
                )


def _keyword_objects(world: World) -> dict[str, tuple[list[str], list[str]]]:
    """Commitment/decision ID -> (current keywords, IDs of the events about it)."""
    out: dict[str, tuple[list[str], list[str]]] = {}
    for e in world.events:
        etype = e.get("type")
        obj = e.get("commitment") or e.get("decision")
        if not isinstance(obj, str) or etype not in (
            "commitment.create",
            "commitment.update",
            "commitment.resolve",
            "decision.make",
            "decision.reverse",
        ):
            continue
        keywords, events = out.setdefault(obj, ([], []))
        events.append(str(e.get("id")))
        new = (
            e.get("keywords")
            if etype in ("commitment.create", "decision.make")
            else (e.get("changes") or {}).get("keywords")
        )
        if isinstance(new, list):
            keywords[:] = new
    return out


def _check_project_summaries(world: World, ix: _Index, issues: list[Issue]) -> None:
    """Warn when a project's `summary` attribute still mentions a superseded date.

    The oracle store prints `summary` verbatim as the project's current state, so a summary
    that says "decision targeted for 29 January" after `target_date` moved presents a stale
    fact as current. Replays project attributes in world order (ignoring knowability).
    """
    attrs: dict[str, dict[str, Any]] = {}
    # A summary rewritten at the same instant as the date change is not stale.
    same_time_summary = {
        (str(e.get("subject")), str(e.get("t")))
        for e in world.events
        if e.get("type") == "fact.set" and e.get("attribute") == "summary"
    }
    for e in world.events:
        etype = e.get("type")
        if etype == "entity.create" and e.get("kind") == "project":
            attrs[str(e.get("entity"))] = dict(e.get("attrs") or {})
        elif etype == "fact.set" and e.get("subject") in attrs:
            cur = attrs[str(e["subject"])]
            attr, old = str(e.get("attribute")), cur.get(str(e.get("attribute")))
            cur[attr] = e.get("value")
            summary = cur.get("summary")
            if (
                attr == "summary"
                or not _is_date(old)
                or old == e.get("value")
                or not isinstance(summary, str)
                or (str(e["subject"]), str(e.get("t"))) in same_time_summary
            ):
                continue
            low = normalize(summary)
            if any(v in low for v in text_variants(old)):
                issues.append(
                    warning(
                        "summary.stale",
                        f"{e['subject']}.{attr} changed from {old} but its summary still mentions {old}; add a fact.set for summary",
                        str(e.get("id")),
                    )
                )


# ---------------------------------------------------------------- questions.yaml
QUESTION_PARAM_KINDS = {
    "person": "person",
    "project": "project",
    "org": "org",
    "commitment": "commitment",
    "decision": "decision",
}


def _check_questions(world: World, ix: _Index, issues: list[Issue]) -> None:
    path = world.dir / "questions.yaml"
    if not path.is_file():
        return
    try:
        specs = _plain(read_yaml(path)) or []
    except Exception as e:  # yaml.YAMLError: report, do not crash
        issues.append(error("question.file", f"cannot parse questions.yaml: {e}", "questions.yaml"))
        return
    if not isinstance(specs, list):
        issues.append(
            error(
                "question.file", "questions.yaml must be a list of question specs", "questions.yaml"
            )
        )
        return
    templates = _template_names()
    checkpoints = {
        str(c.get("id")) for c in world.meta.get("checkpoints") or [] if isinstance(c, dict)
    }
    seen: set[str] = set()
    for i, q in enumerate(specs, 1):
        if not isinstance(q, dict):
            issues.append(error("question.file", f"entry {i} is not a mapping", "questions.yaml"))
            continue
        qid = str(q.get("id") or "")
        loc = f"questions.yaml {qid or f'#{i}'}"
        if not qid:
            issues.append(error("question.id", "question needs an 'id'", loc))
        elif qid in seen:
            issues.append(
                error("question.duplicate", f"question id {qid} is used more than once", loc)
            )
        seen.add(qid)
        if str(q.get("checkpoint")) not in checkpoints:
            issues.append(
                error(
                    "question.checkpoint",
                    f"checkpoint {q.get('checkpoint')!r} is not in world.yaml",
                    loc,
                )
            )
        if templates is not None and q.get("template") not in templates:
            issues.append(
                error("question.template", f"unknown template {q.get('template')!r}", loc)
            )
        params = q.get("params") or {}
        if not isinstance(params, dict):
            issues.append(error("question.param", "params must be a mapping", loc))
            continue
        for key, value in params.items():
            problem = _param_problem(key, value, ix)
            if problem:
                issues.append(error("question.param", problem, loc))
        for tag in q.get("challenges") or []:
            if tag not in CHALLENGE_TAGS:
                issues.append(warning("question.challenge", f"unknown challenge tag {tag!r}", loc))


def _param_problem(key: str, value: Any, ix: _Index) -> str | None:
    if key in QUESTION_PARAM_KINDS:
        kind = QUESTION_PARAM_KINDS[key]
        if not isinstance(value, str) or ix.creator(value, kind) is None:
            return f"param {key}: {value!r} is not an existing {kind}"
    elif key == "event":
        ev = ix.events.get(str(value))
        if ev is None or ev.get("type") == "artifact.emit":
            return f"param event: {value!r} is not an existing world event"
    elif key == "since" and not _is_date(value):
        return f"param since: {value!r} must be YYYY-MM-DD"
    return None


def _template_names() -> set[str] | None:
    """Known question templates, or None while wcb.questions.templates is unavailable."""
    try:
        from wcb.questions.templates import TEMPLATES
    except ImportError:
        return None
    return set(TEMPLATES)


# ---------------------------------------------------------------- artifact text
TEXT_SUFFIXES = {".eml", ".json", ".vtt", ".txt", ".md", ".ics", ".csv", ".html", ".htm"}
OFFICE_SUFFIXES = {".docx", ".xlsx", ".pptx"}
_OFFICE_PART = re.compile(
    r"^(word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml"
    r"|xl/sharedStrings\.xml|xl/worksheets/sheet\d+\.xml"
    r"|ppt/slides/slide\d+\.xml|ppt/notesSlides/notesSlide\d+\.xml)$"
)
_OFFICE_BREAK = re.compile(r"</(?:w:p|a:p|si|row|c)>|<(?:w:br|w:tab|a:br)\b[^>]*/?>")


def raw_text(path: Path) -> str | None:
    """The file's text if it is a text format (a .pdf counts when it is plain text); else None."""
    path = Path(path)
    if not path.is_file():
        return None
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        data = path.read_bytes()
        if data.startswith(b"%PDF"):
            return None
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    return None


def artifact_text(path: Path) -> str | None:
    """Searchable text of an artifact, or None when it cannot be extracted (binary PDF, images).

    Text formats return the raw file plus a decoded view (email bodies and headers, chat
    message strings, unfolded calendar lines). Word, Excel and PowerPoint files return the text
    of their XML parts.
    """
    path = Path(path)
    if path.suffix.lower() in OFFICE_SUFFIXES:
        return _office_text(path) if path.is_file() else None
    raw = raw_text(path)
    if raw is None:
        return None
    decode = {".json": _json_strings, ".eml": _email_text, ".ics": _ics_text}.get(
        path.suffix.lower()
    )
    return raw + "\n" + decode(raw) if decode else raw


def _office_text(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            chunks = []
            for name in sorted(n for n in z.namelist() if _OFFICE_PART.match(n)):
                xml = _OFFICE_BREAK.sub("\n", z.read(name).decode("utf-8", errors="replace"))
                chunks.append(html.unescape(re.sub(r"<[^>]+>", "", xml)))
            return "\n".join(chunks)
    except (zipfile.BadZipFile, OSError, KeyError):
        return None


def _json_strings(raw: str) -> str:
    try:
        data = json.loads(raw)
    except ValueError:
        return ""
    out: list[str] = []

    def walk(x: Any) -> None:
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(data)
    return "\n".join(out)


def _email_text(raw: str) -> str:
    import email
    from email import policy

    msg = email.message_from_string(raw, policy=policy.default)
    parts = [str(msg.get("Subject") or "")]
    for part in msg.walk():
        if part.get_content_maintype() == "text":
            try:
                parts.append(part.get_content())
            except (LookupError, ValueError):
                continue
    return "\n".join(parts)


def _ics_text(raw: str) -> str:
    unfolded = re.sub(r"\r?\n[ \t]", "", raw)
    for a, b in (("\\n", "\n"), ("\\N", "\n"), ("\\,", ","), ("\\;", ";"), ("\\\\", "\\")):
        unfolded = unfolded.replace(a, b)
    return unfolded


def _mentions(text: str, phrase: str) -> bool:
    """Case- and accent-insensitive containment, also across line breaks and punctuation."""
    return normalize(phrase) in normalize(text) or contains_phrase(text, phrase)


# ---------------------------------------------------------------- small helpers
def _is_date(value: Any) -> bool:
    return isinstance(value, str) and bool(DATE_RE.match(value))


def _is_date_or_null(value: Any) -> bool:
    return value is None or _is_date(value)


def _is_time(value: Any, tz: Any) -> bool:
    if not isinstance(value, str) or not TIME_RE.match(value):
        return False
    try:
        parse_dt(value)
    except ValueError:
        return False
    return (
        tz is None
        or value.endswith(str(tz))
        or (str(tz) in ("+00:00", "Z") and value.endswith("Z"))
    )


def _later(a: str, b: str) -> bool:
    """True if time `a` is after time `b` (falls back to string order for odd values)."""
    try:
        return parse_dt(a) > parse_dt(b)
    except (ValueError, TypeError):
        return a > b


def _dedup(xs: list[str]) -> list[str]:
    return list(dict.fromkeys(xs))


def _plain(obj: Any) -> Any:
    """YAML parses bare dates; turn them back into ISO strings."""
    import datetime as _dt

    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    if isinstance(obj, (_dt.date, _dt.datetime)):
        return obj.isoformat()
    return obj
