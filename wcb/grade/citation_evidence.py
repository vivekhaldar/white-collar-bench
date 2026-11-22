"""Check additional delivered sources against the item a citation accompanies."""

from __future__ import annotations

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
        if not title or re.search(r"\b(completed|attended|took place|was held|cancelled)\b", text, re.I):
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
    items = gold.get("items", [])
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
    source = normalize(source)
    keywords = [s for s in item.get("keywords", []) if isinstance(s, str)]
    if not keywords or not contains_phrase(source, keywords[0]):
        return False
    support = item.get("support", [])
    if artifact.parent in support or any(world.artifacts[a].parent == aid for a in support if a in world.artifacts):
        return True
    # Distinct deliverable plus project or another identifying phrase.
    return (len(match_tokens(keywords[0])) >= 2 and
            any(contains_phrase(source, s) for s in keywords[1:] if s != keywords[0]))

