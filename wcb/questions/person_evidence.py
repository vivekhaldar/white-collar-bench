"""Locate delivered evidence tying a named person to a particular attribute value."""

from __future__ import annotations

import re

from wcb.agents.docs_text import DocumentError, extract_text
from wcb.util.text import normalize
from wcb.world.model import World


def _lines(world: World, aid: str) -> list[str]:
    cache = world._cache.setdefault("person_evidence_lines", {})
    if aid not in cache:
        path = world.dir / world.artifacts[aid].path
        try:
            text = extract_text(path)
        except (OSError, DocumentError):
            text = ""
        # A roster of attendees can attach a different affiliation to each person.
        lines = []
        for line in text.splitlines():
            if line.lower().lstrip("*").startswith("attendees:"):
                lines.extend(line.split(","))
            else:
                lines.append(line)
        cache[aid] = [normalize(line) for line in lines if line.strip()]
    return cache[aid]


def _pattern(forms: list[str]) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(re.escape(normalize(s)) for s in forms) + r")(?!\w)")


def attribute_sources(world: World, state: dict, person: str, attribute: str) -> list[str]:
    ent = state["entities"][person]
    value = ent["attrs"].get(attribute)
    if not isinstance(value, str) or not value:
        return []
    cache = world._cache.setdefault("person_attribute_sources", {})
    key = (person, attribute, value)
    if key not in cache:
        alias = world.alias_table()
        names = [ent["name"], *(n for n in ent.get("surface_forms", [])
                                if alias.get(normalize(n)) == {person} and len(n) > 2)]
        org = world.entity_events().get(value) if attribute == "org" else None
        forms = [org["name"], *org.get("surface_forms", [])] if org else [value]
        subject, target = _pattern(names), _pattern(forms)
        normalized_names = {normalize(n) for n in names}
        found = []
        for aid in world.artifacts:
            lines = _lines(world, aid)
            for index, line in enumerate(lines):
                if not subject.search(line):
                    continue
                # In a signature, the next line can give the signer's title and organization.
                signature = line.strip(" -*,") in normalized_names
                passage = " ".join(lines[index:index + 2]) if signature else line
                if target.search(passage):
                    found.append(aid)
                    break
        cache[key] = set(found)
    return [aid for aid in state.get("delivered", []) if aid in cache[key]]


def ground_person_gold(gold: dict, world: World, state: dict, params: dict, template: str) -> dict:
    """Gold may recognize a seeded value while allowing agents to report it as unknown."""
    person = params["person"]
    if template == "person_attr":
        attr = params["attribute"]
        if attr in {"role", "org", "relationship"} and not attribute_sources(world, state, person, attr):
            return {**gold, "uncertain": True}
        return gold

    roles = [r for r in gold["rubric"] if r.get("aspect") == "role"]
    if not roles:
        return gold
    role = roles[0]
    sources = attribute_sources(world, state, person, "role")
    rubric = list(gold["rubric"])
    if not sources:
        rubric.remove(role)
    else:
        ent = state["entities"][person]
        text = role["text"]
        if ent["attrs"].get("org") and not attribute_sources(world, state, person, "org"):
            text = f"{ent['name']} is {ent['attrs']['role']}"
        rubric[rubric.index(role)] = {**role, "text": text, "support": [a for a in role["support"] if a in sources] or sources}
    return {**gold, "rubric": rubric}
