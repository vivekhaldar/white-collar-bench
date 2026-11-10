"""Knowable gold state at the end of a date (docs/formats.md §1.3 and §2).

An event is knowable at the end of date D if an artifact received on or before D reveals it.
Knowable events are applied in world-time order. The result is what an ideal ingestor could
know on that date, which is what the agent's store and answers are graded against.
"""

from __future__ import annotations

import copy
from typing import Any

from wcb.util.dates import date_of
from wcb.world.model import ACTIVE_STATUSES, World

LOOP_FIELDS = ("kind", "what", "debtor", "creditor", "others", "project", "status", "due", "accepted", "basis", "keywords")


def state_at(world: World, date: str) -> dict[str, Any]:
    date = date_of(date)
    known_on = world.known_on()
    revealers = world.revealing_artifacts()
    delivered = world.artifacts_through(date)
    delivered_ids = {a.id for a in delivered}

    def arts(eid: str) -> list[str]:
        return [aid for aid in revealers.get(eid, []) if aid in delivered_ids]

    entities: dict[str, dict[str, Any]] = {}
    loops: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    events_out: list[dict[str, Any]] = []
    unknowable: list[str] = []
    worker = world.worker

    for e in world.events:
        etype = e.get("type")
        if etype == "artifact.emit":
            continue
        eid = e["id"]
        is_worker_create = etype == "entity.create" and e.get("entity") == worker
        kd = known_on.get(eid)
        if not is_worker_create and (kd is None or kd > date):
            if date_of(e["t"]) <= date:
                unknowable.append(eid)
            continue
        kd = kd or date_of(e["t"])
        edate = date_of(e["t"])
        ev_arts = arts(eid)
        project = e.get("project")
        subjects: list[str] = []
        applied = True

        if etype == "entity.create":
            ent = e["entity"]
            subjects = [ent]
            if ent in entities:
                applied = False
            else:
                attrs = copy.deepcopy(e.get("attrs") or {})
                entities[ent] = {
                    "kind": e["kind"],
                    "name": e["name"],
                    "surface_forms": list(e.get("surface_forms", [])),
                    "attrs": attrs,
                    "known_on": kd,
                    "evidence": list(ev_arts),
                    "attr_history": {
                        k: [{"value": v, "t": e["t"], "event": eid}] for k, v in attrs.items()
                    },
                }
                if e["kind"] == "project":
                    project = ent

        elif etype == "fact.set":
            subj, attr, value = e["subject"], e["attribute"], e.get("value")
            subjects = [subj] + ([value] if isinstance(value, str) and value in entities else [])
            ent = entities.get(subj)
            if ent is None:
                applied = False
            else:
                if value is None:
                    ent["attrs"].pop(attr, None)
                else:
                    ent["attrs"][attr] = copy.deepcopy(value)
                ent["attr_history"].setdefault(attr, []).append({"value": value, "t": e["t"], "event": eid})
                _add(ent["evidence"], ev_arts)
                if ent["kind"] == "project":
                    project = subj

        elif etype == "commitment.create":
            cid = e["commitment"]
            if cid in loops:
                applied = False
            else:
                loop = {
                    "kind": e.get("kind", "task"),
                    "what": e["what"],
                    "debtor": e["debtor"],
                    "creditor": e["creditor"],
                    "others": list(e.get("others") or []),
                    "project": e.get("project"),
                    "status": e.get("status") or "open",
                    "due": e.get("due"),
                    "accepted": bool(e.get("accepted", True)),
                    "basis": e.get("basis"),
                    "keywords": list(e.get("keywords") or []),
                    "created": edate,
                    "updated": edate,
                    "known_on": kd,
                    "evidence": list(ev_arts),
                    "history": [],
                }
                loop["history"].append(
                    _hist(e, {k: loop[k] for k in ("status", "debtor", "creditor", "due", "accepted", "project")}, ev_arts)
                )
                loops[cid] = loop
                project = project or loop["project"]
            subjects = _loop_subjects(cid, loops.get(cid))

        elif etype in ("commitment.update", "commitment.resolve"):
            cid = e["commitment"]
            loop = loops.get(cid)
            if loop is None:
                applied = False
                subjects = [cid]
            else:
                if etype == "commitment.resolve":
                    changes = {"status": e.get("status", "done")}
                else:
                    changes = {k: v for k, v in (e.get("changes") or {}).items() if k in LOOP_FIELDS}
                before = _loop_subjects(cid, loop)
                for k, v in changes.items():
                    loop[k] = copy.deepcopy(v)
                if "accepted" in changes:
                    loop["accepted"] = bool(loop["accepted"])
                loop["updated"] = max(loop["updated"], edate)
                _add(loop["evidence"], ev_arts)
                loop["history"].append(_hist(e, changes, ev_arts))
                project = project or loop["project"]
                # A hand-off touches whoever gave the loop up as well as whoever took it.
                subjects = _loop_subjects(cid, loop) + before

        elif etype == "decision.make":
            did = e["decision"]
            if did in decisions:
                applied = False
            else:
                decisions[did] = {
                    "what": e["what"],
                    "by": list(e.get("by") or []),
                    "project": e.get("project"),
                    "status": "made",
                    "made_on": edate,
                    "reversed_on": None,
                    "reason": None,
                    "keywords": list(e.get("keywords") or []),
                    "evidence": list(ev_arts),
                    "known_on": kd,
                }
            subjects = [did, *(e.get("by") or [])]

        elif etype == "decision.reverse":
            did = e["decision"]
            d = decisions.get(did)
            if d is None:
                applied = False
            else:
                d["status"] = "reversed"
                d["reversed_on"] = edate
                d["reason"] = e.get("reason")
                _add(d["evidence"], ev_arts)
                project = project or d["project"]
            subjects = [did]

        elif etype == "project.split":
            src = e["project"]
            into = list(e.get("into") or [])
            project = src
            subjects = [src, *into]
            if src in entities:
                cur = list(entities[src]["attrs"].get("split_into") or [])
                entities[src]["attrs"]["split_into"] = cur + [p for p in into if p not in cur]
                _add(entities[src]["evidence"], ev_arts)
            for p in into:
                if p in entities:
                    entities[p]["attrs"]["parent"] = src
                    _add(entities[p]["evidence"], ev_arts)
            for cid, target in (e.get("moves") or {}).items():
                if cid in loops:
                    _move_loop(loops[cid], target, e, edate, ev_arts)
                    subjects.append(cid)

        elif etype == "project.merge":
            into = e["into"]
            merged = [p for p in e.get("projects", []) if p != into]
            project = into
            subjects = [*merged, into]
            for p in merged:
                if p in entities:
                    entities[p]["attrs"]["status"] = "merged"
                    entities[p]["attrs"]["merged_into"] = into
                    _add(entities[p]["evidence"], ev_arts)
            for cid, loop in loops.items():
                if loop["project"] in merged:
                    _move_loop(loop, into, e, edate, ev_arts)
                    subjects.append(cid)
        else:
            applied = False

        if applied:
            events_out.append(
                {
                    "id": eid,
                    "t": e["t"],
                    "date": edate,
                    "type": etype,
                    "summary": e.get("summary", ""),
                    "project": project,
                    "subjects": _dedup([s for s in subjects if s]),
                    "known_on": kd,
                    "artifacts": ev_arts,
                }
            )

    secrets: list[str] = []
    for a in delivered:
        _add(secrets, a.secrets)

    return {
        "world": world.id,
        "date": date,
        "worker": worker,
        "entities": entities,
        "loops": loops,
        "decisions": decisions,
        "events": events_out,
        "unknowable": unknowable,
        "delivered": [a.id for a in delivered],
        "secrets": secrets,
    }


# ---------------------------------------------------------------- helpers for consumers
def is_active(loop: dict[str, Any]) -> bool:
    return loop.get("status") in ACTIVE_STATUSES


def entity_kind(state: dict[str, Any], kind: str) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in state["entities"].items() if v["kind"] == kind}


def project_loops(state: dict[str, Any], project: str) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in state["loops"].items() if v.get("project") == project}


# ---------------------------------------------------------------- internals
def _hist(e: dict[str, Any], changes: dict[str, Any], arts: list[str]) -> dict[str, Any]:
    return {
        "event": e["id"],
        "t": e["t"],
        "date": date_of(e["t"]),
        "type": e["type"],
        "changes": copy.deepcopy(changes),
        "summary": e.get("summary", ""),
        "artifacts": list(arts),
    }


def _move_loop(
    loop: dict[str, Any], target: str, e: dict[str, Any], edate: str, arts: list[str]
) -> None:
    """Move a loop to another project (split or merge). The move is a change to the loop, so
    its artifacts join the loop's evidence like any other update's."""
    loop["project"] = target
    loop["updated"] = max(loop["updated"], edate)
    _add(loop["evidence"], arts)
    loop["history"].append(_hist(e, {"project": target}, arts))


def _loop_subjects(cid: str, loop: dict[str, Any] | None) -> list[str]:
    if loop is None:
        return [cid]
    return [cid, loop["debtor"], loop["creditor"], *loop.get("others", [])]


def _add(dst: list[str], items: list[str]) -> None:
    for x in items:
        if x not in dst:
            dst.append(x)


def _dedup(xs: list[str]) -> list[str]:
    seen: list[str] = []
    for x in xs:
        if x not in seen:
            seen.append(x)
    return seen
