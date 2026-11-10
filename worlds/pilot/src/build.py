"""Build the pilot world files from the authoring modules.

Usage (from the repo root):
    .venv/bin/python worlds/pilot/src/build.py            # write files + run checks
    .venv/bin/python worlds/pilot/src/build.py --check    # checks only

Writes worlds/pilot/world.jsonl, artifacts.plan.jsonl and questions.yaml, and the generated sections of BIBLE.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORLD = HERE.parent
sys.path.insert(0, str(HERE))

import dsl  # noqa: E402
from dsl import ARTS, COMMITS, DECISIONS, EVENTS, KEYS, PEOPLE, PREFIX, QUESTIONS, UNOBSERVABLE, UNREVEALED  # noqa: E402

MODULES = ["cast", "seed", "day1_mon", "day2_tue", "day3_wed", "day4_thu", "day5_fri", "day6_sat", "questions"]


def load_modules() -> None:
    for m in MODULES:
        if (HERE / f"{m}.py").exists():
            __import__(m)


# ---------------------------------------------------------------- id assignment
def assign_ids():
    order = sorted(EVENTS, key=lambda e: (e["t"], e["_seq"]))
    eid = {}
    for i, e in enumerate(order, 1):
        eid[e["_key"]] = f"e-{i:04d}"
    cid, did = {}, {}
    for e in order:
        if e["type"] == "commitment.create":
            cid[e["commitment"]] = f"c-{len(cid) + 1:03d}"
        elif e["type"] == "decision.make":
            did[e["decision"]] = f"d-{len(did) + 1:03d}"
    aid = {}
    counters: Counter = Counter()
    for e in sorted((e for e in EVENTS if e["type"] == "artifact.emit"), key=lambda e: (e["received_at"], e["_seq"])):
        p = PREFIX[e["channel"]]
        counters[p] += 1
        aid[e["artifact"]] = f"{p}-{counters[p]:04d}"
    return order, eid, cid, did, aid


def ent_name(x):
    if x in PEOPLE:
        return PEOPLE[x]["name"]
    ev = KEYS.get(x)
    if ev and ev["type"] == "entity.create":
        return ev["name"]
    return x


def default_say(ev, cid, did):
    t = ev["type"]
    if t == "entity.create":
        if ev["kind"] == "person":
            at = ev["attrs"]
            if at.get("_minor"):
                return f"{ev['name']} ({at.get('_note', 'minor')})"
            return f"{ev['name']} - {at.get('role')} ({ent_name(at.get('org'))})" if at.get("org") else f"{ev['name']} - {at.get('role')}"
        if ev["kind"] == "org":
            return ev["name"]
        return f"project {ev['name']} (aka {', '.join(ev['surface_forms'][:3])}): {ev['attrs'].get('summary', '')}"
    if t == "commitment.create":
        s = f"{ev['what']} [owner: {ent_name(ev['debtor'])}; owed to: {ent_name(ev['creditor'])}]"
        if ev.get("due"):
            s += f"; due {ev['due']}"
        if not ev.get("accepted", True):
            s += "; ONLY SUGGESTED - Mara does not agree to it here"
        s += f"; use the words: {', '.join(repr(k) for k in ev['keywords'])}"
        return s
    if t == "commitment.update":
        ch = dict(ev["changes"])
        for k in ("debtor", "creditor"):
            if k in ch:
                ch[k] = ent_name(ch[k])
        return f"{ev['summary']} (changes: {json.dumps(ch, ensure_ascii=False)})"
    if t == "fact.set":
        v = ev["value"]
        if isinstance(v, list):
            v = ", ".join(ent_name(x) for x in v)
        elif isinstance(v, str) and v in KEYS:
            v = ent_name(v)
        if ev["attribute"] == "summary":
            return f"{ev['summary']}. Current state: {v}"
        return f"{ev['summary']} ({ev['attribute']} = {v})"
    if t == "decision.make":
        return f"decision: {ev['what']} (by {', '.join(ent_name(b) for b in ev['by'])})"
    if t == "decision.reverse":
        return f"{ev['summary']} (reason: {ev['reason']})"
    return ev["summary"]


def default_how(ev, art=None):
    """Default reveal style for a bare event key: state paragraphs and team lists are conveyed indirectly; an AI recap
    reports second-hand; a calendar item implies what it shows."""
    frm = json.dumps((art or {}).get("_plan", {}).get("from") or "")
    if art is not None and "Huddlescribe" in frm and ev["type"].startswith(("commitment.", "decision.")):
        return "second-hand"
    if art is not None and art["channel"] == "calendar" and ev["type"] in ("commitment.resolve", "fact.set"):
        return "implied"
    if ev["type"] == "fact.set":
        if ev["attribute"] in ("summary", "phase"):
            return "indirect"
        if ev["attribute"] == "members":
            return "implied"
    if ev["type"] == "entity.create" and ev["kind"] in ("org", "project"):
        return "indirect"
    return "direct"


def build(write=True):
    load_modules()
    order, eid, cid, did, aid = assign_ids()

    def rc(sym):
        return cid[sym]

    out = []
    for e in order:
        d = {"id": eid[e["_key"]], "t": e["t"], "type": e["type"]}
        t = e["type"]
        if t != "artifact.emit":
            d["summary"] = e["summary"]
        if t == "entity.create":
            d.update({k: e[k] for k in ("entity", "kind", "name", "surface_forms", "attrs")})
            if e["kind"] == "project":
                d["project"] = e["entity"]
        elif t == "fact.set":
            d.update({k: e[k] for k in ("subject", "attribute", "value")})
            if e.get("project"):
                d["project"] = e["project"]
        elif t == "commitment.create":
            d["commitment"] = rc(e["commitment"])
            d.update({k: e[k] for k in ("kind", "what", "debtor", "creditor", "others", "project", "status", "due",
                                        "accepted", "basis", "keywords")})
        elif t == "commitment.update":
            d["commitment"] = rc(e["commitment"])
            d["changes"] = e["changes"]
            if e.get("project"):
                d["project"] = e["project"]
        elif t == "commitment.resolve":
            d["commitment"] = rc(e["commitment"])
            d["status"] = e["status"]
            if e.get("project"):
                d["project"] = e["project"]
        elif t == "decision.make":
            d["decision"] = did[e["decision"]]
            d.update({k: e[k] for k in ("what", "by", "project", "keywords")})
        elif t == "decision.reverse":
            d["decision"] = did[e["decision"]]
            d["reason"] = e["reason"]
            d["project"] = e["project"]
        elif t == "project.split":
            d.update({"project": e["project"], "into": e["into"], "moves": {rc(k): v for k, v in e["moves"].items()}})
        elif t == "project.merge":
            d.update({"projects": e["projects"], "into": e["into"], "project": e["into"]})
        elif t == "artifact.emit":
            a_id = aid[e["artifact"]]
            date = e["received_at"][:10]
            d.update({"artifact": a_id, "channel": e["channel"], "path": f"inbox/{date}/{a_id}.{e['_ext']}",
                      "received_at": e["received_at"], "reveals": [eid[r["key"]] for r in e["_reveals"]],
                      "noise": e["noise"], "challenges": e["challenges"], "secrets": e["secrets"], "title": e["title"],
                      "parent": aid[e["parent"]] if e["parent"] else None})
        out.append(d)

    # ------------------------------------------------ artifact plan
    plan = []
    for e in sorted((e for e in EVENTS if e["type"] == "artifact.emit"), key=lambda e: (e["received_at"], e["_seq"])):
        p = e["_plan"]
        a_id = aid[e["artifact"]]
        reveals = []
        for r in e["_reveals"]:
            ev = KEYS[r["key"]]
            reveals.append({"event": eid[r["key"]], "type": ev["type"], "summary": ev["summary"], "how": ("implied" if e["channel"] == "document" and ev["type"] == "commitment.resolve"
                                    else r["how"] or default_how(ev, e)),
                            "must_say": r["say"] or default_say(ev, cid, did)})
        plan.append({
            "artifact": a_id, "path": f"inbox/{e['received_at'][:10]}/{a_id}.{e['_ext']}", "channel": e["channel"],
            "format": p["format"], "received_at": e["received_at"], "sent_at": p["sent_at"],
            "from": p["from"], "to": p["to"], "cc": p["cc"], "subject_or_title": p["subject_or_title"],
            "participants": p["participants"], "thread": [aid[x] for x in p["thread"]],
            "parent": aid[e["parent"]] if e["parent"] else None, "length": p["length"], "reveals": reveals,
            "must_not_say": p["must_not_say"], "noise": e["noise"], "low_value": p["low_value"],
            "noise_notes": p["noise_notes"],
            "challenges": e["challenges"], "style": p["style"], "secrets": e["secrets"],
        })

    # ------------------------------------------------ questions
    qs = []
    for i, qd in enumerate(QUESTIONS, 1):
        params = {}
        for k, v in qd["params"].items():
            if k == "commitment":
                v = cid[v]
            elif k == "decision":
                v = did[v]
            elif k == "event":
                v = eid[v]
            params[k] = v
        if qd["name_form"]:
            params["name_form"] = qd["name_form"]
        item = {"id": f"q-{i:03d}", "checkpoint": qd["checkpoint"], "template": qd["template"], "params": params}
        if qd["text"]:
            item["text"] = qd["text"]
        if qd["challenges"]:
            item["challenges"] = qd["challenges"]
        if qd["extra_rubric"]:
            item["extra_rubric"] = [
                {**x, "support": [aid[s] for s in x.get("support", [])]} if isinstance(x, dict) else x
                for x in qd["extra_rubric"]]
        qs.append(item)

    ctx = {"order": order, "eid": eid, "cid": cid, "did": did, "aid": aid, "events": out, "plan": plan, "questions": qs}
    if write:
        with open(WORLD / "world.jsonl", "w") as f:
            for d in out:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")
        with open(WORLD / "artifacts.plan.jsonl", "w") as f:
            for p in plan:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
        write_questions(qs)
    return ctx


def write_questions(qs):
    import yaml

    class D(yaml.SafeDumper):
        pass

    def flow(dumper, data):
        return dumper.represent_mapping("tag:yaml.org,2002:map", data, flow_style=True)

    lines = ["# Pilot world question specs (hidden). Generated by src/build.py from src/questions.py.", ""]
    cur = None
    for q in qs:
        if q["checkpoint"] != cur:
            cur = q["checkpoint"]
            lines.append(f"# ---------------- {cur}")
        body = yaml.dump([q], Dumper=D, sort_keys=False, allow_unicode=True, width=200, default_flow_style=None)
        lines.append(body.rstrip())
    (WORLD / "questions.yaml").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------- checks
def check(ctx) -> list[str]:
    errs: list[str] = []
    warns: list[str] = []
    order = ctx["order"]
    revealed_by: dict[str, list[dict]] = defaultdict(list)
    for e in EVENTS:
        if e["type"] == "artifact.emit":
            for r in e["_reveals"]:
                if r["key"] not in KEYS:
                    errs.append(f"{e['artifact']}: reveals unknown key {r['key']}")
                    continue
                if KEYS[r["key"]]["type"] == "artifact.emit":
                    errs.append(f"{e['artifact']}: reveals an artifact event {r['key']}")
                revealed_by[r["key"]].append(e)
                if KEYS[r["key"]]["t"] > e["received_at"]:
                    errs.append(f"{e['artifact']}: reveals future event {r['key']} ({KEYS[r['key']]['t']} > {e['received_at']})")
            if e["parent"] and e["parent"] not in ARTS:
                errs.append(f"{e['artifact']}: unknown parent {e['parent']}")
            if e["parent"] and ARTS[e["parent"]]["received_at"] > e["received_at"]:
                errs.append(f"{e['artifact']}: parent delivered later")
            for th in e["_plan"]["thread"]:
                if th not in ARTS:
                    errs.append(f"{e['artifact']}: unknown thread ref {th}")
                elif ARTS[th]["received_at"] > e["received_at"]:
                    errs.append(f"{e['artifact']}: thread ref {th} delivered later")
            sent = e["_plan"]["sent_at"]
            if sent and sent > e["received_at"]:
                errs.append(f"{e['artifact']}: sent_at after received_at")
    known: dict[str, str] = {}
    for k, arts in revealed_by.items():
        known[k] = min(a["received_at"][:10] for a in arts)
    worker_key = "p-mara-ilves"
    known[worker_key] = "0000-00-00"
    for e in EVENTS:
        k = e["_key"]
        if e["type"] == "artifact.emit" or k == worker_key:
            continue
        hidden = k in UNOBSERVABLE or k in UNREVEALED
        if hidden and k in revealed_by:
            errs.append(f"{k}: marked unobservable/unrevealed but revealed by {[a['artifact'] for a in revealed_by[k]]}")
        if not hidden and k not in revealed_by:
            errs.append(f"{k}: never revealed ({e['type']}: {e.get('summary')})")

    def kn(x):
        return known.get(x)

    def need(ref, by_key, date, what):
        if ref is None:
            return
        rk = ref
        if ref in COMMITS:
            rk = "c:" + ref
        if rk not in KEYS:
            errs.append(f"{by_key}: unknown reference {ref} ({what})")
            return
        kd = kn(rk)
        if kd is None or kd > date:
            (errs if what != "members" else warns).append(
                f"{by_key} (known {date}): {what} {ref} not known until {kd}")

    for e in EVENTS:
        k = e["_key"]
        if e["type"] == "artifact.emit" or k not in known or k == worker_key:
            continue
        date = known[k]
        t = e["type"]
        if t == "entity.create":
            at = e["attrs"]
            if e["kind"] == "person" and at.get("org"):
                need(at["org"], k, date, "org")
            if e["kind"] == "project":
                for f in ("owner", "sponsor"):
                    need(at.get(f), k, date, f)
                for m in at.get("members", []):
                    need(m, k, date, "members")
                for o in at.get("orgs", []):
                    need(o, k, date, "orgs")
        elif t == "fact.set":
            need(e["subject"], k, date, "subject")
            v = e["value"]
            if isinstance(v, str) and v in KEYS and KEYS[v]["type"] == "entity.create":
                need(v, k, date, "value")
            if isinstance(v, list):
                for m in v:
                    if isinstance(m, str) and m in KEYS:
                        need(m, k, date, "members")
        elif t == "commitment.create":
            for f in ("debtor", "creditor", "project"):
                need(e.get(f), k, date, f)
            for o in e.get("others", []):
                need(o, k, date, "others")
        elif t in ("commitment.update", "commitment.resolve"):
            need(e["commitment"], k, date, "commitment")
            for f in ("debtor", "creditor"):
                if f in e.get("changes", {}):
                    need(e["changes"][f], k, date, f)
            ce = COMMITS[e["commitment"]]
            if ce["t"] > e["t"]:
                errs.append(f"{k}: update before create")
        elif t == "decision.make":
            for b in e["by"]:
                need(b, k, date, "by")
            need(e.get("project"), k, date, "project")
        elif t == "decision.reverse":
            need("d:" + e["decision"], k, date, "decision")
        elif t == "project.split":
            need(e["project"], k, date, "project")
            for p in e["into"]:
                need(p, k, date, "into")
            for c in e["moves"]:
                need(c, k, date, "moved loop")
        elif t == "project.merge":
            for p in e["projects"] + [e["into"]]:
                need(p, k, date, "project")
    # working hours
    for e in EVENTS:
        hh = int(e["t"][11:13])
        if hh < 6 or hh > 23:
            warns.append(f"{e['_key']}: unusual hour {e['t']}")
    # questions
    for qd in QUESTIONS:
        for k, v in qd["params"].items():
            if k == "commitment" and v not in COMMITS:
                errs.append(f"question references unknown commitment {v}")
            if k == "decision" and v not in DECISIONS:
                errs.append(f"question references unknown decision {v}")
            if k == "event" and v not in KEYS:
                errs.append(f"question references unknown event {v}")
            if k in ("person", "project") and v not in KEYS:
                errs.append(f"question references unknown entity {v}")
    for w in warns:
        print("WARN", w)
    for x in errs:
        print("ERROR", x)
    return errs


if __name__ == "__main__":
    ctx = build(write="--check" not in sys.argv)
    errs = check(ctx)
    if "--check" not in sys.argv:
        import bible
        import stats

        (WORLD / "BIBLE.md").write_text(bible.render(ctx, stats.md(stats.compute())))
    print(f"{len(EVENTS)} events, {len(ARTS)} artifacts, {len(COMMITS)} commitments, {len(DECISIONS)} decisions, "
          f"{len(QUESTIONS)} questions; {len(errs)} errors")
    sys.exit(1 if errs else 0)
