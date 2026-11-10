"""Document renderer: versioned `.docx`, `.xlsx`, `.pdf` and `.md` attachments.

Documents arrive as email attachments (their manifest entry has `parent` set to the email).
Scorecards, cost models, registers and trackers are spreadsheets; memos, plans and specs are
Word files; slides and briefs are PDFs; the rest Markdown. Content is descriptive (purpose,
summary, a table, open questions) and never introduces new commitments.

`plan_attachments` adds attachment communications to a simulation before rendering: some
emails that deliver a document (a loop such as "Send Ana the Heron risk register" closing as
done) carry the document itself. The version-mismatch challenge already supplies its own
attachment, whose version differs from the one the email names.
"""

from __future__ import annotations

import random
from pathlib import Path

from wcb.render.context import RenderContext, Rendered, day_words
from wcb.render.office import extract_text, write_docx, write_pdf, write_xlsx
from wcb.render.phrases import subject_of
from wcb.world.comms import Act, Communication

DELIVERABLE_VERBS = ("Send", "Share", "Turn", "Write", "Draft", "Assemble", "Pull", "Update", "Circulate",
                     "Summarize", "Revise")
XLSX_WORDS = ("scorecard", "cost model", "workbook", "budget", "timeline", "raci", "matrix", "dictionary",
              "register", "list", "census", "extract", "export", "schedule", "metrics", "rubric", "comparison")
PDF_WORDS = ("slide", "diagram", "charter", "brief", "blueprint")
P_ATTACH = 0.45


def doc_format(noun: str, rng: random.Random) -> str:
    low = noun.lower()
    if any(w in low for w in XLSX_WORDS):
        return "xlsx"
    if any(w in low for w in PDF_WORDS):
        return "pdf"
    return rng.choice(["docx", "docx", "md", "pdf"])


def plan_attachments(plan: dict, sim, seed: int) -> None:
    """Attach documents to some delivery emails, then renumber document artifacts in delivery order."""
    rng = random.Random(f"wcb-attach:{seed}")
    events = {e["id"]: e for e in sim.events}
    creates: dict[str, dict] = {}
    debtor: dict[str, str] = {}
    debtor_at: dict[str, str] = {}
    for e in sim.events:
        if e["type"] == "commitment.create":
            creates[e["commitment"]] = e
            debtor[e["commitment"]] = e["debtor"]
        elif e["type"] == "commitment.resolve":
            debtor_at[e["id"]] = debtor.get(e["commitment"], "")
        elif e["type"] == "commitment.update" and "debtor" in (e.get("changes") or {}):
            debtor[e["commitment"]] = e["changes"]["debtor"]
    firsts = {p["first"] for p in plan["people"] if p.get("last")}
    has_child = {c.parent for c in sim.comms if c.parent}
    out: list[Communication] = []
    for c in sim.comms:
        out.append(c)
        if c.kind != "email" or c.noise or c.draft or c.id in has_child or not c.sender:
            continue
        for a in c.acts:
            e = events[a.event]
            if e["type"] != "commitment.resolve" or e["status"] != "done":
                continue
            cr = creates.get(e["commitment"])
            if cr is None or debtor_at.get(e["id"]) != c.sender:
                continue
            if cr["what"].split()[0] not in DELIVERABLE_VERBS or "status note" in cr["what"].lower():
                continue
            if rng.random() > P_ATTACH:
                break
            noun = _title_noun(cr["what"], firsts)
            fmt = doc_format(noun, rng)
            version = rng.choice(["v1", "v2", "v2", "v3", "final", "draft"])
            doc = Communication(
                id=f"{c.id}-att", t=c.t, channel="document", kind="document", sender=c.sender,
                project=c.project, subject=f"{noun} {version}" if version.startswith("v") else f"{noun} ({version})",
                acts=[Act(e["id"], "direct")],
                received_at=c.received_at, parent=c.id,
                extra={"format": fmt, "version": version, "attachment_of": e["commitment"]},
            )
            doc.artifacts = ["dc-0000"]
            out.append(doc)
            break
    n = 0
    for c in out:
        if c.kind == "document":
            n += 1
            c.artifacts = [f"dc-{n:04d}"]
    sim.comms[:] = out


def _title_noun(what: str, firsts: set[str]) -> str:
    s = subject_of(firsts, what)
    for art in ("the ", "a ", "an "):
        if s.startswith(art):
            s = s[len(art):]
    return s[:1].upper() + s[1:]


# ---------------------------------------------------------------- rendering
def render(ctx: RenderContext, comm: Communication) -> list[Rendered]:
    aid = comm.artifacts[0]
    rng = ctx.rng(aid)
    fmt = str(comm.extra.get("format") or "md")
    version = str(comm.extra.get("version") or "v1")
    title = comm.subject or "Document"
    author = ctx.full(comm.sender)
    date = comm.t[:10]
    proj = ctx.project(comm.project)
    noun = title.rsplit(" (", 1)[0] if title.endswith(")") else title
    if noun.endswith(" " + version):
        noun = noun[: -len(version) - 1]
    if fmt == "xlsx":
        sheets = _sheets(ctx, comm, noun, version, rng)

        def writer(path: Path) -> None:
            write_xlsx(path, sheets, author=author, date=date, title=title)

        text = "\n".join(str(c) for rows in sheets.values() for row in rows for c in row)
        return [Rendered(aid, ".xlsx", title, writer=writer, text=text)]
    md = _markdown(ctx, comm, noun, version, proj, rng)
    if fmt == "docx":
        return [Rendered(aid, ".docx", title, writer=lambda p: write_docx(p, md, title=title, author=author, date=date), text=md)]
    if fmt == "pdf":
        return [Rendered(aid, ".pdf", title, writer=lambda p: write_pdf(p, md, title=title), text=md)]
    return [Rendered(aid, ".md", title, content=md, text=md)]


def _purpose(noun: str, pname: str) -> str:
    """What a document is for, from its kind (never the worker's own summary of the project)."""
    low = noun.lower()
    kinds = (
        (("slide", "deck"), f"These slides give a short overview of {pname}."),
        (("plan", "outline", "run sheet", "schedule", "timeline", "roadmap", "checklist"),
         f"This {noun} sets out the steps, owners and dates for {pname}."),
        (("register", "list", "log", "tracker", "inventory", "matrix", "census"),
         f"This {noun} records the items tracked for {pname} and where each one stands."),
        (("memo", "brief", "note", "paper", "summary", "one-pager", "statement", "charter", "profile"),
         f"This {noun} summarizes the current position on {pname} for discussion."),
        (("spec", "contract", "diagram", "blueprint", "architecture", "export", "extract", "dictionary", "model"),
         f"This {noun} describes the detail behind {pname}."),
        (("review", "assessment", "audit", "comments", "case", "findings"),
         f"This {noun} records what was reviewed for {pname} and what still needs to change."),
        (("survey", "form", "questions", "script", "guide", "template", "bank", "pack"),
         f"This {noun} is the working draft used with participants in {pname}."),
    )
    for words, text in kinds:
        if any(w in low for w in words):
            return text
    return f"Working document for {pname}."


DETAIL_NOTES = ("agreed at the last review", "draft, comments welcome", "unchanged from the previous version",
                "needs input from the unit", "see appendix", "covers the pilot group only", "reworded after feedback",
                "two options shown, no preference yet", "carried over from the earlier draft", "to be confirmed",
                "aligned with the shared glossary", "out of scope for this version")


def _markdown(ctx: RenderContext, comm: Communication, noun: str, version: str, proj: dict | None,
              rng: random.Random) -> str:
    pname = proj["name"] if proj else ctx.central["name"]
    lines = [f"# {noun}", "",
             f"**Version:** {version}  |  **Project:** {pname}  |  **Prepared by:** {ctx.full(comm.sender)}  |  "
             f"**Date:** {day_words(comm.t[:10], 3)} {comm.t[:4]}", "",
             "## Purpose", "",
             _purpose(noun, pname), "",
             "## Summary", ""]
    points = rng.sample([
        "Scope is unchanged from the previous version.",
        "Assumptions are listed in the appendix and should be checked before sign-off.",
        "Figures are indicative and rounded.",
        "Feedback from the last review has been incorporated where possible.",
        "Two sections are still being drafted and are marked as such.",
        "Terminology follows the shared glossary.",
        "Dependencies on other teams are noted but not yet confirmed.",
        "Comments are tracked in the margin; resolved ones have been removed.",
        "This version is shorter than the last; detail moved to the appendix.",
    ], 3)
    lines += [f"- {p}" for p in points] + ["", "## Details", "", "| Area | Notes |", "|---|---|"]
    areas = rng.sample(["Scope", "Users", "Data", "Security", "Support", "Training", "Timeline", "Costs",
                        "Accessibility", "Integration", "Governance", "Communications"], 4)
    notes = rng.sample(DETAIL_NOTES, len(areas))
    lines += [f"| {a} | {n} |" for a, n in zip(areas, notes, strict=True)]
    lines += ["", "## Open questions", ""]
    lines += [f"- {q}" for q in rng.sample([
        "Is the current scope still right?", "Which unit hosts the shared components?",
        "What is the fallback if a dependency slips?", "Who signs off the final version?",
        "Are the usage assumptions realistic?", "Does this need to go to the council?",
        "Who maintains this once the project ends?"], 2)]
    return "\n".join(lines) + "\n"


def _sheets(ctx: RenderContext, comm: Communication, noun: str, version: str,
            rng: random.Random) -> dict[str, list[list[object]]]:
    proj = ctx.project(comm.project)
    pname = proj["name"] if proj else ctx.central["name"]
    arch = str(((proj or {}).get("attrs") or {}).get("_archetype") or "")
    head = [[noun], [f"Version {version}", pname, f"Prepared by {ctx.full(comm.sender)}"], []]
    low = noun.lower()
    if any(w in low for w in ("scorecard", "rubric", "comparison", "workbook", "matrix")):
        if arch == "hiring_pipeline":
            cols = ["Interviewer A", "Interviewer B"]
            crit = rng.sample(["Technical depth", "Communication", "Problem framing", "Collaboration",
                               "Domain knowledge", "Delivery track record"], 5)
            sheet = "Interview scores"
        else:
            vendors = [ctx.orgs[v]["short"] for v in (proj or {}).get("vendors", []) if v in ctx.orgs] \
                if arch in ("vendor_pair_evaluation", "supplier_negotiation", "stalled_discovery") else []
            cols = vendors or ["Option A", "Option B"]
            crit = rng.sample(["Fit to requirements", "Integration effort", "Security posture", "Accessibility",
                               "Total cost", "Support model", "Usability"], 5)
            sheet = "Scorecard"
        rows: list[list[object]] = [["Criterion", "Weight", *cols]]
        for cname in crit:
            rows.append([cname, rng.choice([10, 15, 20, 25]), *[rng.randint(2, 5) for _ in cols]])
        r0, r1 = len(head) + 2, len(head) + 1 + len(crit)
        total = ["Weighted total", ""]
        for j in range(len(cols)):
            col = chr(ord("C") + j)
            val = sum(int(r[1]) * int(r[2 + j]) for r in rows[1:])
            total.append({"f": f"SUMPRODUCT($B${r0}:$B${r1},{col}{r0}:{col}{r1})", "v": val})
        rows.append(total)
        return {sheet: head + rows, "Notes": [["Scores 1 (poor) to 5 (strong)."], ["Weights sum to the column total."]]}
    if "cost" in low or "budget" in low or "pricing" in low:
        items = rng.sample(["Licences", "Hosting", "Support hours", "Training", "Integration work", "Contingency",
                            "Project management"], 5)
        rows = [["Line item", "Qty", "Unit cost", "Total"]]
        start = len(head) + 2
        for k, it in enumerate(items):
            q, u = rng.randint(1, 40), rng.choice([250, 400, 1200, 1800, 5000])
            r = start + k
            rows.append([it, q, u, {"f": f"B{r}*C{r}", "v": q * u}])
        end = start + len(items) - 1
        rows.append(["Total", "", "", {"f": f"SUM(D{start}:D{end})", "v": sum(int(x[1]) * int(x[2]) for x in rows[1:])}])
        return {"Model": head + rows, "Assumptions": [["All figures exclude tax."], ["Rates as quoted, not negotiated."]]}
    cols = ["ID", "Item", "Status", "Notes"]
    rows = [cols]
    items = rng.sample(["Access", "Data feed", "Training", "Accessibility review", "Support rota", "Reporting",
                        "Retention", "Integration", "Comms", "Testing", "Sign-off", "Documentation"], rng.randint(5, 9))
    for k, item in enumerate(items):
        rows.append([f"{k + 1:02d}", item, rng.choice(["open", "in review", "done", "not started"]),
                     rng.choice(["", "see notes", "waiting on another team", "carried over", "new this version"])])
    return {"Tracker": head + rows}


def searchable_text(path: Path) -> str:
    """Text of a written document, as checks and graders see it."""
    return extract_text(path)
