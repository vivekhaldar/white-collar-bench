"""Error analysis of committed WCB runs (DeepSeek V4.1 Flash vs Qwen3.8-27B, Pi).

Reads results/*/scores-track-{a,b}.json plus gold question files built at each run's own
benchmark revision (DeepSeek c623e77, gold v4; Qwen b66134a, gold v3):

    git fetch --unshallow origin main   # if the clone is shallow
    for rev in c623e77 b66134a; do
      mkdir -p /tmp/wcb-$rev && git archive $rev | tar -x -C /tmp/wcb-$rev
      (cd /tmp/wcb-$rev && PYTHONPATH=. ../../$PWD/.venv/bin/python -m wcb.cli world build --all)
    done
    python results/2026-11-21-error-analysis-deepseek-qwen/error_analysis.py > /tmp/ea.txt

Set WCB_GOLD_DS / WCB_GOLD_QW to use other gold build directories.

Every question gets a WCB weight equal to its share of the headline score
(1/n_bucket_in_cp / n_buckets_in_cp / n_cps_in_world / n_worlds), so per-category
"WCB points lost" sum exactly to 100 - WCB.
"""
import glob
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = str(Path(__file__).resolve().parents[2]) + "/"
RUNS = {
    "DS": REPO + "results/2026-11-11-deepseek-v4.1-flash-1017-pi/",
    "QW": REPO + "results/2026-11-11-qwen3.8-27b-pi/",
}
GOLD = {
    "DS": os.environ.get("WCB_GOLD_DS", "/tmp/wcb-c623e77"),
    "QW": os.environ.get("WCB_GOLD_QW", "/tmp/wcb-b66134a"),
}


def load_gold(root):
    g = {}
    for f in glob.glob(root + "/worlds/**/gold/questions/*.json", recursive=True):
        d = json.load(open(f))
        for q in d["questions"]:
            g[(d["world"], d["checkpoint"], q["id"])] = q
    return g


def weights(rows):
    """Attach WCB weight to each row (rows of a single store arm)."""
    by_cp = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_cp[(r["world"], r["checkpoint"])][r["bucket"]].append(r)
    cps_per_world = defaultdict(int)
    for w, _ in by_cp:
        cps_per_world[w] += 1
    nw = len(cps_per_world)
    for (w, _), buckets in by_cp.items():
        for _b, qs in buckets.items():
            for r in qs:
                r["w"] = 1 / len(qs) / len(buckets) / cps_per_world[w] / nw
    return rows


def classify(r):
    """Split loss (1-score) into components."""
    loss = 1 - r["score"]
    if not r["valid"]:
        return {"invalid": loss}
    if not r["answerable"]:
        return {"false_answer_unanswerable": loss} if loss > 0 else {}
    if r["abstained"]:
        return {"wrong_abstention": loss}
    base_loss = 1 - r["base"]
    cit_loss = r["base"] - r["score"]
    out = {}
    if base_loss > 0:
        out["base_zero" if r["base"] == 0 else "base_partial"] = base_loss
    if cit_loss > 1e-12:
        out["citation_penalty"] = cit_loss
    return out


def pct(x):
    return f"{100*x:.2f}"


def main():
    data = {}
    for m, path in RUNS.items():
        for t in "ab":
            d = json.load(open(path + f"scores-track-{t}.json"))
            for store in ("agent", "oracle"):
                rows = [r for r in d["questions"] if r["store"] == store]
                if not rows:
                    continue
                weights(rows)
                data[(m, t.upper(), store)] = rows
            data[(m, t.upper(), "_report")] = d
    gold = {m: load_gold(GOLD[m]) for m in GOLD}

    out = []
    p = out.append

    # 0. sanity: weighted score == headline
    p("## Sanity: reconstructed WCB vs headline")
    for (m, t, s), rows in data.items():
        if s == "_report":
            continue
        h = data[(m, t, "_report")]["headline"]
        ref = h["wcb"] if s == "agent" else h.get("synthesis")
        p(f"{m} {t} {s}: recon {100*sum(r['w']*r['score'] for r in rows):.4f} headline {ref}")

    arms = [k for k in data if k[2] != "_report"]

    # 1. loss decomposition
    p("\n## Loss decomposition (WCB points; count of affected questions)")
    comps = ["invalid", "wrong_abstention", "false_answer_unanswerable", "base_zero",
             "base_partial", "citation_penalty"]
    p("arm | total lost | " + " | ".join(comps))
    for k in arms:
        rows = data[k]
        agg = defaultdict(float)
        cnt = defaultdict(int)
        for r in rows:
            for c, v in classify(r).items():
                agg[c] += r["w"] * v
                cnt[c] += 1
        tot = sum(agg.values())
        p(f"{k} | {pct(tot)} | " + " | ".join(f"{pct(agg[c])} ({cnt[c]})" for c in comps))

    # counts of full/partial/zero; mean citation
    p("\n## Counts")
    for k in arms:
        rows = data[k]
        full = sum(r["score"] >= 0.99995 for r in rows)
        zero = sum(r["score"] == 0 for r in rows)
        cits = [r["citation"] for r in rows if r["citation"] is not None]
        lt1 = sum(c < 0.99995 for c in cits)
        p(f"{k}: n={len(rows)} full={full} zero={zero} mean_cit={sum(cits)/len(cits):.3f} "
          f"cit<1 on {lt1}/{len(cits)} abstain={sum(r['abstained'] for r in rows)}")

    # 2. by bucket: score, WCB pts lost, base vs cit
    def by(keyf, label, arms_sel, top=None, minn=1):
        p(f"\n## By {label}")
        p(f"{label} | " + " | ".join(f"{'/'.join(a[:2])+('/'+a[2] if a[2]!='agent' else '')} n,mean,ptsLost,citShare" for a in arms_sel))
        keys = set()
        tab = {}
        for a in arms_sel:
            agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0])
            for r in data[a]:
                for kk in keyf(r):
                    x = agg[kk]
                    x[0] += 1
                    x[1] += r["score"]
                    x[2] += r["w"] * (1 - r["score"])
                    cl = classify(r).get("citation_penalty", 0)
                    x[3] += r["w"] * cl
            tab[a] = agg
            keys |= set(agg)
        first = arms_sel[0]
        ks = sorted(keys, key=lambda kk: -tab[first].get(kk, [0, 0, 0, 0])[2])
        ks = [kk for kk in ks if tab[first].get(kk, [0])[0] >= minn]
        if top:
            ks = ks[:top]
        for kk in ks:
            cells = []
            for a in arms_sel:
                x = tab[a].get(kk)
                if not x:
                    cells.append("-")
                    continue
                cells.append(f"{x[0]}, {x[1]/x[0]:.3f}, {pct(x[2])}, {x[3]/x[2]*100 if x[2] else 0:.0f}%")
            p(f"{kk} | " + " | ".join(cells))

    main_arms = [("DS", "A", "agent"), ("DS", "A", "oracle"), ("DS", "B", "agent"),
                 ("QW", "A", "agent"), ("QW", "A", "oracle"), ("QW", "B", "agent")]
    by(lambda r: [r["bucket"]], "bucket", main_arms)
    by(lambda r: [r["template"]], "template", main_arms)
    by(lambda r: r["challenges"], "challenge (multi-label; pts not additive)", main_arms, minn=5)
    by(lambda r: [r["world"]], "world", main_arms)

    # checkpoint position
    def posmap(m, t):
        mp = {}
        for c in data[(m, t, "_report")]["breakdowns"]["by_checkpoint"]:
            rel = c["day_index"] / c["n_days"]
            mp[(c["world"], c["checkpoint"])] = ("early<=1/3" if rel <= 1/3 else
                                                 "mid<=2/3" if rel <= 2/3 else "late>2/3")
        return mp
    pm = {(m, t): posmap(m, t) for m in RUNS for t in "AB"}
    by(lambda r: [pm[(r["_m"], r["_t"])][(r["world"], r["checkpoint"])]], "checkpoint position",
       main_arms) if all(True for _ in [0]) else None

    # 3. Track A ingestion vs synthesis
    for m in RUNS:
        ag = {(r["world"], r["checkpoint"], r["id"]): r for r in data[(m, "A", "agent")]}
        orc = {(r["world"], r["checkpoint"], r["id"]): r for r in data[(m, "A", "oracle")]}
        p(f"\n## {m} Track A: ingestion (oracle-agent) vs synthesis (1-oracle), WCB pts, by template")
        agg = defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
        aggc = defaultdict(lambda: [0, 0.0, 0.0, 0, 0])
        tot_i = tot_s = 0
        for k, a in ag.items():
            o = orc[k]
            ing = a["w"] * (o["score"] - a["score"])
            syn = o["w"] * (1 - o["score"])
            tot_i += ing
            tot_s += syn
            for agg_, keys in ((agg, [a["template"]]), (aggc, a["challenges"])):
                for kk in keys:
                    x = agg_[kk]
                    x[0] += 1
                    x[1] += ing
                    x[2] += syn
                    x[3] += o["score"] - a["score"] > 0.25
                    x[4] += a["score"] - o["score"] > 0.25
        p(f"total ingestion cost {pct(tot_i)}, synthesis loss {pct(tot_s)}")
        p("template | n | ingestion pts | synthesis pts | #agent<<oracle | #agent>>oracle")
        for kk, x in sorted(agg.items(), key=lambda kv: -kv[1][1]):
            p(f"{kk} | {x[0]} | {pct(x[1])} | {pct(x[2])} | {x[3]} | {x[4]}")
        p("challenge (n>=5) | n | ingestion pts | synthesis pts | #agent<<oracle | #agent>>oracle")
        for kk, x in sorted(aggc.items(), key=lambda kv: -kv[1][1]):
            if x[0] >= 5:
                p(f"{kk} | {x[0]} | {pct(x[1])} | {pct(x[2])} | {x[3]} | {x[4]}")
        # per-challenge mean per-question delta
        big = sorted(((o_["score"] - ag[k]["score"], k) for k, o_ in orc.items()), reverse=True)[:15]
        p("largest per-question ingestion drops (oracle-agent):")
        for _dlt, k in big:
            g = gold[m].get(k, {})
            p(f"  {k} {ag[k]['template']} agent={ag[k]['score']:.2f} oracle={orc[k]['score']:.2f} "
              f"abst={ag[k]['abstained']} :: {g.get('text','')[:90]}")

    # 4. A vs B gap
    for m in RUNS:
        a = {(r["world"], r["checkpoint"], r["id"]): r for r in data[(m, "A", "agent")]}
        b = {(r["world"], r["checkpoint"], r["id"]): r for r in data[(m, "B", "agent")]}
        p(f"\n## {m} A-B gap (WCB pts; weights identical in A and B)")
        aggb = defaultdict(lambda: [0, 0.0])
        aggc = defaultdict(lambda: [0, 0.0])
        aggt = defaultdict(lambda: [0, 0.0])
        tot = 0
        for k, ra in a.items():
            rb = b[k]
            gap = ra["w"] * (ra["score"] - rb["score"])
            tot += gap
            for agg_, keys in ((aggb, [ra["bucket"]]), (aggc, ra["challenges"]), (aggt, [ra["template"]])):
                for kk in keys:
                    agg_[kk][0] += 1
                    agg_[kk][1] += gap
        p(f"total gap {pct(tot)}")
        for nm, agg_ in (("bucket", aggb), ("template", aggt), ("challenge", aggc)):
            p(f"{nm}: " + "; ".join(f"{kk} {pct(x[1])} (n={x[0]})" for kk, x in
                                    sorted(agg_.items(), key=lambda kv: -kv[1][1])[:14]))
        # B-only behaviours
        bdec = defaultdict(float)
        for r in data[(m, "B", "agent")]:
            for c, v in classify(r).items():
                bdec[c] += r["w"] * v
        adec = defaultdict(float)
        for r in data[(m, "A", "agent")]:
            for c, v in classify(r).items():
                adec[c] += r["w"] * v
        p("component deltas B-A: " + "; ".join(f"{c} {pct(bdec[c]-adec[c])}" for c in sorted(set(bdec) | set(adec))))

    # 5. DS vs QW on comparable questions
    p("\n## DeepSeek vs Qwen on comparable questions (same text, gold, support in v3 and v4)")
    g3, g4 = gold["QW"], gold["DS"]
    comp = {k for k in g4 if k in g3 and g3[k]["text"] == g4[k]["text"]
            and json.dumps(g3[k]["gold"], sort_keys=True) == json.dumps(g4[k]["gold"], sort_keys=True)
            and sorted(g3[k].get("support", [])) == sorted(g4[k].get("support", []))}
    missing_cp = ("gen-s8-w4", "cp3")
    p(f"comparable questions: {len(comp)} of 745; excluding Qwen's missing gen-s8-w4 cp3 in A agent")
    for t, s in (("A", "agent"), ("A", "oracle"), ("B", "agent")):
        d = {(r["world"], r["checkpoint"], r["id"]): r for r in data[("DS", t, s)]}
        q = {(r["world"], r["checkpoint"], r["id"]): r for r in data[("QW", t, s)]}
        ks = [k for k in comp if not (t == "A" and s == "agent" and k[:2] == missing_cp)]
        both_bad = sum(d[k]["score"] < 0.5 and q[k]["score"] < 0.5 for k in ks)
        ds_bad = sum(d[k]["score"] < 0.5 and q[k]["score"] >= 0.5 for k in ks)
        qw_bad = sum(d[k]["score"] >= 0.5 and q[k]["score"] < 0.5 for k in ks)
        both_zero = sum(d[k]["score"] == 0 and q[k]["score"] == 0 for k in ks)
        p(f"\n{t}/{s}: n={len(ks)} DS mean {sum(d[k]['score'] for k in ks)/len(ks):.3f} QW mean "
          f"{sum(q[k]['score'] for k in ks)/len(ks):.3f}; both<0.5 {both_bad}, DS-only<0.5 {ds_bad}, "
          f"QW-only<0.5 {qw_bad}, both==0 {both_zero}")
        agg = defaultdict(lambda: [0, 0.0, 0.0, 0.0, 0.0])
        aggc = defaultdict(lambda: [0, 0.0, 0.0])
        for k in ks:
            for kk in [d[k]["bucket"] + ":" + d[k]["template"]]:
                x = agg[kk]
                x[0] += 1
                x[1] += d[k]["score"]
                x[2] += q[k]["score"]
                x[3] += d[k]["base"]
                x[4] += q[k]["base"]
            for kk in d[k]["challenges"]:
                aggc[kk][0] += 1
                aggc[kk][1] += d[k]["score"]
                aggc[kk][2] += q[k]["score"]
        p("bucket:template | n | DS score | QW score | DS base | QW base")
        for kk, x in sorted(agg.items(), key=lambda kv: kv[1][1] / kv[1][0]):
            if x[0] >= 4:
                n = x[0]
                p(f"{kk} | {n} | {x[1]/n:.3f} | {x[2]/n:.3f} | {x[3]/n:.3f} | {x[4]/n:.3f}")
        p("challenge (n>=8) | n | DS | QW")
        for kk, x in sorted(aggc.items(), key=lambda kv: kv[1][1] / kv[1][0]):
            if x[0] >= 8:
                p(f"{kk} | {x[0]} | {x[1]/x[0]:.3f} | {x[2]/x[0]:.3f}")
        if s == "agent":
            shared = sorted(ks, key=lambda k: d[k]["score"] + q[k]["score"])[:12]
            p("lowest combined (shared weaknesses):")
            for k in shared:
                p(f"  {k} {d[k]['template']} DS={d[k]['score']:.2f} QW={q[k]['score']:.2f} :: "
                  f"{g4[k]['text'][:90]}")

    # zero-score answerable lists per arm, template counts
    p("\n## Zero-score answerable, non-abstained, valid answers by template")
    for k in arms:
        z = defaultdict(int)
        for r in data[k]:
            if r["answerable"] and r["valid"] and not r["abstained"] and r["score"] == 0:
                z[r["template"]] += 1
        p(f"{k}: " + ", ".join(f"{t} {n}" for t, n in sorted(z.items(), key=lambda kv: -kv[1])))
    p("\n## Wrong abstentions (answerable) and false answers (unanswerable)")
    for k in arms:
        wa = [(r["world"], r["checkpoint"], r["id"], r["template"]) for r in data[k]
              if r["answerable"] and r["abstained"]]
        fa = [(r["world"], r["checkpoint"], r["id"], r["template"]) for r in data[k]
              if not r["answerable"] and not r["abstained"]]
        p(f"{k}: wrong_abst {len(wa)} {wa[:8]}")
        p(f"   false_ans {len(fa)} {fa}")

    print("\n".join(out))


if __name__ == "__main__":
    # tag rows with model/track for position lookup
    _orig = json.load

    def _load(f, *a, **kw):
        d = _orig(f, *a, **kw)
        name = getattr(f, "name", "")
        if isinstance(d, dict) and "questions" in d and "headline" in d:
            m = "DS" if "deepseek" in name else "QW"
            t = "A" if "track-a" in name else "B"
            for r in d["questions"]:
                r["_m"], r["_t"] = m, t
        return d
    json.load = _load
    main()
    sys.exit(0)
