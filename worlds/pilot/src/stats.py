"""Calibration and sanity statistics for the pilot world, computed with the gold-state engine.

    .venv/bin/python worlds/pilot/src/stats.py [--md]
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from wcb.world.model import World  # noqa: E402
from wcb.world.state import state_at  # noqa: E402

WD = Path(__file__).resolve().parents[1]


def pct(n, d):
    return f"{100 * n / d:.0f}%" if d else "-"


def compute():
    w = World.load(WD)
    worker = w.worker
    raw = [json.loads(x) for x in (WD / "world.jsonl").read_text().splitlines()]
    ev = {e["id"]: e for e in raw}
    out = {}
    # ---- referential integrity
    problems = []
    for e in raw:
        if e["type"] == "artifact.emit":
            for r in e["reveals"]:
                if r not in ev:
                    problems.append(f"{e['artifact']} reveals missing {r}")
                elif ev[r]["t"] > e["received_at"]:
                    problems.append(f"{e['artifact']} reveals future {r}")
            if e["path"].split("/")[1] != e["received_at"][:10]:
                problems.append(f"{e['artifact']} path date mismatch")
    revealed = {r for e in raw if e["type"] == "artifact.emit" for r in e["reveals"]}
    unrevealed = [e for e in raw if e["type"] != "artifact.emit" and e["id"] not in revealed
                  and not (e["type"] == "entity.create" and e["entity"] == worker)]
    out["problems"] = problems
    out["unrevealed"] = [(e["id"], e["type"], e["summary"]) for e in unrevealed]

    # ---- entities
    ents = [e for e in raw if e["type"] == "entity.create"]
    people = [e for e in ents if e["kind"] == "person"]
    out["people_core"] = sum(1 for e in people if not e["attrs"].get("_minor")) - 1
    out["people_minor"] = sum(1 for e in people if e["attrs"].get("_minor"))
    out["orgs"] = sum(1 for e in ents if e["kind"] == "org")
    out["projects"] = sum(1 for e in ents if e["kind"] == "project")

    # ---- commitments (world truth, all)
    creates = [e for e in raw if e["type"] == "commitment.create"]
    out["loops_total"] = len(creates)
    seed_end = w.seed_end
    out["loops_seed"] = sum(1 for e in creates if e["t"][:10] <= seed_end)
    per_day = Counter(e["t"][:10] for e in creates if e["t"][:10] > seed_end)
    out["new_loops_per_day"] = dict(sorted(per_day.items()))
    out["kind"] = Counter(e["kind"] for e in creates)
    own = Counter()
    for e in creates:
        if e["others"]:
            own["joint"] += 1
        elif e["debtor"] == worker:
            own["worker"] += 1
        else:
            own["others"] += 1
    out["owner"] = own
    out["basis"] = Counter(e["basis"] for e in creates)
    out["suggested"] = sum(1 for e in creates if not e["accepted"])
    ever_due = {e["commitment"] for e in creates if e.get("due")}
    ever_due |= {e["commitment"] for e in raw if e["type"] == "commitment.update" and e["changes"].get("due")}
    out["hard_due"] = len(ever_due)
    out["decisions"] = sum(1 for e in raw if e["type"] == "decision.make")
    out["reversals"] = sum(1 for e in raw if e["type"] == "decision.reverse")

    # ---- gold state per checkpoint / day
    snaps = {}
    for d in [seed_end] + w.episode_days():
        s = state_at(w, d)
        loops = s["loops"]
        st = Counter(l["status"] for l in loops.values())
        wk = Counter(l["status"] for l in loops.values() if l["debtor"] == worker)
        ot = Counter(l["status"] for l in loops.values() if l["debtor"] != worker)
        snaps[d] = {"loops": len(loops), "status": dict(st), "worker_status": dict(wk), "others_status": dict(ot),
                    "people": sum(1 for x in s["entities"].values() if x["kind"] == "person"),
                    "projects": sum(1 for x in s["entities"].values() if x["kind"] == "project"),
                    "decisions": len(s["decisions"]), "unknowable": len(s["unknowable"]),
                    "delivered": len(s["delivered"]), "secrets": len(s["secrets"])}
    out["snapshots"] = snaps

    # ---- artifacts
    arts = list(w.artifacts.values())
    by_day = defaultdict(Counter)
    for a in arts:
        by_day[a.date][a.channel] += 1
    out["artifacts_by_day"] = {d: dict(c) for d, c in sorted(by_day.items())}
    ep = [a for a in arts if a.date in w.episode_days()]
    out["episode_channel_mix"] = Counter(a.channel for a in ep)
    out["episode_artifacts"] = len(ep)
    out["seed_artifacts"] = len(arts) - len(ep)
    out["noise_artifacts"] = sum(1 for a in arts if a.noise)
    batch = [a for a in arts if any(e["artifact"] == a.id for e in raw if e["type"] == "artifact.emit")]
    ch = Counter()
    for a in arts:
        ch.update(set(a.challenges))
    out["challenge_artifacts"] = dict(sorted(ch.items()))
    # loop-level challenges derived from events
    loopch = Counter()
    for e in raw:
        if e["type"] == "commitment.update" and "debtor" in e["changes"]:
            loopch["transfer(events)"] += 1
        if e["type"] == "commitment.update" and e["changes"].get("status") == "open":
            loopch["reopen(events)"] += 1
        if e["type"] == "commitment.update" and e["changes"].get("accepted") is True:
            loopch["endorsement(events)"] += 1
        if e["type"] == "commitment.update" and "due" in e["changes"]:
            loopch["due change(events)"] += 1
        if e["type"] in ("project.split", "project.merge"):
            loopch[e["type"]] += 1
    out["event_challenges"] = dict(loopch)

    # ---- loop lifetimes (world truth): calendar days from creation to the first close
    import datetime as _dt
    created, closed = {}, {}
    for e in raw:
        if e["type"] == "commitment.create":
            created[e["commitment"]] = e["t"][:10]
        elif e["type"] == "commitment.resolve" and e["commitment"] not in closed:
            closed[e["commitment"]] = e["t"][:10]
    life = sorted((_dt.date.fromisoformat(closed[c]) - _dt.date.fromisoformat(created[c])).days for c in closed)
    out["closed_lifetimes"] = life
    ep_life = sorted((_dt.date.fromisoformat(closed[c]) - _dt.date.fromisoformat(created[c])).days
                     for c in closed if created[c] > seed_end)
    out["closed_lifetimes_episode"] = ep_life

    # ---- people per loop (direct parties) and Ramona's participation in creating artifacts
    party = Counter()
    final = state_at(w, w.episode_days()[-1])["loops"]
    for cid_, l in final.items():
        for p in {l["debtor"], l["creditor"], *l["others"]} - {worker}:
            party[p] += 1
    out["party_share"] = party.most_common(6)
    plan = {json.loads(x)["artifact"]: json.loads(x) for x in (WD / "artifacts.plan.jsonl").read_text().splitlines()}
    creators = {}
    for e in raw:
        if e["type"] == "artifact.emit":
            for r in e["reveals"]:
                if ev[r]["type"] == "commitment.create":
                    creators.setdefault(ev[r]["commitment"], []).append(e["artifact"])
    def mentions(a, name):
        p = plan[a]
        blob = json.dumps([p.get("from"), p.get("to"), p.get("cc"), p.get("participants")], ensure_ascii=False)
        return name in blob
    out["ramona_participation"] = sum(1 for c, arts in creators.items() if any(mentions(a, "Ramona Szabo") for a in arts))

    # ---- email value, reveal styles
    ep_email = [p for p in plan.values() if p["channel"] == "email" and p["received_at"][:10] in w.episode_days()]
    out["email_low_value"] = (sum(1 for p in ep_email if p.get("low_value") or p.get("noise")), len(ep_email))
    out["reveal_how"] = Counter(r["how"] for p in plan.values() for r in p["reveals"])
    out["noise_notes"] = sum(1 for p in plan.values() if p.get("noise_notes") and not p.get("noise"))
    return out


def md(o):
    L = []
    cp = o["snapshots"]
    last = max(cp)
    s = cp[last]
    n = s["loops"]
    L.append("| Measure | Target | Actual |")
    L.append("|---|---|---|")
    L.append(f"| Seed artifacts | 35-40 | {o['seed_artifacts']} |")
    L.append(f"| Episode artifacts | 80-85 | {o['episode_artifacts']} |")
    for d, c in o["artifacts_by_day"].items():
        if d > "2027-02-28":
            L.append(f"| Artifacts {d} | Mon 18 / Tue 17 / Wed 8 / Thu 20 / Fri 15 / Sat 4 | {sum(c.values())} ({', '.join(f'{k} {v}' for k, v in sorted(c.items()))}) |")
    em = o["episode_channel_mix"]
    tot = o["episode_artifacts"]
    L.append(f"| Episode channel mix | email 30, chat 28, transcript 12, notes 10, doc 8, note 6, calendar 6 (%) | "
             + ", ".join(f"{k} {pct(v, tot)}" for k, v in sorted(em.items())) + " |")
    L.append(f"| Core people (excl. worker) / minor | ~30 / ~6 | {o['people_core']} / {o['people_minor']} |")
    L.append(f"| Projects (incl. successors) | 8 + new | {o['projects']} |")
    L.append(f"| Commitments total (seed / episode) | ~45 + ~40 | {o['loops_total']} ({o['loops_seed']} / {o['loops_total'] - o['loops_seed']}) |")
    L.append(f"| New commitments per episode day | 5-9 per workday | {', '.join(f'{d[5:]}: {v}' for d, v in o['new_loops_per_day'].items())} |")
    k = o["kind"]
    L.append(f"| Kind task / ask | 55% / 42% (+ decisions) | {pct(k['task'], n)} / {pct(k['ask'], n)} (decisions: {o['decisions']}, reversals {o['reversals']}) |")
    ow = o["owner"]
    L.append(f"| Owner worker / others / joint | 45 / 48 / 7 % | {pct(ow['worker'], n)} / {pct(ow['others'], n)} / {pct(ow['joint'], n)} |")
    b = o["basis"]
    L.append(f"| Basis reported / received / sent / scheduled+inferred | 45 / 30 / 20 / small % | {pct(b['reported'], n)} / {pct(b['received'], n)} / {pct(b['sent'], n)} / {pct(b['scheduled'] + b['inferred'], n)} |")
    L.append(f"| Suggested (accepted: false at creation) | ~10% | {pct(o['suggested'], n)} ({o['suggested']}) |")
    L.append(f"| Hard due date (ever) | ~10% | {pct(o['hard_due'], n)} ({o['hard_due']}) |")
    st = s["status"]
    L.append(f"| Gold status at cp3 done / waiting / open / dropped / blocked | 40 / 28 / 26 / 4 / 2 % | "
             f"{pct(st.get('done', 0), n)} / {pct(st.get('waiting', 0), n)} / {pct(st.get('open', 0), n)} / "
             f"{pct(st.get('dropped', 0), n)} / {pct(st.get('blocked', 0), n)} (n={n}) |")
    L.append(f"| Waiting loops owed by others | most | {s['others_status'].get('waiting', 0)} of {st.get('waiting', 0)} |")
    L.append(f"| Open loops owed by worker | most | {s['worker_status'].get('open', 0)} of {st.get('open', 0)} |")
    L.append(f"| Noise artifacts (noise: true) / substantive briefs with off-topic noise_notes | some | {o['noise_artifacts']} / {o['noise_notes']} |")
    lv, ne = o["email_low_value"]
    L.append(f"| Episode email that is noise or low-value | about 50% | {pct(lv, ne)} ({lv} of {ne}) |")
    life = o["closed_lifetimes"]
    med = life[len(life) // 2] if life else "-"
    le1 = sum(1 for x in life if x <= 1)
    el = o["closed_lifetimes_episode"]
    emed = el[len(el) // 2] if el else "-"
    L.append(f"| Closed-loop lifetime (calendar days, all / episode-created) | median ~1 business day | median {med} / {emed}; "
             f"closed within 1 day: {le1} of {len(life)} (episode-created: {sum(1 for x in el if x <= 1)} of {len(el)}) |")
    top = ", ".join(f"{p[2:]} {pct(c, n)}" for p, c in o["party_share"])
    L.append(f"| Direct-party share of loops (top 6) | top collaborator ~35%, next three 13-15% | {top} |")
    L.append(f"| Ramona in the creating artifact (sender/recipient/participant) | 30-35% | {pct(o['ramona_participation'], o['loops_total'])} |")
    hw = o["reveal_how"]
    L.append(f"| Reveal styles in briefs | varied (round 1: 375 of 394 direct) | " + ", ".join(f"{k} {v}" for k, v in hw.most_common()) + " |")
    L.append("")
    L.append("Gold state per day (knowable): ")
    L.append("")
    L.append("| Date | delivered | people | projects | loops | open | waiting | blocked | done | dropped | decisions | unknowable | secrets |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for d, x in cp.items():
        t = x["status"]
        L.append(f"| {d} | {x['delivered']} | {x['people']} | {x['projects']} | {x['loops']} | {t.get('open', 0)} | {t.get('waiting', 0)} | "
                 f"{t.get('blocked', 0)} | {t.get('done', 0)} | {t.get('dropped', 0)} | {x['decisions']} | {x['unknowable']} | {x['secrets']} |")
    return "\n".join(L)


if __name__ == "__main__" and "--questions" not in sys.argv:
    o = compute()
    if "--md" in sys.argv:
        print(md(o))
    else:
        def conv(x):
            return dict(x) if isinstance(x, Counter) else x
        print(json.dumps({k: conv(v) for k, v in o.items()}, indent=1, default=str))


# ---------------------------------------------------------------- question gold preview (approximate, for authoring)
def preview_questions():
    import yaml
    from wcb.util.dates import next_business_day

    w = World.load(WD)
    worker = w.worker
    raw = {e["id"]: e for e in (json.loads(x) for x in (WD / "world.jsonl").read_text().splitlines())}
    qs = yaml.safe_load((WD / "questions.yaml").read_text())
    cps = {c["id"]: c["date"] for c in w.checkpoints()}
    states = {d: state_at(w, d) for d in set(cps.values())}
    rows = []
    for q in qs:
        d = cps[q["checkpoint"]]
        s = states[d]
        p = q["params"]
        t = q["template"]
        loops = s["loops"]
        act = {k: v for k, v in loops.items() if v["status"] in ("open", "waiting", "blocked") and v["accepted"]}
        if t == "project_attr":
            ent = s["entities"].get(p["project"])
            g = ent["attrs"].get(p["attribute"]) if ent else None
        elif t == "person_attr":
            ent = s["entities"].get(p["person"])
            g = ent["attrs"].get(p["attribute"]) if ent else None
        elif t == "loop_owner":
            g = loops.get(p["commitment"], {}).get("debtor")
        elif t == "loop_due":
            g = loops.get(p["commitment"], {}).get("due")
        elif t == "i_owe":
            g = [f"{k} {v['status']} {v['due'] or ''} {v['what']}" for k, v in act.items()
                 if v["debtor"] == worker and (v["creditor"] == p["person"] or p["person"] in v["others"])]
        elif t == "owed_to_me":
            g = [f"{k} {v['status']} {v['what']}" for k, v in act.items() if v["debtor"] == p["person"] and v["creditor"] == worker]
        elif t == "project_loops":
            g = [f"{k} {v['status']} {v['debtor'][2:]} {v['what']}" for k, v in act.items() if v["project"] == p["project"]]
        elif t == "project_changes":
            g = [f"{e['date']} {e['type']} {e['summary']}" for e in s["events"]
                 if e["project"] == p["project"] and e["date"] > str(p["since"]) and e["type"] != "entity.create"]
        elif t == "decision_date":
            g = s["decisions"].get(p["decision"], {}).get("made_on")
        elif t == "event_date":
            g = next((e["date"] for e in s["events"] if e["id"] == p["event"]), None)
        elif t == "focus_tomorrow":
            nb = next_business_day(d)
            g = [f"{k} due {v['due']} {v['what']}" for k, v in act.items()
                 if v["debtor"] == worker and v["due"] and v["due"] <= nb]
        elif t == "project_status":
            ent = s["entities"][p["project"]]
            g = f"[{ent['attrs'].get('status')}] owner={ent['attrs'].get('owner')} {ent['attrs'].get('summary')}"
        elif t == "person_brief":
            g = [f"{k} {v['status']} {v['what']}" for k, v in act.items()
                 if p["person"] in (v["debtor"], v["creditor"], *v["others"])]
        else:
            g = "?"
        rows.append((q["id"], q["checkpoint"], t, q.get("text", ""), g))
    for r in rows:
        print(f"\n{r[0]} {r[1]} {r[2]}: {r[3]}")
        g = r[4]
        if isinstance(g, list):
            print(f"   ({len(g)} items)")
            for x in g:
                print("   -", x)
        else:
            print("   =>", g if g not in (None, "", []) else "UNANSWERABLE/EMPTY")


if __name__ == "__main__" and "--questions" in sys.argv:
    preview_questions()
