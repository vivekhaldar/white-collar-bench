"""Store integrity score (SIS) for Track A stores (docs/scoring.md, "Store integrity").

After every ingestion day the agent's store is compared with the knowable gold state of that
day (docs/formats.md §2). `store_integrity` returns six sub-metrics in [0, 1] and their mean
on a 0-100 scale:

| Metric | What it measures |
|---|---|
| `entity_f1` | person, org and project records mapped to knowable world entities |
| `loop_f1` | loop records matched to knowable commitments and decisions |
| `field_accuracy` | status, owner, counterparty, due date and accepted flag of matched loops |
| `freshness` | matched loops and projects that do not show a superseded value as current |
| `groundedness` | loop records with at least one delivered artifact as evidence |
| `validity` | contract-validator errors per record |

``SIS = 100 x mean(entity_f1, loop_f1, field_accuracy, freshness, groundedness, validity)``

**Mapping records to entities.** Every person, org and project record offers *forms*: its
`name`, its `aliases`, and its `email` (people) or `domain` (orgs). Gold offers, for every
entity knowable at the date, its `name`, `surface_forms`, `email` and `domain`. Forms are
compared as whole normalized phrases (case, accents and punctuation ignored, a leading `@` or
`the` dropped), and only against entities of the record's own kind. A form shared by several
knowable entities, such as a first name two people have, is *ambiguous* and identifies no one.

* `people/me` always maps to the worker.
* A record whose unambiguous forms all point to one entity is **mapped** to it.
* A record whose unambiguous forms point to several entities is a **wrong merge**: it maps to
  one of them (the one its `name` names, else the one most forms name) and *absorbs* the rest.
* A record with only ambiguous forms is **unresolved**; one with no matching form at all is
  **unmatched** (for example a record for something no delivered input mentions).
* Minor entities (`attrs._minor`, such as a newsletter sender) are ignored on both sides: they
  are not gold, and records that map only to them are neither rewarded nor penalized.

Entity F1 then counts a true positive for every knowable entity that some record maps to.
Every other record is a false positive (a duplicate, i.e. a second record for an entity that is
already mapped, an unresolved record, an unmatched record); every knowable entity no record maps
to is a false negative, which includes an entity absorbed by a wrong merge and not kept anywhere
else.

**Matching loops.** Gold loops are all knowable commitments (any status, including suggested
ones) and all knowable decisions. Each loop record becomes a predicted item (its `title`, the
name of its owner, the name of the *other party*, and its evidence sources as citations) and
is matched one-to-one to gold with `wcb.grade.matching.match_items`, the same procedure list
questions use. The other party is the person on the far side of the loop from the worker:
the counterparty when the worker owes, the owner when the worker is owed (`other_party`).

Everything here is deterministic given the judge.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from wcb.contract.validate import validate_store
from wcb.grade.answers import ScoreContext, due_credit, f1, status_credit
from wcb.grade.matching import match_items
from wcb.store.parse import Record, Store, load_store, normalize_ref
from wcb.util.dates import date_of
from wcb.util.text import normalize
from wcb.world.model import World

#: The six sub-metrics, in the order they are reported.
METRICS = ("entity_f1", "loop_f1", "field_accuracy", "freshness", "groundedness", "validity")

#: Store directory -> the entity kind its records describe.
ENTITY_DIRS = {"people": "person", "orgs": "org", "projects": "project"}

#: Record ID of the worker's own record (contract/CONTRACT.md §2.1).
WORKER_RECORD = "people/me"

#: Commitment fields graded by `field_accuracy`, in report order.
LOOP_FIELDS = ("status", "owner", "counterparty", "due", "accepted")

#: Decision status in gold state -> the store status that represents it.
DECISION_STATUS = {"made": "done", "reversed": "reversed"}

_WORD = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------- entry point
def store_integrity(store_root: Path, state: dict, world: World, judge: Any) -> dict:
    """Grade the store at `store_root` against the gold state `state` of the same date.

    `judge` confirms loop matches (`wcb.grade.judge.make_judge`). Returns a dict with the six
    sub-metrics in [0, 1] (`METRICS`), `sis` on a 0-100 scale, and `details` with the
    diagnostics behind each number (record mappings, matches, stale and ungrounded records,
    validator error counts). Raises FileNotFoundError if `store_root` is not a directory.
    """
    store = load_store(Path(store_root))
    ctx = ScoreContext.from_state(world, state, store_root=Path(store_root))

    mapping = map_entity_records(store, state)
    entity = entity_scores(mapping, state)
    pairs, loops = loop_scores(store, state, mapping, judge, ctx)
    fields = field_scores(pairs, store, state, mapping)
    fresh = freshness_score(pairs, store, state, mapping)
    grounded = groundedness_score(store, state)
    valid = validity_score(Path(store_root), store, state)

    out = {
        "entity_f1": entity["f1"],
        "loop_f1": loops["f1"],
        "field_accuracy": fields["score"],
        "freshness": fresh["score"],
        "groundedness": grounded["score"],
        "validity": valid["score"],
    }
    out["sis"] = 100.0 * sum(out[m] for m in METRICS) / len(METRICS)
    out["details"] = {
        "date": state.get("date"),
        "entities": entity,
        "loops": loops,
        "fields": fields,
        "freshness": fresh,
        "groundedness": grounded,
        "validity": valid,
    }
    return out


# ---------------------------------------------------------------- entity mapping
def alias_key(form: Any) -> str:
    """A form as a normalized phrase: lowercase ASCII words joined by single spaces.

    `"Marisol Teague"`, `"marisol  teague"` and `"@Marisol-Teague"` all give `"marisol teague"`; an email
    `"marisol.teague@brenwick.example"` gives `"marisol teague brenwick example"`.
    """
    return " ".join(_WORD.findall(normalize(str(form))))


def form_keys(form: Any) -> set[str]:
    """Lookup keys for a form: its `alias_key`, plus the key without a leading 'the'."""
    key = alias_key(form)
    keys = {key} if key else set()
    if key.startswith("the ") and len(key) > 4:
        keys.add(key[4:])
    return keys


def _strings(value: Any) -> list[str]:
    """A string or a list of strings as a list (anything else is dropped)."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if isinstance(v, str)]
    return []


def entity_forms(entity: dict) -> list[str]:
    """Gold forms of an entity: name, surface forms, email(s) and (orgs) domain."""
    attrs = entity.get("attrs") or {}
    return [
        *_strings(entity.get("name")),
        *_strings(entity.get("surface_forms")),
        *_strings(attrs.get("email")),
        *_strings(attrs.get("domain")),
    ]


def record_forms(rec: Record) -> list[str]:
    """Forms a store record offers: name, aliases, email(s) and (orgs) domain."""
    meta = rec.meta or {}
    return [
        *_strings(meta.get("name")),
        *_strings(meta.get("aliases")),
        *_strings(meta.get("email")),
        *_strings(meta.get("domain")),
    ]


def build_alias_index(state: dict) -> dict[str, dict[str, set[str]]]:
    """Kind -> form key -> IDs of the knowable entities with that form (minor ones included)."""
    index: dict[str, dict[str, set[str]]] = {k: {} for k in ENTITY_DIRS.values()}
    for eid, ent in state["entities"].items():
        table = index.setdefault(ent.get("kind", ""), {})
        for form in entity_forms(ent):
            for key in form_keys(form):
                table.setdefault(key, set()).add(eid)
    return index


def is_minor(entity: dict | None) -> bool:
    return bool(((entity or {}).get("attrs") or {}).get("_minor"))


@dataclass
class EntityMatch:
    """How one person, org or project record maps to world entities.

    `status` is one of `mapped`, `merged` (wrong merge), `duplicate` (a second record for an
    entity already mapped), `unresolved` (only ambiguous forms), `unmatched` (no form matches
    a knowable entity) or `minor` (maps only to minor entities; ignored).
    """

    record: str
    kind: str
    status: str
    entity: str | None = None
    absorbed: list[str] = field(default_factory=list)
    forms: dict[str, list[str]] = field(default_factory=dict)  # form -> entity IDs it names

    @property
    def counted(self) -> bool:
        """Whether the record counts as a prediction for Entity F1 (minor records do not)."""
        return self.status != "minor"

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"status": self.status, "entity": self.entity}
        if self.absorbed:
            d["absorbed"] = list(self.absorbed)
        return d


def map_record(rec: Record, kind: str, index: dict[str, set[str]], state: dict) -> EntityMatch:
    """Map one record to entities of `kind` (see the module docstring). Never marks duplicates."""
    entities = state["entities"]
    if rec.expected_id == WORKER_RECORD:
        return EntityMatch(rec.expected_id, kind, "mapped", state["worker"])
    forms: dict[str, list[str]] = {}
    for form in record_forms(rec):
        ids: set[str] = set()
        for key in form_keys(form):
            ids |= index.get(key, set())
        if ids:
            forms[form] = sorted(ids)
    named: Counter[str] = Counter()
    for ids in forms.values():
        if len(ids) == 1:
            named[ids[0]] += 1
    minor = {e for e in named if is_minor(entities.get(e))}
    real = {e: n for e, n in named.items() if e not in minor}
    if not real:
        if minor:
            return EntityMatch(rec.expected_id, kind, "minor", sorted(minor)[0], forms=forms)
        status = "unresolved" if forms else "unmatched"
        return EntityMatch(rec.expected_id, kind, status, forms=forms)
    if len(real) == 1:
        return EntityMatch(rec.expected_id, kind, "mapped", next(iter(real)), forms=forms)
    name_ids = [
        ids for form, ids in forms.items() if form in _strings((rec.meta or {}).get("name"))
    ]
    by_name = (
        name_ids[0][0] if name_ids and len(name_ids[0]) == 1 and name_ids[0][0] in real else None
    )
    primary = by_name or sorted(real, key=lambda e: (-real[e], e))[0]
    absorbed = sorted(e for e in real if e != primary)
    return EntityMatch(rec.expected_id, kind, "merged", primary, absorbed, forms)


def map_entity_records(store: Store, state: dict) -> dict[str, EntityMatch]:
    """Record ID -> `EntityMatch` for every person, org and project record in the store.

    When several records map to the same entity, the first one keeps its status and the
    others become `duplicate`. "First" prefers `people/me`, then cleanly mapped records over
    wrong merges, then record ID order, so the outcome does not depend on file order.
    """
    index = build_alias_index(state)
    matches: dict[str, EntityMatch] = {}
    for folder, kind in ENTITY_DIRS.items():
        for rec in store.records.values():
            if rec.expected_id.split("/", 1)[0] == folder:
                matches[rec.expected_id] = map_record(rec, kind, index.get(kind, {}), state)

    def rank(m: EntityMatch) -> tuple:
        return (m.record != WORKER_RECORD, m.status != "mapped", m.record)

    seen: set[str] = set()
    for m in sorted(matches.values(), key=rank):
        if m.status not in ("mapped", "merged") or m.entity is None:
            continue
        if m.entity in seen:
            m.status = "duplicate"
        seen.add(m.entity)
    return dict(sorted(matches.items()))


def gold_entities(state: dict) -> list[str]:
    """IDs of the knowable, non-minor people, orgs and projects (Entity F1's gold set)."""
    kinds = set(ENTITY_DIRS.values())
    return sorted(
        eid
        for eid, ent in state["entities"].items()
        if ent.get("kind") in kinds and not is_minor(ent)
    )


def entity_scores(mapping: dict[str, EntityMatch], state: dict) -> dict:
    """Entity F1 with its counts and the records and entities behind each error."""
    gold = gold_entities(state)
    found = {m.entity for m in mapping.values() if m.status in ("mapped", "merged")}
    tp = len(found & set(gold))
    counted = [m for m in mapping.values() if m.counted]
    fp = len(counted) - tp
    fn = len(gold) - tp
    precision = tp / len(counted) if counted else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else (1.0 if not counted else 0.0)
    score = 1.0 if not gold and not counted else f1(precision, recall)
    return {
        "f1": score,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "missing": [e for e in gold if e not in found],
        "false_positives": [m.record for m in counted if m.status not in ("mapped", "merged")],
        "wrong_merges": [
            {"record": m.record, "entity": m.entity, "absorbed": m.absorbed}
            for m in mapping.values()
            if m.absorbed
        ],
        "records": {rid: m.to_dict() for rid, m in mapping.items()},
    }


def entity_of(ref: Any, mapping: dict[str, EntityMatch], worker: str) -> str | None:
    """The world entity a record link (e.g. `people/cora-velez`) stands for, or None.

    `people/me` is the worker. Any other link counts only if its record exists and maps to an
    entity (duplicates and wrong merges map to their entity too).
    """
    if not isinstance(ref, str) or not ref.strip():
        return None
    rid = normalize_ref(ref)
    if rid == WORKER_RECORD:
        return worker
    m = mapping.get(rid)
    return m.entity if m and m.status in ("mapped", "merged", "duplicate") else None


# ---------------------------------------------------------------- loops
def other_party(debtor: Any, creditor: Any, worker: str) -> Any:
    """The person on the other side of a loop from the worker's point of view.

    The creditor when the worker owes, the debtor when the worker is owed, else the creditor.
    This is how list questions name a loop's counterparty, and it keeps the matcher's
    "same counterparty" candidates small: the worker is never the shared counterparty.
    """
    return debtor if creditor == worker and debtor != worker else creditor


def gold_loop_items(state: dict) -> list[dict]:
    """Gold items for loop matching: every knowable commitment, then every knowable decision.

    Each item has `loop` (world ID), `what`, `counterparty` (`other_party`; None for
    decisions), `keywords` and `support` (evidence artifacts), as list-question gold does.
    Status and due date are left out: they do not decide whether two items are the same loop,
    and leaving them out lets an LLM judge's cache serve the same pair on every day.
    """
    worker = state["worker"]
    items = []
    for cid, loop in state.get("loops", {}).items():
        items.append(
            {
                "loop": cid,
                "what": loop.get("what", ""),
                "counterparty": other_party(loop.get("debtor"), loop.get("creditor"), worker),
                "keywords": list(loop.get("keywords") or []),
                "support": list(loop.get("evidence") or []),
            }
        )
    for did, dec in state.get("decisions", {}).items():
        items.append(
            {
                "loop": did,
                "what": dec.get("what", ""),
                "counterparty": None,
                "keywords": list(dec.get("keywords") or []),
                "support": list(dec.get("evidence") or []),
            }
        )
    return items


def evidence_sources(meta: dict) -> list[str]:
    """Artifact IDs in a loop record's `evidence` (entries may be mappings or bare strings)."""
    out = []
    ev = meta.get("evidence")
    for entry in ev if isinstance(ev, list) else []:
        src = entry.get("source") if isinstance(entry, dict) else entry
        if isinstance(src, str) and src.strip():
            out.append(src.strip())
    return out


def ref_name(store: Store, ref: Any) -> str | None:
    """Display name for a record link: the linked record's `name`, else words from its slug.

    `people/me` without a readable record gives "me", which graders resolve to the worker.
    """
    if not isinstance(ref, str) or not ref.strip():
        return None
    rec = store.get(ref)
    name = (rec.meta or {}).get("name") if rec else None
    if isinstance(name, str) and name.strip():
        return name.strip()
    rid = normalize_ref(ref)
    if rid == WORKER_RECORD:
        return "me"
    return rid.rsplit("/", 1)[-1].replace("-", " ")


def loop_title(rec: Record) -> str:
    """A loop record's `title`, or the first non-empty body line when the title is missing."""
    title = (rec.meta or {}).get("title")
    if isinstance(title, str) and title.strip():
        return title.strip()
    for line in rec.body.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            return line.strip()
    return ""


def loop_record_item(
    rec: Record, store: Store, mapping: dict[str, EntityMatch], worker: str
) -> dict:
    """A loop record as a predicted list item for `match_items`.

    `text` is the title, `owner` the owner record's name, `counterparty` the name of the
    other party (`other_party` of the owner and counterparty links, resolved through the
    entity mapping), and `cites` the evidence sources.
    """
    meta = rec.meta or {}
    owner_ref, cp_ref = meta.get("owner"), meta.get("counterparty")
    owner_is_worker = entity_of(owner_ref, mapping, worker) == worker
    cp_is_worker = entity_of(cp_ref, mapping, worker) == worker
    other_ref = owner_ref if cp_is_worker and not owner_is_worker else cp_ref
    item = {"text": loop_title(rec), "cites": evidence_sources(meta)}
    owner, other = ref_name(store, owner_ref), ref_name(store, other_ref)
    if owner:
        item["owner"] = owner
    if other:
        item["counterparty"] = other
    return item


def loop_scores(
    store: Store, state: dict, mapping: dict[str, EntityMatch], judge: Any, ctx: ScoreContext
) -> tuple[list[tuple[Record, dict]], dict]:
    """Match loop records to gold loops; returns (matched (record, gold item) pairs, Loop F1)."""
    records = store.of_type("loop")
    gold = gold_loop_items(state)
    preds = [loop_record_item(r, store, mapping, state["worker"]) for r in records]
    pairs = match_items(preds, gold, judge, kind="loop", ctx=ctx) if preds and gold else []
    tp = len(pairs)
    precision = tp / len(preds) if preds else (1.0 if not gold else 0.0)
    recall = tp / len(gold) if gold else (1.0 if not preds else 0.0)
    score = 1.0 if not preds and not gold else f1(precision, recall)
    matched_pred, matched_gold = {i for i, _ in pairs}, {j for _, j in pairs}
    details = {
        "f1": score,
        "precision": precision,
        "recall": recall,
        "tp": tp,
        "fp": len(preds) - tp,
        "fn": len(gold) - tp,
        "matches": {records[i].expected_id: gold[j]["loop"] for i, j in pairs},
        "unmatched_records": [
            r.expected_id for i, r in enumerate(records) if i not in matched_pred
        ],
        "missing": [g["loop"] for j, g in enumerate(gold) if j not in matched_gold],
    }
    return [(records[i], gold[j]) for i, j in pairs], details


# ---------------------------------------------------------------- field accuracy
def _status(value: Any) -> str | None:
    return str(value).strip().lower() if isinstance(value, str) and value.strip() else None


def commitment_fields(
    meta: dict, gold: dict, mapping: dict[str, EntityMatch], worker: str
) -> dict[str, float]:
    """Per-field credit of a loop record against a gold commitment (`LOOP_FIELDS`).

    status: 1 for the same status, 0.5 if both are active; owner: the owner record maps to the
    debtor; counterparty: maps to the creditor; due: same date or both empty; accepted: equal.
    """
    accepted = meta.get("accepted")
    return {
        "status": status_credit(_status(meta.get("status")), gold.get("status")),
        "owner": float(entity_of(meta.get("owner"), mapping, worker) == gold.get("debtor")),
        "counterparty": float(
            entity_of(meta.get("counterparty"), mapping, worker) == gold.get("creditor")
        ),
        "due": due_credit(meta.get("due"), gold.get("due")),
        "accepted": float(isinstance(accepted, bool) and accepted == bool(gold.get("accepted"))),
    }


def decision_fields(meta: dict, gold: dict) -> dict[str, float]:
    """A decision record's status credit: `done` for a made decision, `reversed` for a reversed one."""
    want = DECISION_STATUS.get(gold.get("status"), gold.get("status"))
    return {"status": float(_status(meta.get("status")) == want)}


def field_scores(
    pairs: list[tuple[Record, dict]], store: Store, state: dict, mapping: dict[str, EntityMatch]
) -> dict:
    """Field accuracy: mean, over matched loops, of the mean credit of the loop's fields.

    With no matched loops the score is 1 if the store and gold both have no loops, else 0.
    """
    per_loop = {}
    for rec, item in pairs:
        gid = item["loop"]
        meta = rec.meta or {}
        if gid in state.get("loops", {}):
            parts = commitment_fields(meta, state["loops"][gid], mapping, state["worker"])
        else:
            parts = decision_fields(meta, state["decisions"][gid])
        per_loop[rec.expected_id] = {
            "gold": gid,
            "credit": sum(parts.values()) / len(parts),
            **parts,
        }
    if per_loop:
        score = sum(p["credit"] for p in per_loop.values()) / len(per_loop)
    else:
        no_loops = not store.of_type("loop") and not gold_loop_items(state)
        score = 1.0 if no_loops else 0.0
    return {"score": score, "per_loop": per_loop}


# ---------------------------------------------------------------- freshness
def _date_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return date_of(str(value))


def superseded_loop_values(loop: dict) -> dict[str, set]:
    """Values a commitment's status, due date and debtor had before their current one.

    Empty values (no due date yet) are not counted: a missing due date is an omission, which
    field accuracy grades, not a stale fact.
    """
    out: dict[str, set] = {"status": set(), "due": set(), "debtor": set()}
    for h in loop.get("history") or []:
        changes = h.get("changes") or {}
        for key in out:
            if changes.get(key) not in (None, ""):
                out[key].add(_date_or_none(changes[key]) if key == "due" else changes[key])
    out["status"].discard(loop.get("status"))
    out["due"].discard(_date_or_none(loop.get("due")))
    out["debtor"].discard(loop.get("debtor"))
    return out


def stale_loop_fields(
    meta: dict, gold_id: str, state: dict, mapping: dict[str, EntityMatch]
) -> list[str]:
    """Fields of a matched loop record that show a superseded value instead of the current one."""
    if gold_id in state.get("decisions", {}):
        dec = state["decisions"][gold_id]
        reversed_now = dec.get("status") == "reversed"
        return ["status"] if reversed_now and _status(meta.get("status")) == "done" else []
    old = superseded_loop_values(state["loops"][gold_id])
    stale = []
    if _status(meta.get("status")) in old["status"]:
        stale.append("status")
    if _date_or_none(meta.get("due")) in old["due"]:
        stale.append("due")
    if entity_of(meta.get("owner"), mapping, state["worker"]) in old["debtor"]:
        stale.append("owner")
    return stale


def superseded_attr_values(entity: dict, attr: str) -> set:
    """Earlier values of an entity attribute (from `attr_history`), minus the current value."""
    current = (entity.get("attrs") or {}).get(attr)
    values = {
        h.get("value")
        for h in (entity.get("attr_history") or {}).get(attr) or []
        if isinstance(h.get("value"), str) and h.get("value")
    }
    values.discard(current)
    return values


def stale_project_fields(meta: dict, entity: dict) -> list[str]:
    """Fields of a project record that show a superseded status or target date."""
    stale = []
    if _status(meta.get("status")) in {
        _status(v) for v in superseded_attr_values(entity, "status")
    }:
        stale.append("status")
    old_dates = {_date_or_none(v) for v in superseded_attr_values(entity, "target_date")}
    if _date_or_none(meta.get("target_date")) in old_dates:
        stale.append("target_date")
    return stale


def freshness_score(
    pairs: list[tuple[Record, dict]], store: Store, state: dict, mapping: dict[str, EntityMatch]
) -> dict:
    """Freshness: 1 - share of checked records that present a superseded value as current.

    Checked records are the matched loops (status, due date, owner; decisions: a reversed
    decision still marked `done`) and every project record mapped to a project entity
    (status, target date). With nothing to check the score is 1.
    """
    stale: list[dict] = []
    checked = 0
    for rec, item in pairs:
        checked += 1
        fields = stale_loop_fields(rec.meta or {}, item["loop"], state, mapping)
        if fields:
            stale.append({"record": rec.expected_id, "gold": item["loop"], "fields": fields})
    for rid, m in mapping.items():
        if m.kind != "project" or m.status not in ("mapped", "merged", "duplicate"):
            continue
        rec = store.records.get(rid)
        if rec is None or m.entity not in state["entities"]:
            continue
        checked += 1
        fields = stale_project_fields(rec.meta or {}, state["entities"][m.entity])
        if fields:
            stale.append({"record": rid, "gold": m.entity, "fields": fields})
    score = 1.0 - len(stale) / checked if checked else 1.0
    return {"score": score, "checked": checked, "stale": stale}


# ---------------------------------------------------------------- groundedness and validity
def groundedness_score(store: Store, state: dict) -> dict:
    """Groundedness: 1 - share of loop records with no evidence source among delivered artifacts.

    With no loop records the score is 1.
    """
    delivered = set(state.get("delivered") or [])
    records = store.of_type("loop")
    ungrounded = [
        r.expected_id
        for r in records
        if not any(s in delivered for s in evidence_sources(r.meta or {}))
    ]
    score = 1.0 - len(ungrounded) / len(records) if records else 1.0
    return {"score": score, "loop_records": len(records), "ungrounded": ungrounded}


def validity_score(store_root: Path, store: Store, state: dict) -> dict:
    """Validity: 1 - min(1, validator errors / records), with planted secrets checked.

    Uses `wcb.contract.validate.validate_store` with the gold state's `secrets` (so a leaked
    passcode is an error) and `delivered`. Only error-severity issues count; a store with no
    records counts as one record.
    """
    issues = validate_store(
        store_root,
        secrets=list(state.get("secrets") or []),
        delivered=set(state.get("delivered") or []),
    )
    errors = [i for i in issues if i.severity == "error"]
    n = len(store.records)
    score = 1.0 - min(1.0, len(errors) / max(1, n))
    return {
        "score": score,
        "records": n,
        "errors": len(errors),
        "by_code": dict(sorted(Counter(i.code for i in errors).items())),
    }
