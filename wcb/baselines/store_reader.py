"""Store reader: a deterministic, LLM-free query agent for contract-format stores.

It answers questions by parsing the question text against the benchmark's standard
question phrasings (see wcb/questions/templates.py) and reading the Track A store's front
matter and sections. It never reads inputs, gold or anything outside the workspace.

Purpose: a pipeline sanity check and a rules-based reference point. Run against oracle
stores (``wcb run --skip-ingest``), it shows how much of each question type a store in the
contract format answers directly. It abstains on any question it cannot parse, so custom
question wording, Track B stores and free-form judgment all reduce its score. It is not a
meaningful leaderboard entry.

Run as ``python -m wcb.baselines.store_reader`` in a query session.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from wcb.store.parse import Record, Store, load_store, normalize_ref
from wcb.util.dates import date_of, next_business_day, normalize_date_text
from wcb.util.text import jaccard, normalize, token_set

ACTIVE = ("open", "waiting", "blocked")
SRC_RE = re.compile(r"\[src:\s*([^\]]+)\]")


class Reader:
    def __init__(self, store: Store, today: str):
        self.store = store
        self.today = today
        self.year = int(today[:4])
        self.names: dict[str, set[str]] = {}
        for rec in store.records.values():
            if rec.type in ("person", "project", "org"):
                forms = [rec.meta.get("name") or "", *(rec.meta.get("aliases") or [])]
                email = rec.meta.get("email")
                forms += email if isinstance(email, list) else [email or ""]
                for f in forms:
                    key = normalize(str(f)).lstrip("@")
                    if key:
                        self.names.setdefault(key, set()).add(rec.expected_id)

    # ------------------------------------------------------------ lookups
    def resolve(self, name: str, prefix: str) -> Record | None:
        ids = {
            i for i in self.names.get(normalize(name).lstrip("@"), set()) if i.startswith(prefix)
        }
        return self.store.get(next(iter(ids))) if len(ids) == 1 else None

    def name_of(self, rid: str | None) -> str | None:
        rec = self.store.get(rid) if rid else None
        if rec is None:
            return None
        if rec.expected_id == "people/me":
            return "me"
        return str(rec.meta.get("name") or rec.expected_id)

    def loops(self) -> list[Record]:
        return self.store.of_type("loop")

    def find_loop(self, title: str) -> Record | None:
        want = token_set(title)
        best, score = None, 0.0
        for rec in self.loops():
            s = jaccard(want, token_set(str(rec.meta.get("title", ""))))
            if s > score:
                best, score = rec, s
        return best if score >= 0.5 else None

    def sources(self, rec: Record) -> list[str]:
        out = [str(e.get("source")) for e in rec.meta.get("evidence") or [] if isinstance(e, dict)]
        for m in SRC_RE.finditer(rec.body):
            out += [s.strip() for s in m.group(1).split(",")]
        return list(dict.fromkeys(s for s in out if s))

    def loop_item(self, rec: Record) -> dict[str, Any]:
        m = rec.meta
        owner, cp = (
            normalize_ref(str(m.get("owner") or "")),
            normalize_ref(str(m.get("counterparty") or "")),
        )
        if owner == "people/me":
            direction, other = "i_owe", cp
        elif cp == "people/me":
            direction, other = "owed_to_me", owner
        else:
            direction, other = "other", owner
        return {
            "text": str(m.get("title", "")),
            "counterparty": self.name_of(other),
            "direction": direction,
            "status": m.get("status") if m.get("status") in (*ACTIVE, "done", "dropped") else None,
            "due": m.get("due") or None,
            "cites": [rec.expected_id, *self.sources(rec)],
        }

    def active_loops(self, pred) -> list[Record]:
        out = []
        for rec in self.loops():
            m = rec.meta
            if (
                m.get("kind") == "decision"
                or m.get("accepted") is not True
                or m.get("status") not in ACTIVE
            ):
                continue
            if pred(
                m,
                normalize_ref(str(m.get("owner") or "")),
                normalize_ref(str(m.get("counterparty") or "")),
            ):
                out.append(rec)
        return sorted(out, key=lambda r: (str(r.meta.get("due") or "9999"), r.expected_id))

    # ------------------------------------------------------------ answering
    def answer(self, q: dict[str, Any]) -> dict[str, Any]:
        qtype, text = q["type"], q["text"].strip()
        try:
            ans = self._dispatch(qtype, text)
        except Exception as e:  # noqa: BLE001 - a baseline must never crash the session
            print(f"store_reader: {q['id']}: {e}", file=sys.stderr)
            ans = None
        return ans if ans is not None else {"type": qtype, "abstain": True}

    def _dispatch(self, qtype: str, text: str) -> dict[str, Any] | None:
        for pattern, handler in self._handlers():
            m = re.fullmatch(pattern, text)
            if m:
                out = handler(*m.groups())
                if out is not None and out.get("type") != qtype:
                    return None
                return out
        return None

    def _handlers(self):
        return [
            (r"Who owns (.+)\?", lambda p: self._project_person(p, "owner")),
            (
                r"Who is the executive sponsor of (.+)\?",
                lambda p: self._project_person(p, "sponsor"),
            ),
            (
                r"What is the current target date for (.+)\?",
                lambda p: self._project_field(p, "target_date", "Target date"),
            ),
            (r"What phase is (.+) in\?", lambda p: self._project_field(p, None, "Phase")),
            (
                r"What is currently blocking (.+)\?",
                lambda p: self._project_field(p, None, "Blocker"),
            ),
            (
                r"What is the next step on (.+)\?",
                lambda p: self._project_field(p, None, "Next step"),
            ),
            (
                r"What is the current status of (.+): active, paused, dormant, done or cancelled\?",
                lambda p: self._project_field(p, "status", None),
            ),
            (r"What is the budget for (.+)\?", lambda p: None),
            (r"What is (.+)'s role\?", lambda x: self._person_field(x, "role")),
            (r"What is (.+)'s email address\?", lambda x: self._person_field(x, "email")),
            (
                r"What is my working relationship with (.+)\?",
                lambda x: self._person_field(x, "relationship"),
            ),
            (r"Which organization is (.+) with\?", self._person_org),
            (r'Who is responsible for "(.+)"\?', self._loop_owner),
            (r'When is "(.+)" due\?', self._loop_due),
            (r"What do I (?:currently )?owe (.+)\?", self._i_owe),
            (r"What does (.+) currently owe me\?", self._owed_to_me),
            (r"What loops are open on (.+)\?", self._project_loops),
            (r"What is the status of (.+)\?", self._status),
            (r"What am I working on with (.+)\?", self._brief),
            (r"What changed on (.+) since (.+)\?", self._changes),
            (r"When did we decide to (.+)\?", self._decision_date),
            (r"What should I focus on tomorrow\?", self._focus),
        ]

    # point
    def _project_person(self, pname: str, field: str) -> dict | None:
        proj = self.resolve(pname, "projects/")
        if proj is None:
            return None
        ref = proj.meta.get(field)
        if not ref and field == "sponsor":
            m = re.search(r"Sponsor:\s*([^.\n]+)", proj.section("Knowledge") or "")
            name = m.group(1).strip() if m else None
        else:
            name = self.name_of(normalize_ref(str(ref))) if ref else None
        if not name:
            return None
        return {
            "type": "point",
            "abstain": False,
            "value": name,
            "cites": [proj.expected_id, *self.sources(proj)],
        }

    def _project_field(self, pname: str, meta_key: str | None, label: str | None) -> dict | None:
        proj = self.resolve(pname, "projects/")
        if proj is None:
            return None
        value = proj.meta.get(meta_key) if meta_key else None
        if value in (None, "") and label:
            m = re.search(
                rf"{label}:\s*([^\n]+?)(?:\.\s+[A-Z][a-z ]+:|\.\s*\[src|\.?\s*$)",
                proj.section("Current state") or "",
            )
            value = m.group(1).strip() if m else None
        if value in (None, ""):
            return None
        return {
            "type": "point",
            "abstain": False,
            "value": str(value),
            "cites": [proj.expected_id, *self.sources(proj)],
        }

    def _person_field(self, xname: str, field: str) -> dict | None:
        rec = self.resolve(xname, "people/")
        value = rec.meta.get(field) if rec else None
        if isinstance(value, list):
            value = value[0] if value else None
        if not value:
            return None
        return {"type": "point", "abstain": False, "value": str(value), "cites": [rec.expected_id]}

    def _person_org(self, xname: str) -> dict | None:
        rec = self.resolve(xname, "people/")
        org = (
            self.name_of(normalize_ref(str(rec.meta.get("org"))))
            if rec and rec.meta.get("org")
            else None
        )
        return (
            {"type": "point", "abstain": False, "value": org, "cites": [rec.expected_id]}
            if org
            else None
        )

    def _loop_owner(self, title: str) -> dict | None:
        rec = self.find_loop(title)
        name = self.name_of(normalize_ref(str(rec.meta.get("owner")))) if rec else None
        return (
            {
                "type": "point",
                "abstain": False,
                "value": name,
                "cites": [rec.expected_id, *self.sources(rec)],
            }
            if name
            else None
        )

    def _loop_due(self, title: str) -> dict | None:
        rec = self.find_loop(title)
        due = rec.meta.get("due") if rec else None
        return (
            {
                "type": "point",
                "abstain": False,
                "value": str(due),
                "cites": [rec.expected_id, *self.sources(rec)],
            }
            if due
            else None
        )

    # lists
    def _list(self, recs: list[Record]) -> dict:
        return {"type": "list", "abstain": False, "items": [self.loop_item(r) for r in recs]}

    def _i_owe(self, xname: str) -> dict | None:
        person = self.resolve(xname, "people/")
        if person is None:
            return None
        pid = person.expected_id
        return self._list(
            self.active_loops(
                lambda m, o, c: (
                    o == "people/me"
                    and (c == pid or pid in [normalize_ref(str(x)) for x in m.get("others") or []])
                )
            )
        )

    def _owed_to_me(self, xname: str) -> dict | None:
        person = self.resolve(xname, "people/")
        if person is None:
            return None
        pid = person.expected_id
        return self._list(self.active_loops(lambda m, o, c: o == pid and c == "people/me"))

    def _project_loops(self, pname: str) -> dict | None:
        proj = self.resolve(pname, "projects/")
        if proj is None:
            return None
        pid = proj.expected_id
        return self._list(
            self.active_loops(lambda m, o, c: normalize_ref(str(m.get("project") or "")) == pid)
        )

    # summaries
    def _status(self, pname: str) -> dict | None:
        proj = self.resolve(pname, "projects/")
        if proj is None:
            return None
        current = (proj.section("Current state") or "").strip()
        pid = proj.expected_id
        loops = self.active_loops(lambda m, o, c: normalize_ref(str(m.get("project") or "")) == pid)
        claims = [{"text": f"Status: {proj.meta.get('status')}", "cites": [pid]}]
        if proj.meta.get("target_date"):
            claims.append({"text": f"Target date: {proj.meta['target_date']}", "cites": [pid]})
        for r in loops[:8]:
            claims.append(
                {
                    "text": f"{r.meta.get('title')} (owner: {self.name_of(normalize_ref(str(r.meta.get('owner'))))})",
                    "cites": [r.expected_id, *self.sources(r)],
                }
            )
        return {
            "type": "status",
            "abstain": False,
            "summary": SRC_RE.sub("", current).strip()
            or f"{proj.meta.get('name')} is {proj.meta.get('status')}.",
            "claims": claims,
        }

    def _brief(self, xname: str) -> dict | None:
        person = self.resolve(xname, "people/")
        if person is None:
            return None
        pid = person.expected_id
        claims = []
        for proj in self.store.of_type("project"):
            involved = (
                pid in [normalize_ref(str(x)) for x in proj.meta.get("people") or []]
                or normalize_ref(str(proj.meta.get("owner") or "")) == pid
            )
            if involved and proj.meta.get("status") in ("active", "paused", None):
                claims.append(
                    {
                        "text": f"Shared project: {proj.meta.get('name')}",
                        "cites": [proj.expected_id],
                    }
                )
        for r in self.active_loops(lambda m, o, c: o == "people/me" and c == pid):
            claims.append(
                {
                    "text": f"I owe {person.meta.get('name')}: {r.meta.get('title')}",
                    "cites": [r.expected_id, *self.sources(r)],
                }
            )
        for r in self.active_loops(lambda m, o, c: o == pid and c == "people/me"):
            claims.append(
                {
                    "text": f"{person.meta.get('name')} owes me: {r.meta.get('title')}",
                    "cites": [r.expected_id, *self.sources(r)],
                }
            )
        if person.meta.get("role"):
            claims.append(
                {"text": f"{person.meta.get('name')} is {person.meta['role']}", "cites": [pid]}
            )
        summary = (
            "; ".join(c["text"] for c in claims) or f"Nothing open with {person.meta.get('name')}."
        )
        return {"type": "brief", "abstain": False, "summary": summary, "claims": claims}

    def _changes(self, pname: str, since_text: str) -> dict | None:
        proj = self.resolve(pname, "projects/")
        since = normalize_date_text(since_text, default_year=self.year)
        if proj is None or since is None:
            return None
        items = []
        for line in (proj.section("Log") or "").splitlines():
            m = re.match(r"\s*-\s*(\d{4}-\d{2}-\d{2}):\s*(.+)", line)
            if m and since < m.group(1) <= self.today:
                cites = [s.strip() for g in SRC_RE.findall(m.group(2)) for s in g.split(",")]
                items.append(
                    {
                        "text": SRC_RE.sub("", m.group(2)).strip(),
                        "date": m.group(1),
                        "cites": [proj.expected_id, *cites],
                    }
                )
        return {"type": "change", "abstain": False, "items": items}

    def _decision_date(self, what: str) -> dict | None:
        want = token_set(what)
        best, score = None, 0.0
        for rec in self.loops():
            if rec.meta.get("kind") != "decision":
                continue
            s = jaccard(want, token_set(str(rec.meta.get("title", ""))))
            if s > score:
                best, score = rec, s
        if best is None or score < 0.4 or not best.meta.get("decided_on"):
            return None
        return {
            "type": "temporal",
            "abstain": False,
            "date": date_of(str(best.meta["decided_on"])),
            "cites": [best.expected_id, *self.sources(best)],
        }

    def _focus(self) -> dict:
        tomorrow = next_business_day(self.today)
        mine = self.active_loops(lambda m, o, c: o == "people/me")
        due = [r for r in mine if r.meta.get("due") and str(r.meta["due"]) <= tomorrow]
        rest = [r for r in mine if r not in due]
        items = []
        for r in (due + rest)[:10]:
            it = self.loop_item(r)
            items.append(
                {
                    "text": it["text"],
                    "due": it["due"],
                    "why": "due soon" if r in due else "open and mine",
                    "cites": it["cites"],
                }
            )
        return {"type": "priority", "abstain": False, "items": items}


def main() -> int:
    workspace = Path(os.environ.get("WCB_WORKSPACE", "."))
    qfile = workspace / ".wcb" / "questions.json"
    data = json.loads(qfile.read_text(encoding="utf-8"))
    today = os.environ.get("WCB_DATE") or data.get("date")
    reader = Reader(load_store(workspace), today)
    answers = {q["id"]: reader.answer(q) for q in data["questions"]}
    (workspace / ".wcb" / "answers.json").write_text(
        json.dumps(answers, indent=2) + "\n", encoding="utf-8"
    )
    print(f"answered {sum(not a.get('abstain') for a in answers.values())}/{len(answers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
