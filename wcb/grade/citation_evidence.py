"""Check additional delivered sources against the item a citation accompanies."""

from __future__ import annotations

import json
import re
from email import policy
from email.parser import Parser

from wcb.agents.docs_text import DocumentError, extract_text
from wcb.grade.judge import match_tokens
from wcb.util.text import contains_phrase, normalize


def _source(world, aid):
    cache = world._cache.setdefault("citation_text", {})
    if aid not in cache:
        a = world.artifacts[aid]
        try:
            text = extract_text(world.dir / a.path)
        except (DocumentError, OSError):
            text = ""
        cache[aid] = text
    return cache[aid]


def _scheduled_or_draft(text, source, channel):
    if channel == "calendar":
        title = re.search(r"^SUMMARY:(.+)$", source, re.MULTILINE)
        cancelled = bool(re.search(r"^(?:METHOD:CANCEL|STATUS:CANCELLED)\s*$", source, re.I | re.M))
        claims_cancellation = bool(re.search(r"\bcancel(?:led|ed|lation)\b", text, re.I))
        if not title or cancelled != claims_cancellation or re.search(
            r"\b(completed|attended|took place|was held|already met)\b", text, re.I
        ):
            return False
        subject = title[1].replace("\\,", ",")
    elif channel == "email":
        message = Parser(policy=policy.default).parsestr(source)
        if str(message.get("X-Draft", "")).lower() != "true" or not re.search(
            r"\b(draft|unsent|not (?:yet )?sent|still to send|not delivered)\b", text, re.I
        ):
            return False
        subject = str(message.get("Subject", ""))
    else:
        return False
    words = match_tokens(subject)
    return len(words) >= 2 and words <= match_tokens(text)


def additional_sources(question, answer, details, ctx):
    """Return validated citations by prediction index, without adding candidate edges."""
    world = ctx.world
    if world is None or question["type"] not in {"list", "change", "priority"}:
        return {}
    gold = question["gold"]
    items = [*gold.get("items", []), *gold.get("suggested", [])]
    by_id = {g.get("loop") or g.get("event"): g for g in items}
    references = {}
    for match in details.get("matches", []):
        if match["gold"] in by_id:
            references.setdefault(match["pred"], []).append(by_id[match["gold"]])
    out = {}
    for index, pred in enumerate(answer.get("items", [])):
        text = " ".join(str(pred.get(k) or "") for k in ("text", "why"))
        for aid in pred.get("cites", []):
            if aid not in ctx.delivered or aid not in world.artifacts:
                continue
            artifact = world.artifacts[aid]
            source = _source(world, aid)
            if not source:
                continue
            if question["type"] == "priority":
                supported = _scheduled_or_draft(text, source, artifact.channel)
            else:
                supported = any(_confirms_item(item, aid, artifact, source, text, world)
                                for item in references.get(index, []))
            if supported:
                out.setdefault(index, set()).add(aid)
    return out


def _confirms_item(item, aid, artifact, source, claim, world):
    # An invitation or an unsent email alone cannot establish fulfillment.
    if artifact.channel == "calendar" or re.search(r"^X-Draft: true", source, re.I | re.M):
        return _scheduled_or_draft(claim, source, artifact.channel)
    # Attachments and same-thread replies must also identify this deliverable: some
    # messages and their attachments mention several distinct commitments.
    passages = [normalize(line) for line in source.splitlines() if line.strip()]
    keywords = [s for s in item.get("keywords", []) if isinstance(s, str)]
    if not keywords or not any(contains_phrase(p, keywords[0]) for p in passages):
        return False
    support = item.get("support", [])
    if artifact.parent in support or any(world.artifacts[a].parent == aid for a in support if a in world.artifacts):
        return True
    # Distinct deliverable plus project or another identifying phrase.
    return (len(match_tokens(keywords[0])) >= 2 and
            any(contains_phrase(p, keywords[0]) and contains_phrase(p, s)
                for p in passages for s in keywords[1:] if s != keywords[0]))



def evidence_excerpt(source, claim, limit=1700):
    """Keep the header and a contiguous passage around the strongest matching line."""
    if len(source) <= limit:
        return source
    words = match_tokens(claim)
    lines = source.splitlines(keepends=True)
    anchor = max(range(len(lines)), key=lambda i: len(words & match_tokens(lines[i])))
    offset = sum(map(len, lines[:anchor]))
    start = max(0, offset - 250)
    return source[:260] + "\n[…]\n" + source[start:start + limit - 270]


def cited_claim(answer, cite, item):
    """Retain only units carrying this citation, including any explicit attribution."""
    units = answer.get("items", []) if item is not None else [
        u for key in ("items", "claims") for u in answer.get(key, []) if cite in u.get("cites", [])
    ]
    if item is not None:
        units = [units[item]]
    if not units:
        units = [answer]
    parts = [{k: v for k, v in unit.items() if k in
              {"text", "why", "value", "summary", "note", "counterparty", "status", "date", "due", "owner"} and v}
             for unit in units]
    return json.dumps(parts, ensure_ascii=False, sort_keys=True)


def evidence_vote(question, answer, cite, item, ctx, judge, record_id, source_id=None):
    """Adjudicate delivered evidence using the question and the actual attached claim."""
    if ctx.world is None or not hasattr(judge, "citation"):
        return False
    source_id = source_id or cite
    ids = [source_id] if source_id in ctx.delivered else []
    if record_id and record_id != "people/me":
        ids = sorted((ctx.record_refs(record_id) or set()) & ctx.delivered)
    if not ids:
        return False
    claim = cited_claim(answer, cite, item)
    if not claim or claim == "[{}]":
        return False
    query = question["text"]
    words = match_tokens(query + " " + claim)
    passages = [evidence_excerpt(_source(ctx.world, aid), query + " " + claim) for aid in ids]
    passages = sorted(filter(None, passages), key=lambda p: -len(words & match_tokens(p)))
    if not passages:
        return False
    decision = judge.citation(query, claim, "\n\n".join(passages[:3]))
    if decision is not None or not hasattr(judge, "review_citation"):
        return bool(decision)
    # A split first read gets more source context, including project aliases used in the question.
    subjects = [ctx.entities[e] for key, e in (question.get("params") or {}).items()
                if key in {"person", "project"} and e in ctx.entities]
    context = [ent["name"] + " (" + ", ".join(ent.get("surface_forms") or []) + ")" for ent in subjects]
    who = ctx.entities.get(ctx.worker, {}).get("name", "")
    review = f"Question: {query}\nWorker: {who}\nQuestion subjects and aliases: " + ", ".join(context)
    sources = sorted((_source(ctx.world, aid) for aid in ids), key=lambda p: -len(words & match_tokens(p)))
    longer = "\n\n".join(evidence_excerpt(s, query + " " + claim, limit=6500) for s in sources[:3])
    return bool(judge.review_citation(review, claim, longer))
