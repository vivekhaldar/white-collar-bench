"""Identify contradictory blocker exchanges in already released generated transcripts."""

from __future__ import annotations

import re

from wcb.questions.templates import attr_support
from wcb.world.model import World


def conflicting_blocker_sources(world: World, state: dict, project: str) -> list[str]:
    if world.meta.get("generator", {}).get("version") != 1:
        return []
    ent = state["entities"].get(project, {})
    if not ent.get("attrs", {}).get("blocker"):
        return []
    support = attr_support(world, state, project, "blocker")
    if not support:
        return []
    last_report = max(world.artifacts[a].received_at for a in support)
    if "blocker_probe_topics" not in world._cache:
        projects = {eid: [ev["name"], *ev.get("surface_forms", [])]
                    for eid, ev in world.entity_events().items() if ev.get("kind") == "project"}
        denials = {}
        for a in world.artifacts.values():
            if a.channel != "transcript":
                continue
            path = world.dir / a.path
            if not path.is_file():
                continue
            transcript = path.read_text()
            if "Any blockers there?" not in transcript:
                continue
            cues = re.findall(r"^<v [^>]+>(.*)$", transcript, re.MULTILINE)
            topic = set()
            for index, cue in enumerate(cues[:-1]):
                if cue == "Any blockers there?" and cues[index + 1] in {"Not right now, no.", "Nothing major."}:
                    if len(topic) == 1:
                        denials.setdefault(next(iter(topic)), []).append(a)
                elif cue.strip() and len(cue.split()) >= 3:
                    mentioned = {eid for eid, forms in projects.items()
                                 if any(re.search(r"\b" + re.escape(f) + r"\b", cue, re.I) for f in forms)}
                    if mentioned:
                        topic = mentioned
        world._cache["blocker_probe_topics"] = denials
    delivered = set(state["delivered"])
    sources = world._cache["blocker_probe_topics"].get(project, [])
    return [a.id for a in sources if a.id in delivered and a.received_at > last_report]
