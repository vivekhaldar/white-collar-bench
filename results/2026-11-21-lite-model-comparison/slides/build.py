#!/usr/bin/env python3
"""Build the WCB-lite results deck: one self-contained HTML file with inline SVG charts.

    python results/2026-11-21-lite-model-comparison/slides/build.py

Reads ../data.json (written by ../compare.py) and writes index.html next to this script.
Every chart number comes from data.json; the failure examples quote the runs' saved answers
(cited on each slide). Open index.html in a browser: arrow keys or clicks move between
slides, F toggles full screen. Slides are 16:9 and scale to the window.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE.parent / "data.json").read_text())["models"]
ORDER = ["Opus 5.5", "Sonnet 5.5", "Haiku 5.5", "GPT-6.1 Sol"]
ROOT = HERE.parents[2]


def earlier_runs() -> dict:
    """DeepSeek V4.1 Flash and Qwen3.8-27B: full runs (Pi 1.5.2) rescored as lite from their
    saved reports by scripts/suite_fidelity.py's `view` (older scorer and gold v4 / v3, so not
    strictly comparable). Cost: agent sessions of the lite days plus Track A oracle sessions."""
    import sys

    sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
    from suite_fidelity import view

    from wcb.suites import SUITES

    out = {}
    for label, d in (("DeepSeek V4.1 Flash", "2026-11-11-deepseek-v4.1-flash-1017-pi"),
                     ("Qwen3.8-27B", "2026-11-11-qwen3.8-27b-pi")):  # fmt: skip
        r = {"scores": {}, "cost": 0.0}
        for t in "ab":
            rep = json.loads((ROOT / "results" / d / f"scores-track-{t}.json").read_text())
            su = SUITES["lite"]
            score, cost = view(rep, su)
            worlds = {w["id"]: w for w in rep["worlds"]}
            last = {w: worlds[w]["days"][su.max_days - 1] for w in su.world_ids}
            cps = {(w, c["id"]) for w in last for c in worlds[w]["checkpoints"] if c["date"] <= last[w]}
            cost += sum(q["cost_usd"] or 0 for q in rep["efficiency"]["per_query_session"]
                        if q.get("store") == "oracle" and (q["world"], q["checkpoint"]) in cps)  # fmt: skip
            r["scores"][t], r["cost"] = score, r["cost"] + cost
        out[label] = r
    return out


EARLIER = earlier_runs()
JUDGE = json.loads((HERE.parent / "judge-cost.json").read_text())
COLOR = {"Opus 5.5": "#d97757", "Sonnet 5.5": "#c9a227", "Haiku 5.5": "#7fb37a", "GPT-6.1 Sol": "#5b8def",
         "DeepSeek V4.1 Flash": "#b48ead", "Qwen3.8-27B": "#88c0d0"}
INK, MUTED, GRID, BG = "#f4f1ea", "#9a968c", "#3a3833", "#1c1b19"
W, H = 1600, 900  # slide coordinate system


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def t(x, y, s, size=28, fill=INK, anchor="start", weight=400, extra=""):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}" {extra}>{esc(str(s))}</text>')  # fmt: skip


def xtitle(x0, x1, y, s):
    """Axis title under a horizontal axis."""
    return t((x0 + x1) / 2, y, s, 26, MUTED, "middle", 600)


def ytitle(x, y0, y1, s):
    """Axis title beside a vertical axis, rotated."""
    return (f'<text transform="translate({x:.1f},{(y0 + y1) / 2:.1f}) rotate(-90)" font-size="26" '
            f'fill="{MUTED}" text-anchor="middle" font-weight="600">{esc(s)}</text>')  # fmt: skip


def svg(body: str, w=1400, h=560) -> str:
    return f'<svg viewBox="0 0 {w} {h}" class="chart" role="img">{body}</svg>'


# ------------------------------------------------------------------ charts
def hbars(rows, vmax, fmt, w=1400, h=560, label_w=300, unit="", highlight=None, note=None,
          xlab="", ylab=""):
    """Horizontal bars: rows = [(label, value, color)], with a value axis under them."""
    n = len(rows)
    gap = 26
    bh = (h - 130 - gap * (n - 1)) / n
    span = w - label_w - 200
    out = []
    for i, (label, v, color) in enumerate(rows):
        y = 20 + i * (bh + gap)
        bw = span * v / vmax
        op = 1 if (highlight is None or label in highlight) else 0.35
        out.append(t(label_w - 24, y + bh / 2 + 12, label, 36, INK, "end", 500))
        out.append(f'<rect x="{label_w}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="8" fill="{color}" opacity="{op}"/>')
        out.append(t(label_w + bw + 18, y + bh / 2 + 14, fmt(v) + unit, 40, INK, "start", 600))
    base = 20 + n * (bh + gap) - gap + 10
    out.append(f'<line x1="{label_w}" x2="{label_w + span}" y1="{base:.1f}" y2="{base:.1f}" stroke="{GRID}" stroke-width="2"/>')
    for k in range(5):
        v = vmax * k / 4
        x = label_w + span * k / 4
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base:.1f}" y2="{base + 8:.1f}" stroke="{MUTED}"/>')
        out.append(t(x, base + 34, fmt(v), 22, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, base + 70, xlab))
    out.append(ytitle(28, 20, base, ylab))
    if note:
        out.append(t(label_w, h - 4, note, 22, MUTED))
    return svg("".join(out), w, h)


def grouped_scores():
    """Lite A and B per model, with 95% CI whiskers."""
    w, h = 1400, 600
    left, right, top, bottom = 120, 40, 30, 130
    lo, hi = 50, 100
    ys = lambda v: top + (h - top - bottom) * (hi - v) / (hi - lo)  # noqa: E731
    out = []
    for v in range(50, 101, 10):
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{ys(v):.1f}" y2="{ys(v):.1f}" stroke="{GRID}"/>')
        out.append(t(left - 14, ys(v) + 9, v, 24, MUTED, "end"))
    gw = (w - left - right) / len(ORDER)
    bw = 110
    for i, m in enumerate(ORDER):
        cx = left + gw * (i + 0.5)
        for j, tr in enumerate("ab"):
            s = DATA[m]["scores"][f"lite-{tr}"]
            x = cx + (j - 1) * (bw + 14) + 7
            y = ys(s["rescored"])
            op = 1 if tr == "a" else 0.55
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw}" height="{ys(lo) - y:.1f}" rx="6" fill="{COLOR[m]}" opacity="{op}"/>')
            c0, c1 = ys(s["ci95"][0]), ys(s["ci95"][1])
            mx = x + bw / 2
            out.append(f'<line x1="{mx}" x2="{mx}" y1="{c1:.1f}" y2="{c0:.1f}" stroke="{INK}" stroke-width="3" opacity=".7"/>')
            for cy in (c0, c1):
                out.append(f'<line x1="{mx - 12}" x2="{mx + 12}" y1="{cy:.1f}" y2="{cy:.1f}" stroke="{INK}" stroke-width="3" opacity=".7"/>')
            out.append(t(mx, ys(lo) - 18, f'{s["rescored"]:.1f}', 34, BG, "middle", 700))
            out.append(t(mx, ys(lo) + 34, "A" if tr == "a" else "B", 24, MUTED, "middle"))
        out.append(t(cx, h - bottom + 80, m, 34, INK, "middle", 600))
    out.append(xtitle(left, w - right, h - 6, "Model (A = fixed store contract, B = own memory design)"))
    out.append(ytitle(36, top, h - bottom, "WCB-lite score (0–100)"))
    return svg("".join(out), w, h)


def frontier(track: str):
    """Score vs cost of one lite run (A + B, log x) for all six runs, with the Pareto frontier."""
    import math

    pts = [(m, DATA[m]["usage"]["lite"]["cost_billed_usd"], DATA[m]["scores"][f"lite-{track}"]["rescored"], True)
           for m in ORDER]  # fmt: skip
    pts += [(m, r["cost"], r["scores"][track], False) for m, r in EARLIER.items()]
    w, h = 1400, 580
    left, right, top, bottom = 130, 60, 70, 90
    xlo, xhi = math.log10(2), math.log10(100)
    ys_ = [p[2] for p in pts]
    ylo, yhi = 5 * math.floor(min(ys_) / 5 - 0.6), 5 * math.ceil(max(ys_) / 5 + 0.4)
    xs = lambda c: left + (w - left - right) * (math.log10(c) - xlo) / (xhi - xlo)  # noqa: E731
    ys = lambda v: top + (h - top - bottom) * (yhi - v) / (yhi - ylo)  # noqa: E731
    out = []
    for c in (2, 5, 10, 20, 50, 100):
        out.append(f'<line x1="{xs(c):.1f}" x2="{xs(c):.1f}" y1="{top}" y2="{h - bottom}" stroke="{GRID}"/>')
        out.append(t(xs(c), h - bottom + 40, f"${c}", 26, MUTED, "middle"))
    for v in range(ylo, yhi + 1, 5):
        out.append(f'<line x1="{left}" x2="{w - right}" y1="{ys(v):.1f}" y2="{ys(v):.1f}" stroke="{GRID}"/>')
        out.append(t(left - 14, ys(v) + 9, v, 24, MUTED, "end"))
    out.append(xtitle(left, w - right, h - 8, "Cost of one lite run, Tracks A + B, USD (log scale)"))
    out.append(ytitle(40, top, h - bottom, f"Track {track.upper()} score (0–100)"))
    best, front = -1.0, []
    for p in sorted(pts, key=lambda p: p[1]):
        if p[2] > best:
            best = p[2]
            front.append(p)
    path = " ".join(f"{'M' if i == 0 else 'L'}{xs(p[1]):.1f},{ys(p[2]):.1f}" for i, p in enumerate(front))
    out.append(f'<path d="{path}" fill="none" stroke="{INK}" stroke-width="4" stroke-dasharray="10 8" opacity=".6"/>')
    # (dx, dy of the name line, anchor): above, below or to one side, so no labels collide
    place = {"a": {"Opus 5.5": (32, -6, "start"), "Sonnet 5.5": (0, -58, "middle"),
                   "GPT-6.1 Sol": (0, 54, "middle"), "DeepSeek V4.1 Flash": (30, 44, "start")},
             "b": {"Opus 5.5": (32, -6, "start"), "Sonnet 5.5": (30, 44, "start"),
                   "GPT-6.1 Sol": (0, -58, "middle"), "DeepSeek V4.1 Flash": (-30, 44, "end")}}[track]
    place["Haiku 5.5"] = (0, 54, "middle")
    for m, c, sc, ours in pts:
        x, y = xs(c), ys(sc)
        if ours:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="20" fill="{COLOR[m]}"/>')
        else:
            out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="none" stroke="{COLOR[m]}" stroke-width="6"/>')
        dx, dy, anchor = place.get(m, (32, -6, "start"))
        out.append(t(x + dx, y + dy, m, 32, INK, anchor, 600))
        out.append(t(x + dx, y + dy + 32, f"${c:.2f} · {sc:.1f}", 24, MUTED, anchor))
    return svg("".join(out), w, h)


def stacked_ingest():
    """Synthesis (oracle store) vs Track A: the gap is what the model's own store costs."""
    w, h = 1400, 560
    label_w, span = 300, 980
    lo, hi = 60, 100
    xs = lambda v: label_w + span * (v - lo) / (hi - lo)  # noqa: E731
    out = []
    for v in range(60, 101, 5):
        out.append(f'<line x1="{xs(v):.1f}" x2="{xs(v):.1f}" y1="10" y2="{h - 100}" stroke="{GRID}"/>')
        out.append(t(xs(v), h - 64, v, 24, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, h - 20, "Track A score (0–100): own memory (dot) vs perfect memory (ring)"))
    out.append(ytitle(28, 10, h - 100, "Model"))
    for i, m in enumerate(ORDER):
        y = 40 + i * 110
        a = DATA[m]["scores"]["lite-a"]["rescored"]
        s = DATA[m]["scores"]["lite-a"]["synthesis"]
        out.append(t(label_w - 24, y + 40, m, 36, INK, "end", 500))
        out.append(f'<line x1="{xs(a):.1f}" x2="{xs(s):.1f}" y1="{y + 30}" y2="{y + 30}" stroke="{COLOR[m]}" stroke-width="10" opacity=".45"/>')
        out.append(f'<circle cx="{xs(s):.1f}" cy="{y + 30}" r="16" fill="none" stroke="{INK}" stroke-width="4"/>')
        out.append(f'<circle cx="{xs(a):.1f}" cy="{y + 30}" r="16" fill="{COLOR[m]}"/>')
        out.append(t((xs(a) + xs(s)) / 2, y + 2, f"−{s - a:.1f}", 28, INK, "middle", 600))
    return svg("".join(out), w, h)


def bucket_heat():
    """Mean score by question type, Track A, per model."""
    buckets = ["point", "temporal", "status", "list", "brief", "priority", "change"]
    names = {"point": "Point facts", "temporal": "Dates", "status": "Status", "list": "Lists",
             "brief": "Person briefs", "priority": "Focus tomorrow", "change": "What changed"}  # fmt: skip
    w, h = 1400, 600
    left, top = 360, 70
    cw, ch = (w - left) / len(ORDER), (h - top) / len(buckets)
    out = []
    for i, m in enumerate(ORDER):
        out.append(t(left + cw * (i + 0.5), 44, m, 30, INK, "middle", 600))
    for j, b in enumerate(buckets):
        y = top + j * ch
        out.append(t(left - 24, y + ch / 2 + 11, names[b], 32, INK, "end", 500))
        for i, m in enumerate(ORDER):
            v = DATA[m]["buckets"]["a"][b]["agent"] / 100
            # dark red (0) -> amber -> green (1)
            hue = 120 * v
            out.append(f'<rect x="{left + i * cw + 6:.1f}" y="{y + 5:.1f}" width="{cw - 12:.1f}" height="{ch - 10:.1f}" rx="8" fill="hsl({hue:.0f},45%,{22 + 10 * v:.0f}%)"/>')
            out.append(t(left + cw * (i + 0.5), y + ch / 2 + 13, f"{v:.2f}", 36, INK, "middle", 700))
    out.append(ytitle(28, top, h, "Question type"))
    out.append(t(left - 24, 44, "Model →", 26, MUTED, "end", 600))
    return svg("".join(out), w, h)


def turns_dots():
    """Turns per ingestion day, every session, per model (jittered strip)."""
    import random

    rng = random.Random(7)
    w, h = 1400, 560
    label_w, span = 300, 1000
    vmax = 40
    xs = lambda v: label_w + span * min(v, vmax) / vmax  # noqa: E731
    out = []
    for v in range(0, vmax + 1, 10):
        out.append(f'<line x1="{xs(v):.1f}" x2="{xs(v):.1f}" y1="10" y2="{h - 100}" stroke="{GRID}"/>')
        out.append(t(xs(v), h - 64, f"{v}+" if v == vmax else v, 24, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, h - 20, "Model turns per ingestion session (one dot per inbox day; bar = median)"))
    out.append(ytitle(28, 10, h - 100, "Model"))
    for i, m in enumerate(["Sonnet 5.5", "Opus 5.5", "GPT-6.1 Sol", "Haiku 5.5"]):
        y = 70 + i * 110
        out.append(t(label_w - 24, y + 12, m, 34, INK, "end", 500))
        for s in DATA[m]["ingest_sessions"]:
            out.append(f'<circle cx="{xs(s["turns"]) + rng.uniform(-4, 4):.1f}" cy="{y + rng.uniform(-24, 24):.1f}" r="7" fill="{COLOR[m]}" opacity=".75"/>')
        med = DATA[m]["usage"]["lite"]["ingest_turns_median"]
        out.append(f'<line x1="{xs(med):.1f}" x2="{xs(med):.1f}" y1="{y - 38}" y2="{y + 38}" stroke="{INK}" stroke-width="5"/>')
        out.append(t(xs(med) + 12, y - 40, f"median {med:g}", 24, INK))
    return svg("".join(out), w, h)


def tokens_split():
    """Total tokens per lite run, split into cache reads, cache writes, uncached input and output."""
    parts = [("cache_read_input_tokens", "cache read", 1.0), ("cache_creation_input_tokens", "cache write", 0.7),
             ("input_tokens", "uncached input", 0.5), ("output_tokens", "output", 0.3)]  # fmt: skip
    w, h = 1400, 560
    label_w, span = 300, 760
    tot = {m: sum(DATA[m]["usage"]["lite"]["tokens"][k] + DATA[m]["usage"]["lite"]["oracle_tokens"][k]
                  for k, _, _ in parts) for m in ORDER}  # fmt: skip
    vmax = max(tot.values())
    out = []
    for i, m in enumerate(["Haiku 5.5", "Opus 5.5", "GPT-6.1 Sol", "Sonnet 5.5"]):
        y = 30 + i * 110
        out.append(t(label_w - 24, y + 42, m, 34, INK, "end", 500))
        x = label_w
        for k, _, op in parts:
            v = DATA[m]["usage"]["lite"]["tokens"][k] + DATA[m]["usage"]["lite"]["oracle_tokens"][k]
            bw = span * v / vmax
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="62" fill="{COLOR[m]}" opacity="{op}"/>')
            x += bw
        out_m = (DATA[m]["usage"]["lite"]["tokens"]["output_tokens"] + DATA[m]["usage"]["lite"]["oracle_tokens"]["output_tokens"]) / 1e6
        out.append(t(x + 18, y + 30, f"{tot[m] / 1e6:.0f}M", 36, INK, "start", 700))
        out.append(t(x + 18, y + 62, f"{out_m:.1f}M output", 24, MUTED))
    base = 30 + 4 * 110 - 30
    out.append(f'<line x1="{label_w}" x2="{label_w + span}" y1="{base}" y2="{base}" stroke="{GRID}" stroke-width="2"/>')
    for k in range(5):
        v = vmax * k / 4
        x = label_w + span * k / 4
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base}" y2="{base + 8}" stroke="{MUTED}"/>')
        out.append(t(x, base + 32, f"{v / 1e6:.0f}M", 22, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, base + 66, "Tokens per lite run, millions (shade: cache read, cache write, uncached input, output)"))
    out.append(ytitle(28, 30, base, "Model"))
    return svg("".join(out), w, h)


def lite_cost_bars():
    rows = [(m, DATA[m]["usage"]["lite"]["cost_billed_usd"], COLOR[m]) for m in ORDER]
    return hbars(rows, 60, lambda v: f"${v:.0f}" if v == int(v) else f"${v:.2f}",
                 xlab="USD per lite run, Tracks A + B (LiteLLM prices; Sol at flex tier; includes oracle sessions)",
                 ylab="Model")


def track_gap():
    """Track A vs Track B per model (dumbbell)."""
    w, h = 1400, 560
    label_w, span = 300, 980
    lo, hi = 55, 95
    xs = lambda v: label_w + span * (v - lo) / (hi - lo)  # noqa: E731
    out = []
    for v in range(55, 96, 5):
        out.append(f'<line x1="{xs(v):.1f}" x2="{xs(v):.1f}" y1="10" y2="{h - 100}" stroke="{GRID}"/>')
        out.append(t(xs(v), h - 64, v, 24, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, h - 20, "WCB-lite score (0–100): Track A (filled) vs Track B (ring)"))
    out.append(ytitle(28, 10, h - 100, "Model"))
    for i, m in enumerate(ORDER):
        y = 50 + i * 110
        a, b = DATA[m]["scores"]["lite-a"]["rescored"], DATA[m]["scores"]["lite-b"]["rescored"]
        out.append(t(label_w - 24, y + 12, m, 34, INK, "end", 500))
        out.append(f'<line x1="{xs(b):.1f}" x2="{xs(a):.1f}" y1="{y}" y2="{y}" stroke="{COLOR[m]}" stroke-width="8" opacity=".5"/>')
        out.append(f'<circle cx="{xs(b):.1f}" cy="{y}" r="16" fill="none" stroke="{COLOR[m]}" stroke-width="5"/>')
        out.append(f'<circle cx="{xs(a):.1f}" cy="{y}" r="16" fill="{COLOR[m]}"/>')
        out.append(t(xs(b) - 26, y + 10, "B", 26, MUTED, "end"))
        out.append(t(xs(a) + 26, y + 10, "A", 26, MUTED, "start"))
        out.append(t((xs(a) + xs(b)) / 2, y - 24, f"−{a - b:.1f}", 28, INK, "middle", 600))
    return svg("".join(out), w, h)


def rescore_bars(track="a"):
    """One track's lite score per model under each grader: original, judge fixes (11-21),
    gold v6 with the heuristic judge, and gold v6 with the cross-family panel."""
    steps = [("original", "Original grader", MUTED), ("fixed", "Date/hedge fixes", "#88c0d0"),
             ("heuristic", "Gold v6, heuristic", "#c9a227"), ("rescored", "Gold v6 + panel", INK)]  # fmt: skip
    w, h = 1400, 600
    label_w, span = 300, 980
    lo, hi = 55, 100
    xs = lambda v: label_w + span * (v - lo) / (hi - lo)  # noqa: E731
    out = []
    for v in range(55, 101, 5):
        out.append(f'<line x1="{xs(v):.1f}" x2="{xs(v):.1f}" y1="10" y2="{h - 150}" stroke="{GRID}"/>')
        out.append(t(xs(v), h - 114, v, 24, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, h - 76, f"Track {track.upper()} WCB-lite score (0–100), same answers"))
    out.append(ytitle(28, 10, h - 150, "Model"))
    for i, m in enumerate(ORDER):
        y = 50 + i * 100
        sc = DATA[m]["scores"][f"lite-{track}"]
        out.append(t(label_w - 24, y + 12, m, 34, INK, "end", 500))
        lo_v, hi_v = min(sc[k] for k, _, _ in steps), max(sc[k] for k, _, _ in steps)
        out.append(f'<line x1="{xs(lo_v):.1f}" x2="{xs(hi_v):.1f}" y1="{y}" y2="{y}" stroke="{COLOR[m]}" stroke-width="8" opacity=".45"/>')
        for k, _, color in steps:
            r = 16 if k == "rescored" else 11
            out.append(f'<circle cx="{xs(sc[k]):.1f}" cy="{y}" r="{r}" fill="{color}"/>')
        out.append(t(xs(sc["rescored"]) + 28, y + 12, f'{sc["rescored"]:.1f}', 34, INK, "start", 700))
        out.append(t(xs(sc["original"]) - 22, y + 10, f'{sc["original"]:.1f}', 24, MUTED, "end"))
    for k, (_, name, color) in enumerate(steps):
        x = label_w + k * 250
        out.append(f'<circle cx="{x + 12}" cy="{h - 22}" r="11" fill="{color}"/>')
        out.append(t(x + 32, h - 13, name, 24, INK))
    return svg("".join(out), w, h)


def judge_cost_bars():
    """Agent cost vs grading cost per lite run (A + B)."""
    w, h = 1400, 560
    label_w, span, vmax = 300, 820, 70
    out = []
    for i, m in enumerate(ORDER):
        y = 30 + i * 100
        agent = DATA[m]["usage"]["lite"]["cost_billed_usd"]
        judge = sum(JUDGE["runs"][m][t]["cost_billed_usd"] for t in "ab")
        out.append(t(label_w - 24, y + 44, m, 34, INK, "end", 500))
        aw, jw = span * agent / vmax, span * judge / vmax
        out.append(f'<rect x="{label_w}" y="{y + 10}" width="{aw:.1f}" height="54" fill="{COLOR[m]}"/>')
        out.append(f'<rect x="{label_w + aw:.1f}" y="{y + 10}" width="{jw:.1f}" height="54" fill="{INK}" opacity=".85"/>')
        out.append(t(label_w + aw + jw + 16, y + 48, f"${agent:.2f} + ${judge:.2f}", 32, INK, "start", 600))
    base = 30 + 4 * 100 + 4
    out.append(f'<line x1="{label_w}" x2="{label_w + span}" y1="{base}" y2="{base}" stroke="{GRID}" stroke-width="2"/>')
    for v in range(0, vmax + 1, 10):
        x = label_w + span * v / vmax
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base}" y2="{base + 8}" stroke="{MUTED}"/>')
        out.append(t(x, base + 32, f"${v}", 22, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, base + 66, "USD per lite run, Tracks A + B: model under test (color) + judge panel (white)"))
    out.append(ytitle(28, 30, base, "Model under test"))
    return svg("".join(out), w, h)


def suite_diagram():
    """Full vs lite vs micro: worlds × days as blocks."""
    days = {"pilot": 6, "gen-s1-w1": 6, "gen-s2-w1": 5, "gen-s3-w1": 6, "gen-s4-w2": 12, "gen-s5-small": 6,
            "gen-s6-w1": 6, "gen-s7-w2": 12, "gen-s8-w4": 24, "gen-s9-large": 6, "gen-s10-w2-small": 11}  # fmt: skip
    micro = {"pilot", "gen-s1-w1", "gen-s4-w2", "gen-s5-small", "gen-s9-large"}
    w, h = 1400, 600
    left, cell, rowh = 260, 40, 46
    out = []
    for i, (wid, n) in enumerate(days.items()):
        y = 20 + i * rowh
        out.append(t(left - 20, y + 30, wid, 24, MUTED, "end", 400, 'font-family="ui-monospace,monospace"'))
        for d in range(n):
            x = left + d * (cell + 4)
            if d < 2 and wid in micro:
                fill, op = "#d97757", 1
            elif d < 2:
                fill, op = "#c9a227", 1
            else:
                fill, op = GRID, 1
            out.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{rowh - 8}" rx="5" fill="{fill}" opacity="{op}"/>')
    ly = 20 + len(days) * rowh + 26
    for k, (label, fill) in enumerate([("micro: 5 worlds × 2 days", "#d97757"), ("lite: 11 worlds × 2 days", "#c9a227"),
                                       ("full: 100 days", GRID)]):  # fmt: skip
        x = left + k * 380
        out.append(f'<rect x="{x}" y="{ly - 22}" width="28" height="28" rx="5" fill="{fill}"/>')
        out.append(t(x + 40, ly, label, 28, INK))
    return svg("".join(out), w, h)


def harness_diagram():
    """How one world is played: ingest each day, query at checkpoints."""
    w, h = 1400, 460
    out = []
    boxes = [(60, "Inbox, day 1", "email · chat · notes"), (400, "Agent ingests", "updates its memory"),
             (740, "Inbox, day 2", "…"), (1080, "Checkpoint", "questions, graded")]  # fmt: skip
    for x, a, b in boxes:
        out.append(f'<rect x="{x}" y="120" width="280" height="160" rx="16" fill="#2a2925" stroke="{GRID}" stroke-width="3"/>')
        out.append(t(x + 140, 190, a, 34, INK, "middle", 600))
        out.append(t(x + 140, 236, b, 26, MUTED, "middle"))
    for x in (340, 680, 1020):
        out.append(f'<line x1="{x + 6}" x2="{x + 52}" y1="200" y2="200" stroke="{INK}" stroke-width="4" marker-end="url(#a2)"/>')
    out.append(t(700, 360, "Track A: memory follows a fixed contract · Track B: the agent designs its own", 28, MUTED, "middle"))
    out.append(t(700, 404, "Oracle run (Track A): same questions answered from a perfect memory", 28, MUTED, "middle"))
    defs = (f'<defs><marker id="a2" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" '
            f'orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{INK}"/></marker></defs>')  # fmt: skip
    return svg(defs + "".join(out), w, h)


#: Opus 5.5 lost points by cause, lite, rescored (results/2026-11-21-claude-opus-5.5-pi-lite/ERROR-AUDIT.md)
OPUS_LOSS = [("Model error", 2.3, 2.8, "#d97757"), ("Grader too strict", 5.6, 16.0, "#c9a227"),
             ("Arguable gold", 3.0, 5.6, "#88c0d0"), ("Citation penalty", 1.5, 3.2, "#9a968c")]


def opus_loss():
    """Opus's lost points per track, stacked by cause."""
    w, h = 1400, 560
    label_w, span, vmax = 220, 1000, 28
    out = []
    for i, (tr, idx, score) in enumerate([("Track A", 1, 87.5), ("Track B", 2, 72.4)]):
        y = 60 + i * 190
        out.append(t(label_w - 24, y + 50, tr, 36, INK, "end", 600))
        x = label_w
        for _, a, b, color in OPUS_LOSS:
            v = (a, b)[idx - 1]
            bw = span * v / vmax
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="80" fill="{color}"/>')
            if bw > 60:
                out.append(t(x + bw / 2, y + 52, f"{v:.1f}", 30, BG, "middle", 700))
            x += bw
        out.append(t(x + 18, y + 52, f"−{100 - score:.1f}", 36, INK, "start", 700))
    base = 60 + 190 + 100
    out.append(f'<line x1="{label_w}" x2="{label_w + span}" y1="{base}" y2="{base}" stroke="{GRID}" stroke-width="2"/>')
    for v in range(0, vmax + 1, 4):
        x = label_w + span * v / vmax
        out.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base}" y2="{base + 8}" stroke="{MUTED}"/>')
        out.append(t(x, base + 32, v, 22, MUTED, "middle"))
    out.append(xtitle(label_w, label_w + span, base + 64, "Points lost (100 − score), heuristic grader, by cause"))
    for k, (name, _, _, color) in enumerate(OPUS_LOSS):
        x = label_w + k * 290
        out.append(f'<rect x="{x}" y="{h - 40}" width="28" height="28" rx="5" fill="{color}"/>')
        out.append(t(x + 40, h - 17, name, 28, INK))
    return svg("".join(out), w, h)


def earlier_table():
    rows = [(m, DATA[m]["scores"]["lite-a"]["rescored"], DATA[m]["scores"]["lite-b"]["rescored"],
             DATA[m]["usage"]["lite"]["cost_billed_usd"], "") for m in ORDER]  # fmt: skip
    rows += [(m, r["scores"]["a"], r["scores"]["b"], r["cost"], "*") for m, r in EARLIER.items()]
    rows.sort(key=lambda r: -r[1])
    head = '<tr><th></th><th>Track A</th><th>Track B</th><th>Lite cost</th></tr>'
    body = "".join(f'<tr><td style="color:{COLOR[m]}">{esc(m)}{mark}</td><td>{a:.1f}</td><td>{b:.1f}</td><td>${c:.2f}</td></tr>'
                   for m, a, b, c, mark in rows)  # fmt: skip
    return (f'<table class="tbl">{head}{body}</table>'
            '<div class="foot">* Full runs from 11 Nov rescored as lite; older scorer (gold v4 DeepSeek, v3 Qwen), '
            'no judge fixes. Full-run scores: DeepSeek 84.6 / 67.5, Qwen 72.3 / 55.0.</div>')


# ------------------------------------------------------------------ slides
def quote(who, text, score, color, verdict=None):
    v = f'<div class="verdict">{esc(verdict)}</div>' if verdict else ""
    return (f'<div class="quote" style="border-color:{color}"><div class="who" style="color:{color}">{esc(who)}'
            f'<span class="score">{esc(score)}</span></div><div class="qt">{text}</div>{v}</div>')  # fmt: skip


def slide(title, body="", sub="", cls=""):
    s = f'<div class="sub">{esc(sub)}</div>' if sub else ""
    return f'<section class="slide {cls}"><h1>{esc(title)}</h1>{s}<div class="body">{body}</div></section>'


def big_number(n, label):
    return f'<div class="bignum"><div class="n">{esc(n)}</div><div class="l">{esc(label)}</div></div>'


def main() -> None:
    D = DATA
    full_ds = 118.8  # DeepSeek V4.1 Flash full run, agent + oracle, both tracks (docs/lite.md)
    opus, son, hai, sol = (D[m] for m in ORDER)
    slides = []

    slides.append(
        '<section class="slide title"><div class="kicker">white-collar-bench</div>'
        '<h1 class="hero">Six models, one memory benchmark,<br>lite runs from $3.53</h1>'
        '<div class="sub">WCB-lite · Claude Opus, Sonnet, Haiku 5.5 · GPT-6.1 Sol · DeepSeek V4.1 Flash · Qwen3.8-27B · Pi harness · gold v6, judge panel · Nov 2026</div></section>'
    )
    slides.append(slide("The task: be someone's working memory", harness_diagram(),
                        "Synthetic knowledge-worker worlds: projects, people, commitments, decisions"))
    slides.append(slide("A full run is expensive", '<div class="row">'
                        + big_number(f"${full_ds:.0f}", "DeepSeek V4.1 Flash, cheap open model")
                        + big_number(f"~${opus['usage']['lite']['cost_billed_usd'] / 0.21:.0f}", "Opus 5.5, estimated from its lite cost")
                        + big_number("76%", "of the cost is ingesting inbox days") + "</div>",
                        "100 episode days across 11 worlds; days, not questions, drive cost"))
    slides.append(slide("Lite: every world, first two days", suite_diagram(),
                        "Breadth beats depth: most variance is between worlds"))
    slides.append(slide("Lite keeps the ranking at ~20% of the cost", '<div class="row">'
                        + big_number("21%", "lite cost vs full")
                        + big_number("10%", "micro cost vs full")
                        + big_number("≤ 2.8", "points error in model gaps") + "</div>",
                        "Checked by rescoring two full runs (DeepSeek, Qwen) as each suite"))

    slides.append(slide("Opus leads; the rest are close", grouped_scores(),
                        "WCB-lite, gold v6 + judge panel · bars: Track A solid, Track B faded · whiskers: 95% CI over worlds"))
    slides.append(slide("One lite run costs $3.53 to $57", lite_cost_bars(), "Cost of the model under test, before grading"))
    slides.append(slide("Track A: Haiku is 89 for $3.53", frontier("a"),
                        "Dashed: best score per budget · hollow: earlier runs, older grader (not rescored)"))
    slides.append(slide("Track B: Opus pulls away when memory is up to the model", frontier("b"),
                        "Dashed: best score per budget · hollow: earlier runs, older grader (not rescored)"))
    slides.append(slide("Six models on lite", earlier_table(),
                        "DeepSeek and Qwen: earlier full runs, rescored as lite with the older grader; raw answers unavailable"))
    slides.append(slide("Answering is easy. Remembering is hard.", stacked_ingest(),
                        "Ring: score from a perfect memory · dot: score from the model's own memory"))
    slides.append(slide("Without a memory contract, every model drops", track_gap(),
                        "Opus loses 4.5 points · the others 7–10 · Track A: fixed store layout · Track B: own design"))
    slides.append(slide("Where the points go", bucket_heat(), "Mean score by question type, Track A, judge panel"))

    slides.append(slide("Sonnet plans; Haiku explores", turns_dots(),
                        "Turns per ingestion day, every session (Tracks A and B)"))
    slides.append(slide("Haiku reads 6× more tokens than Sonnet", tokens_split(),
                        "Tokens per lite run, all sessions"))
    slides.append(slide("Four personalities", '<div class="cards">'
                        + "".join(f'<div class="card" style="border-color:{COLOR[m]}"><div class="cn" style="color:{COLOR[m]}">{esc(m)}</div><div class="cd">{esc(d)}</div></div>'
                                  for m, d in [("Opus 5.5", "Thorough. Best memory, long explanations."),
                                               ("Sonnet 5.5", "Efficient. 6 turns a day, short answers."),
                                               ("Haiku 5.5", "Busy. 20 turns a day, still the cheapest."),
                                               ("GPT-6.1 Sol", "Literal. Follows the contract to the letter.")])
                        + "</div>"))

    # failure examples
    slides.append(slide("Failure 1: “Should I even do this?”",
                        '<div class="ask">Andres in chat: “can you send me the Fennel rollout checklist by Wednesday?”</div>'
                        + quote("GPT-6.1 Sol", "Respond to Andres's request for the Fennel rollout checklist; <b>agree whether you can deliver it tomorrow</b>, then send it if accepted.",
                                "0 → 0.93", COLOR["GPT-6.1 Sol"], "Right task, hedged. Nobody had answered Andres, so the item is now optional.")
                        + '<div class="foot">Gold: “Send Andres the Fennel rollout checklist”. Sol scored 0 on 5 of 11 “focus tomorrow” questions this way.</div>',
                        "What should I focus on tomorrow?"))
    slides.append(slide("Who is right? The rules disagree",
                        '<div class="two"><div class="col"><div class="lab">The memory contract</div><div class="big">An ask is <b>not accepted</b> until the worker agrees</div></div>'
                        '<div class="col"><div class="lab">The world generator</div><div class="big">A direct request is <b>accepted</b></div></div></div>'
                        + '<div class="foot">Share of new loops a model marks unaccepted: Sol 24% · Haiku 21% · Opus 15% · Sonnet 14%. Fix: unanswered asks are optional, neither required nor wrong.</div>',
                        "A benchmark bug, found by a model that read the rules literally"))
    slides.append(slide("Failure 2: telling the history got zero",
                        '<div class="ask">The target date moved twice: 15 Dec → 22 Dec → 31 Dec</div>'
                        + quote("GPT-6.1 Sol", "Petra moved the target from December 15 to December 22 on November 8, <b>then to December 31</b> on November 9.", "0 → 0.96", COLOR["GPT-6.1 Sol"])
                        + quote("Opus 5.5", "The target date moved to Fri 31 Dec 2027 (<b>it was 15 Dec, then 22 Dec</b>).", "0 → 0.72", COLOR["Opus 5.5"],
                                "The grader read “22 Dec” as the current date. Fixed."),
                        "What is the status of Marten?"))
    slides.append(slide("Grading for substance moved every model up", rescore_bars("a"),
                        "Same answers, four graders · Sol gains most: it explains and hedges"))
    slides.append(slide("Track B gains the most: 11–17 points", rescore_bars("b"),
                        "Own-memory answers are longer and freer, so word matching missed them"))
    slides.append(slide("The judge: heuristic first, then a two-family panel",
                        '<div class="two"><div class="col"><div class="lab">Heuristic says yes</div><div class="big">Accepted. <b>No model call</b>.</div></div>'
                        '<div class="col"><div class="lab">Heuristic says no</div><div class="big">Claude Sonnet <b>and</b> GPT-6.1 Sol must both say yes</div></div></div>'
                        '<div class="foot">Neither family can grade its own models alone · one sample each · every decision cached</div>',
                        "Substantially correct gets credit, whatever the wording"))
    slides.append(slide(f"Grading costs ${JUDGE['total_billed_usd']:.0f} for all four runs", judge_cost_bars(),
                        f"{JUDGE['total']['claude-sonnet-5.5']['calls'] + JUDGE['total']['gpt-6.1-sol']['calls']:,} panel calls · "
                        f"{JUDGE['total_tokens'] / 1e6:.1f}M tokens · plus ${JUDGE['wasted_sis_calls']['cost_usd']:.0f} lost to a bug, now fixed"))
    slides.append(slide("Failure 3: right answer, buried in explanation",
                        quote("Opus 5.5", "Finish and send the Fulmar privacy impact assessment to Goran Liu. <b>It was due 14 Sep and no completion has been seen, so it is probably overdue</b>", "0", COLOR["Opus 5.5"])
                        + quote("Sonnet 5.5", "Send Fulmar privacy impact assessment to Goran Liu (was due 14 Sep, no completion evidenced)", "0.93", COLOR["Sonnet 5.5"])
                        + '<div class="foot">Gold: “Complete the Fulmar privacy impact assessment”. Same item, ranked first by both. The panel now gives Opus 0.92.</div>',
                        "Track B · What should I focus on tomorrow?"))
    slides.append(slide("Failure 4: “What changed?” stumped the grader",
                        '<div class="ask">Gold: decided to build Corrie in-house · I handed Corrie over to Iselbury</div>'
                        + quote("Sonnet 5.5", "Anastasia confirmed Corrie will be built in-house rather than bought · Handover of Corrie to Iselbury reported done", "0", COLOR["Sonnet 5.5"])
                        + quote("Opus 5.5", "Anastasia confirmed Corrie will be built in-house rather than bought (decision made) · Hiba … reported it done", "0 → 0.80", COLOR["Opus 5.5"],
                                "Word matching gave every model 0 or near it. The panel accepts both events."),
                        "What changed on Project Corrie since Saturday?"))
    slides.append(slide("Failure 5: a completed task listed as owed",
                        '<div class="ask">What does Sol owe me?   Gold: “Collect two references for Mateus”</div>'
                        + quote("Opus 5.5", "Schedule the panel interview for Mateus (done; panel held 1 March)", "0", COLOR["Opus 5.5"],
                                "A real error: a finished loop instead of the open one. Pilot world, the hardest for everyone."),
                        "Track A · pilot world"))

    slides.append(slide("Why Opus wasn't at 100: mostly the grader", opus_loss(),
                        "Audit of the old grader's losses · with gold v6 and the panel Opus scores 91.9 / 87.4"))
    slides.append(slide("What all four share", '<div class="cards">'
                        + "".join(f'<div class="card"><div class="cn">{esc(a)}</div><div class="cd">{esc(b)}</div></div>'
                                  for a, b in [("Never invent", "Unanswerable questions: 1.00 for every model"),
                                               ("Dates are solid", "Temporal questions: 0.95–1.00"),
                                               ("“What changed?” is hardest", "0.62–0.74 on Track A, lowest of all types"),
                                               ("The pilot world is hardest", "Dense hand-offs and corrections")])
                        + "</div>"))
    slides.append(slide("Takeaways", '<ol class="take">'
                        '<li><b>Lite works.</b> Same ranking as full runs at ~20% of the cost.</li>'
                        '<li><b>Opus leads, Haiku is the bargain.</b> 89 on Track A for $3.53.</li>'
                        '<li><b>Own memory is the real test.</b> Track B separates models.</li>'
                        f'<li><b>Grade substance, not words.</b> A two-family panel costs ~${JUDGE["total_billed_usd"] / 4:.0f} a run.</li></ol>'))

    page = TEMPLATE.replace("{{SLIDES}}", "\n".join(slides))
    (HERE / "index.html").write_text(page)
    print(f"wrote {HERE / 'index.html'} ({len(slides)} slides, {len(page) // 1024} KB)")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WCB-lite: four models</title>
<style>
:root { --bg: #1c1b19; --ink: #f4f1ea; --muted: #9a968c; }
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: #000; color: var(--ink);
  font-family: -apple-system, "Segoe UI", Inter, Helvetica, Arial, sans-serif; overflow: hidden; }
#stage { position: absolute; left: 50%; top: 50%; width: 1600px; height: 900px; transform-origin: 0 0; }
.slide { position: absolute; inset: 0; background: var(--bg); padding: 70px 100px; display: none; flex-direction: column; }
.slide.on { display: flex; }
h1 { font-size: 64px; line-height: 1.1; margin: 0 0 12px; font-weight: 700; letter-spacing: -0.01em; }
.sub { font-size: 30px; color: var(--muted); margin-bottom: 28px; }
.body { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.chart { width: 100%; height: auto; max-height: 620px; font-family: inherit; }
.title { justify-content: center; }
.title .hero { font-size: 88px; line-height: 1.05; }
.kicker { font-size: 30px; color: #d97757; font-weight: 600; margin-bottom: 24px; letter-spacing: .04em; text-transform: uppercase; }
.row { display: flex; gap: 60px; justify-content: space-between; }
.bignum { flex: 1; } .bignum .n { font-size: 140px; font-weight: 800; line-height: 1; color: #c9a227; }
.bignum .l { font-size: 34px; color: var(--muted); margin-top: 18px; }
.quote { border-left: 10px solid; padding: 16px 32px; margin: 14px 0; background: #24231f; border-radius: 0 14px 14px 0; }
.quote .who { font-size: 28px; font-weight: 700; display: flex; justify-content: space-between; }
.quote .score { color: var(--ink); font-size: 34px; }
.quote .qt { font-size: 38px; line-height: 1.3; margin-top: 6px; }
.quote .qt b { color: #ffd37a; font-weight: 600; }
.verdict { font-size: 28px; color: var(--muted); margin-top: 10px; }
.ask { font-size: 34px; color: var(--muted); margin-bottom: 10px; }
.foot { font-size: 28px; color: var(--muted); margin-top: 24px; }
.two { display: flex; gap: 60px; } .two .col { flex: 1; background: #24231f; padding: 40px; border-radius: 18px; }
.two .lab { font-size: 28px; color: var(--muted); margin-bottom: 16px; }
.two .big { font-size: 52px; line-height: 1.2; } .two b { color: #ffd37a; }
.cards { display: grid; grid-template-columns: 1fr 1fr; gap: 36px; }
.card { border-left: 10px solid #555; background: #24231f; padding: 30px 36px; border-radius: 0 16px 16px 0; }
.card .cn { font-size: 44px; font-weight: 700; } .card .cd { font-size: 34px; color: var(--muted); margin-top: 10px; }
.take { font-size: 50px; line-height: 1.35; padding-left: 60px; margin: 0; } .take li { margin: 14px 0; }
.take b { color: #ffd37a; }
.tbl { font-size: 40px; border-collapse: collapse; width: 100%; }
.tbl th { color: var(--muted); font-weight: 500; font-size: 28px; text-align: right; padding: 8px 24px; }
.tbl td { padding: 10px 24px; text-align: right; border-top: 2px solid #3a3833; font-variant-numeric: tabular-nums; }
.tbl td:first-child, .tbl th:first-child { text-align: left; font-weight: 700; }
#n { position: fixed; right: 18px; bottom: 12px; color: #666; font: 14px sans-serif; }
@media print { html, body { overflow: visible; background: var(--bg); }
  #stage { position: static; transform: none !important; } .slide { position: relative; display: flex !important;
  page-break-after: always; width: 1600px; height: 900px; } #n { display: none; } }
@page { size: 1600px 900px; margin: 0; }
</style></head><body>
<div id="stage">
{{SLIDES}}
</div><div id="n"></div>
<script>
{
  const slides = [...document.querySelectorAll('.slide')];
  const stage = document.getElementById('stage');
  const n = document.getElementById('n');
  let i = Math.max(0, Math.min(slides.length - 1, (parseInt(location.hash.slice(1)) || 1) - 1));
  const fit = () => { const s = Math.min(innerWidth / 1600, innerHeight / 900);
    stage.style.transform = `scale(${s}) translate(-50%, -50%)`; stage.style.left = '50%'; stage.style.top = '50%';
    stage.style.transformOrigin = '0 0'; stage.style.transform = `translate(-${800 * s}px, -${450 * s}px) scale(${s})`; };
  const show = k => { i = Math.max(0, Math.min(slides.length - 1, k)); slides.forEach((s, j) => s.classList.toggle('on', j === i));
    n.textContent = `${i + 1} / ${slides.length}`; history.replaceState(null, '', '#' + (i + 1)); };
  addEventListener('resize', fit); fit(); show(i);
  addEventListener('keydown', e => {
    if (['ArrowRight', 'PageDown', ' ', 'Enter'].includes(e.key)) show(i + 1);
    else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(e.key)) show(i - 1);
    else if (e.key === 'Home') show(0); else if (e.key === 'End') show(slides.length - 1);
    else if (e.key === 'f') (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
  });
  addEventListener('click', e => show(e.clientX > innerWidth / 3 ? i + 1 : i - 1));
}
</script></body></html>
"""

if __name__ == "__main__":
    main()
