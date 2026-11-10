"""Render a scored run (`report.json` data from `wcb.grade.score`) as text and Markdown.

`summary_text` gives the few lines `wcb score` prints; `render_markdown` gives `report.md`:
headline table, per-world results, breakdowns by question type, planted challenge and
checkpoint, store integrity per day, efficiency, failure samples and notes. Both are pure
functions of the report data, so a report can be re-rendered from `report.json` alone::

    from wcb.grade.report import render_markdown
    print(render_markdown(json.load(open("runs/x/scores/report.json"))))
"""

from __future__ import annotations

import json
from typing import Any

#: Column labels for the SIS sub-metrics, in report order.
METRIC_LABELS = {
    "entity_f1": "Entity F1",
    "loop_f1": "Loop F1",
    "field_accuracy": "Field acc.",
    "freshness": "Freshness",
    "groundedness": "Grounded",
    "validity": "Validity",
}

#: Longest JSON excerpt shown for a gold or predicted answer in failure samples.
MAX_JSON_CHARS = 1500


# ---------------------------------------------------------------- formatting helpers
def fmt(x: Any, digits: int = 1) -> str:
    """A number with `digits` decimals, or 'n/a' for None."""
    if x is None:
        return "n/a"
    if isinstance(x, (int, float)):
        return f"{x:.{digits}f}"
    return str(x)


def fmt_ci(ci: list[float] | None) -> str:
    return "" if not ci else f"[95% CI {fmt(ci[0])}, {fmt(ci[1])}]"


def table(headers: list[str], rows: list[list[Any]]) -> str:
    """A Markdown table; cells are converted with str() and pipes are escaped."""

    def cell(v: Any) -> str:
        return str(v).replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows]
    return "\n".join(lines)


def excerpt(obj: Any, limit: int = MAX_JSON_CHARS) -> str:
    """Indented JSON, cut to `limit` characters."""
    text = json.dumps(obj, indent=2, ensure_ascii=False, default=str)
    return text if len(text) <= limit else text[:limit] + "\n... (truncated)"


def adapter_label(adapter: Any) -> str:
    if not isinstance(adapter, dict):
        return "unknown adapter"
    name = adapter.get("name") or "unknown"
    version = f" {adapter['version']}" if adapter.get("version") else ""
    model = f" (model {adapter['model']})" if adapter.get("model") else ""
    return f"{name}{version}{model}"


# ---------------------------------------------------------------- summary
def summary_text(data: dict) -> str:
    """Headline numbers in a few lines (what `wcb score` prints)."""
    h = data.get("headline") or {}
    track = h.get("track", "?")
    counts = (
        f"{h.get('n_worlds', 0)} world(s), {h.get('n_episodes', 0)} episode(s), "
        f"{h.get('n_questions', 0)} question(s)"
    )
    lines = [f"WCB score (Track {track}): {fmt(h.get('wcb'))} {fmt_ci(h.get('wcb_ci95'))}".rstrip()]
    lines[0] += f"  over {counts}"
    if h.get("synthesis") is not None or track == "A":
        lines.append(
            f"Synthesis score (oracle store): {fmt(h.get('synthesis'))}   "
            f"Ingestion cost: {fmt(h.get('ingestion_cost'))}"
        )
    if track == "A":
        lines.append(
            f"Store integrity (SIS): {fmt(h.get('sis'))}   final day: {fmt(h.get('sis_final'))}"
        )
    judge = data.get("judge") or {}
    lines.append(f"Judge: {judge.get('name', judge.get('kind', '?'))}")
    notes = data.get("notes") or []
    if notes:
        lines.append(f"{len(notes)} note(s) in the report (missing answers, snapshots, ...)")
    out = (data.get("output") or {}).get("dir")
    if out:
        lines.append(f"Wrote {out}/report.json and {out}/report.md")
    return "\n".join(lines)


# ---------------------------------------------------------------- markdown
def render_markdown(data: dict) -> str:
    """The full `report.md`."""
    parts = [
        _header(data),
        _headline(data),
        _worlds(data),
        _by_type(data),
        _by_challenge(data),
        _by_checkpoint(data),
        _sis(data),
        _efficiency(data),
        _failures(data),
        _notes(data),
    ]
    return "\n\n".join(p for p in parts if p).rstrip() + "\n"


def _header(data: dict) -> str:
    run = data.get("run") or {}
    judge = data.get("judge") or {}
    return "\n".join(
        [
            "# white-collar-bench report",
            "",
            f"- Run: `{run.get('dir', '?')}` (Track {run.get('track', '?')}, status "
            f"{run.get('status') or 'unknown'})",
            f"- Adapter: {adapter_label(run.get('adapter'))}",
            f"- Judge: {judge.get('name', judge.get('kind', '?'))}",
            f"- Scored at {data.get('scored_at', '?')} with wcb {(data.get('scorer') or {}).get('wcb_version', '?')} "
            f"(scorer {(data.get('scorer') or {}).get('version', '?')}); run made with wcb "
            f"{run.get('wcb_version') or '?'}",
        ]
    )


def _headline(data: dict) -> str:
    h = data.get("headline") or {}
    rows = [
        ["WCB score", f"{fmt(h.get('wcb'))} {fmt_ci(h.get('wcb_ci95'))}".strip()],
        [
            "Synthesis score (oracle store)",
            f"{fmt(h.get('synthesis'))} {fmt_ci(h.get('synthesis_ci95'))}".strip(),
        ],
        ["Ingestion cost (Synthesis - WCB)", fmt(h.get("ingestion_cost"))],
    ]
    if h.get("track") == "A":
        rows += [
            ["SIS (mean over days)", fmt(h.get("sis"))],
            ["SIS (final day)", fmt(h.get("sis_final"))],
        ]
    rows.append(
        [
            "Worlds / episodes / questions",
            f"{h.get('n_worlds', 0)} / {h.get('n_episodes', 0)} / {h.get('n_questions', 0)}",
        ]
    )
    return (
        "## Headline\n\n"
        + table(["Metric", "Value"], rows)
        + (
            "\n\nScores are on a 0-100 scale. The interval is a 95% bootstrap over worlds; "
            "with one world it is degenerate."
        )
    )


def _worlds(data: dict) -> str:
    rows = []
    for w in data.get("worlds") or []:
        for e in w.get("repeats") or []:
            sis = e.get("sis") or {}
            rows.append(
                [
                    w["id"],
                    f"r{e['repeat']}",
                    fmt(e.get("score")),
                    fmt(e.get("synthesis")),
                    fmt(e.get("ingestion_cost")),
                    fmt(sis.get("mean")),
                    fmt(sis.get("final")),
                ]
            )
        if len(w.get("repeats") or []) > 1:
            rows.append(
                [
                    w["id"],
                    "**mean**",
                    fmt(w.get("score")),
                    fmt(w.get("synthesis")),
                    fmt(w.get("ingestion_cost")),
                    fmt(w.get("sis")),
                    fmt(w.get("sis_final")),
                ]
            )
    if not rows:
        return ""
    return "## By world and repeat\n\n" + table(
        ["World", "Repeat", "WCB", "Synthesis", "Ingestion cost", "SIS", "SIS final"], rows
    )


def _breakdown_table(title: str, key_label: str, d: dict) -> str:
    if not d:
        return ""
    rows = [
        [k, v.get("n", 0), fmt(v.get("wcb")), fmt(v.get("synthesis")), fmt(v.get("ingestion_cost"))]
        for k, v in d.items()
    ]
    return f"## {title}\n\n" + table([key_label, "n", "WCB", "Synthesis", "Ingestion cost"], rows)


def _by_type(data: dict) -> str:
    d = (data.get("breakdowns") or {}).get("by_type") or {}
    text = _breakdown_table("By question type", "Type", d)
    if text:
        text += (
            "\n\nMean question score per type over all checkpoints and repeats. Unanswerable "
            "questions form their own bucket."
        )
    return text


def _by_challenge(data: dict) -> str:
    d = (data.get("breakdowns") or {}).get("by_challenge") or {}
    return _breakdown_table("By planted challenge", "Challenge", d)


def _by_checkpoint(data: dict) -> str:
    rows = [
        [
            c["world"],
            c["checkpoint"],
            c["date"],
            f"{c.get('day_index') or '?'} of {c.get('n_days') or '?'}",
            c.get("n_questions", 0),
            fmt(c.get("wcb")),
            fmt(c.get("synthesis")),
            fmt(c.get("ingestion_cost")),
        ]
        for c in (data.get("breakdowns") or {}).get("by_checkpoint") or []
    ]
    if not rows:
        return ""
    return "## By checkpoint\n\n" + table(
        [
            "World",
            "Checkpoint",
            "Date",
            "Episode day",
            "Questions",
            "WCB",
            "Synthesis",
            "Ingestion cost",
        ],
        rows,
    )


def _sis(data: dict) -> str:
    days = data.get("sis_by_day") or []
    if not days:
        return ""
    rows = [
        [d["world"], d["date"], fmt(d.get("sis")), *[fmt(d.get(m), 3) for m in METRIC_LABELS]]
        for d in days
    ]
    text = "## Store integrity per day\n\n" + table(
        ["World", "Date", "SIS", *METRIC_LABELS.values()], rows
    )
    text += "\n\nSIS is 0-100; sub-metrics are 0-1. Values are means over repeats."
    errors = _sis_errors(data)
    return text + ("\n\n" + errors if errors else "")


def _sis_errors(data: dict) -> str:
    """Store errors on the final day of each episode: missing and spurious records, stale state."""
    lines = []
    for w in data.get("worlds") or []:
        for e in w.get("repeats") or []:
            sis = e.get("sis") or {}
            days = sis.get("days") or []
            if not days:
                continue
            last = days[-1]
            bits = []
            for label, key in (
                ("missing entities", "missing_entities"),
                ("spurious or duplicate entity records", "false_positive_records"),
                ("missing loops", "missing_loops"),
                ("unmatched loop records", "unmatched_loop_records"),
            ):
                if last.get(key):
                    bits.append(f"{label}: {', '.join(map(str, last[key]))}")
            stale = last.get("stale_records") or []
            if stale:
                bits.append(
                    "stale: " + ", ".join(f"{s['record']} ({'/'.join(s['fields'])})" for s in stale)
                )
            if bits:
                lines.append(f"- {w['id']} r{e['repeat']} ({last['date']}): " + "; ".join(bits))
    return ("Final-day store errors:\n\n" + "\n".join(lines)) if lines else ""


def _efficiency(data: dict) -> str:
    eff = data.get("efficiency") or {}
    summary = eff.get("summary") or {}
    labels = {
        "ingest": "Ingestion",
        "query": "Query (agent store)",
        "query_oracle": "Query (oracle store)",
    }
    rows = []
    for key, label in labels.items():
        s = summary.get(key) or {}
        if not s.get("sessions"):
            continue
        rows.append(
            [
                label,
                s["sessions"],
                fmt((s.get("wall_s") or {}).get("total")),
                fmt((s.get("wall_s") or {}).get("mean")),
                fmt((s.get("input_tokens") or {}).get("total"), 0),
                fmt((s.get("output_tokens") or {}).get("total"), 0),
                fmt((s.get("cost_usd") or {}).get("total"), 2),
                s.get("timeouts", 0),
                s.get("failures", 0),
                s.get("usage_reported", 0),
            ]
        )
    if not rows:
        return "## Efficiency\n\nNo session records found."
    text = "## Efficiency\n\n" + table(
        [
            "Sessions",
            "n",
            "Wall s (total)",
            "Wall s (mean)",
            "Input tokens",
            "Output tokens",
            "Cost USD",
            "Timeouts",
            "Failures",
            "Usage reported",
        ],
        rows,
    )
    per_ep = eff.get("per_episode") or {}
    text += (
        f"\n\nPer episode (agent sessions): {fmt(per_ep.get('wall_s'))} s, "
        f"{fmt(per_ep.get('input_tokens'), 0)} input tokens, {fmt(per_ep.get('output_tokens'), 0)} "
        f"output tokens, ${fmt(per_ep.get('cost_usd'), 2)}. Usage is self-reported unless the run was metered."
    )
    days = eff.get("per_ingest_day") or []
    if days:
        text += "\n\n### Per ingestion day\n\n" + table(
            ["World", "Date", "n", "Wall s", "Input tokens", "Output tokens", "Cost USD", "Status"],
            [
                [
                    d["world"],
                    d["date"],
                    d["n"],
                    fmt(d.get("wall_s")),
                    fmt(d.get("input_tokens"), 0),
                    fmt(d.get("output_tokens"), 0),
                    fmt(d.get("cost_usd"), 2),
                    ", ".join(d.get("statuses") or []),
                ]
                for d in days
            ],
        )
    queries = eff.get("per_query_session") or []
    if queries:
        text += "\n\n### Per query session\n\n" + table(
            [
                "World",
                "Checkpoint",
                "Store",
                "n",
                "Wall s",
                "Input tokens",
                "Output tokens",
                "Cost USD",
                "Status",
            ],
            [
                [
                    d["world"],
                    d["checkpoint"],
                    d["store"],
                    d["n"],
                    fmt(d.get("wall_s")),
                    fmt(d.get("input_tokens"), 0),
                    fmt(d.get("output_tokens"), 0),
                    fmt(d.get("cost_usd"), 2),
                    ", ".join(d.get("statuses") or []),
                ]
                for d in queries
            ],
        )
    return text


def _failures(data: dict) -> str:
    fails = data.get("failures") or []
    if not fails:
        return "## Failure samples\n\nNo question scored below 1."
    out = [
        "## Failure samples",
        "",
        f"The {len(fails)} lowest-scoring questions, with gold and predicted answers "
        "(dev worlds only; never publish these for test worlds).",
    ]
    for i, f in enumerate(fails, 1):
        tags = f" [{', '.join(f['challenges'])}]" if f.get("challenges") else ""
        out += [
            "",
            f"### {i}. {f['world']} r{f['repeat']} {f['checkpoint']} {f['id']} ({f['type']}, "
            f"{f['template']}): score {fmt(f['score'], 2)}{tags}",
            "",
            f"Question: {f.get('text')}",
            "",
            f"Base {fmt(f.get('base'), 2)}, citation precision {fmt(f.get('citation'), 2)}"
            + (
                ""
                if f.get("answerable", True)
                else "; the question is unanswerable (gold: abstain)"
            ),
            "",
            "Gold:",
            "",
            "```json",
            excerpt(f.get("gold")),
            "```",
            "",
            "Predicted:",
            "",
            "```json",
            excerpt(f.get("predicted")),
            "```",
        ]
    return "\n".join(out)


def _notes(data: dict) -> str:
    notes = data.get("notes") or []
    if not notes:
        return ""
    return "## Notes\n\n" + "\n".join(f"- {n}" for n in notes)
