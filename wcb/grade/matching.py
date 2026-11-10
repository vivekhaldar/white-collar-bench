"""One-to-one matching of predicted items to gold items (docs/scoring.md, "Matching").

List questions (`kind='loop'`), priority questions (`kind='loop'`) and change questions
(`kind='change'`) all compare a predicted list of free-text items with a gold list. Matching
has two steps:

1. **Candidates** (`candidate_pairs`). A predicted item and a gold item are candidates when
   any of these holds:

   * they share an artifact: a `cites` entry of the prediction is in the gold item's `support`;
   * the prediction's `counterparty` resolves (through the world's alias table) to the gold
     item's counterparty;
   * their text similarity (`similarity`, a Dice coefficient over content tokens) is at least
     `CANDIDATE_SIMILARITY` (0.2).

2. **Confirmation and assignment** (`match_items`). The judge answers `same_item` for every
   candidate pair (each distinct pair is asked once per call). Confirmed pairs are assigned
   one-to-one: first greedily, in order of decreasing text similarity, then improved with
   augmenting paths so that the number of matched pairs is the maximum possible. Ties keep
   input order, so the result is deterministic.
"""

from __future__ import annotations

import json
from typing import Any

from wcb.grade.judge import gold_text, match_tokens, pred_text

#: Minimum Dice similarity for a pair to become a candidate on text alone.
CANDIDATE_SIMILARITY = 0.2


def similarity(pred: dict, gold: dict) -> float:
    """Dice coefficient between the prediction's full text and the gold description + keywords."""
    p = match_tokens(pred_text(pred, full=True))
    g = match_tokens(gold_text(gold))
    for kw in gold.get("keywords") or []:
        if isinstance(kw, str):
            g |= match_tokens(kw)
    if not p or not g:
        return 0.0
    return 2 * len(p & g) / (len(p) + len(g))


def _cites(pred: dict) -> set[str]:
    return {c for c in pred.get("cites") or [] if isinstance(c, str)}


def _counterparty_hit(pred: dict, gold: dict, ctx: Any) -> bool:
    cp, gcp = pred.get("counterparty"), gold.get("counterparty")
    if ctx is None or not isinstance(cp, str) or not cp.strip() or not gcp:
        return False
    return gcp in ctx.resolve_entities(cp)


def candidate_pairs(pred: list[dict], gold: list[dict], ctx: Any) -> list[tuple[int, int]]:
    """All (pred_idx, gold_idx) pairs worth asking the judge about, in index order.

    `ctx` is a `wcb.grade.answers.ScoreContext` (or None, which disables the counterparty
    route).
    """
    out = []
    for i, p in enumerate(pred):
        cites = _cites(p)
        for j, g in enumerate(gold):
            if (
                cites & set(g.get("support") or [])
                or _counterparty_hit(p, g, ctx)
                or similarity(p, g) >= CANDIDATE_SIMILARITY
            ):
                out.append((i, j))
    return out


def _display_gold(gold: dict, ctx: Any) -> dict:
    """Gold item as shown to the judge: adds `counterparty_name` when the entity is known."""
    cp = gold.get("counterparty")
    entities = getattr(ctx, "entities", None) or {}
    if isinstance(cp, str) and cp in entities and "counterparty_name" not in gold:
        return {**gold, "counterparty_name": entities[cp].get("name", cp)}
    return gold


def match_items(
    pred: list[dict], gold: list[dict], judge: Any, *, kind: str, ctx: Any
) -> list[tuple[int, int]]:
    """Match predicted to gold items one-to-one; returns sorted (pred_idx, gold_idx) pairs.

    Only judge-confirmed candidate pairs can match. Among them the assignment has the maximum
    number of pairs, preferring pairs with higher text similarity (see the module docstring).
    """
    shown = [_display_gold(g, ctx) for g in gold]
    asked: dict[tuple[str, int], bool] = {}
    edges: list[tuple[float, int, int]] = []
    for i, j in candidate_pairs(pred, gold, ctx):
        key = (json.dumps(pred[i], sort_keys=True, default=str), j)
        if key not in asked:
            asked[key] = bool(judge.same_item(pred[i], shown[j], kind=kind))
        if asked[key]:
            edges.append((similarity(pred[i], gold[j]), i, j))
    return assign(edges)


def assign(edges: list[tuple[float, int, int]]) -> list[tuple[int, int]]:
    """Maximum one-to-one assignment over (weight, pred_idx, gold_idx) edges.

    Greedy by decreasing weight first, then augmenting paths (Kuhn's algorithm) for every
    unmatched prediction, which makes the number of pairs maximal while keeping most greedy
    choices.
    """
    order = sorted(edges, key=lambda e: (-e[0], e[1], e[2]))
    adj: dict[int, list[int]] = {}
    for _, i, j in order:
        adj.setdefault(i, []).append(j)
    pred_of: dict[int, int] = {}  # gold_idx -> pred_idx
    gold_of: dict[int, int] = {}  # pred_idx -> gold_idx
    for _, i, j in order:
        if i not in gold_of and j not in pred_of:
            gold_of[i], pred_of[j] = j, i

    def augment(i: int, seen: set[int]) -> bool:
        for j in adj.get(i, []):
            if j in seen:
                continue
            seen.add(j)
            if j not in pred_of or augment(pred_of[j], seen):
                pred_of[j], gold_of[i] = i, j
                return True
        return False

    for i in sorted(adj):
        if i not in gold_of:
            augment(i, set())
    return sorted(gold_of.items())
