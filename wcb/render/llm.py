"""Optional LLM prose rewrite with a verifier (docs/generator.md, "Optional LLM rewrite").

Used only when a world is generated with `llm=True`. Template prose of non-noise emails is sent
to a model with strict constraints (keep every fact, keyword, name, date and secret; add no
commitments, decisions or dates). The rewrite is kept only if it passes:

1. deterministic checks: every keyword and secret still occurs verbatim; no date, weekday,
   month or capitalized name appears that the original did not contain;
2. a verifier call: a second prompt asks the model whether the rewrite adds, drops or changes
   any commitment, request, decision, date or person. Anything but `NO` rejects it.

Otherwise the template text is kept. Every model response is cached under
`.wcb-cache/gen-llm/` (or `$WCB_CACHE_DIR/gen-llm/`), keyed by the SHA-256 of the prompt, so
regenerating a world with the same model is reproducible and free.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from wcb.render.phrases import has_keywords

SYSTEM = (
    "You edit workplace messages so they read naturally. You never add, remove or change facts. "
    "Reply with the edited text only."
)
REWRITE_PROMPT = """Rewrite the message body below so it reads like a real {register} written by a busy colleague.

Hard rules:
- Keep every fact: who does what, for whom, and every date, exactly as given.
- Keep each of these phrases verbatim (case may change): {keywords}
- Keep these strings exactly, character for character: {secrets}
- Do not add any new task, request, promise, decision, date, number or person.
- Keep roughly the same length. Plain text only, no markdown, no greeting or sign-off.

Message body:
<<<
{text}
>>>"""
VERIFY_PROMPT = """Compare ORIGINAL and REWRITE. Does REWRITE add, drop or change any commitment, request,
decision, date, number or person compared with ORIGINAL? Answer with exactly one word: YES or NO.

ORIGINAL:
<<<
{original}
>>>

REWRITE:
<<<
{rewrite}
>>>"""

_DATEISH = re.compile(
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun|"
    r"january|february|march|april|may|june|july|august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec|tomorrow|yesterday|tonight|\d+(?:st|nd|rd|th)?)\b",
    re.I,
)
_CAPWORD = re.compile(r"\b[A-Z][a-z]{2,}\b")


class Rewriter:
    """Rewrites prose with a model, verifies it, and caches every response by prompt hash."""

    def __init__(self, spec: str | None = None, *, client: Any = None, cache_dir: str | Path | None = None):
        if client is None:
            from wcb.llm.client import make_client

            if not spec:
                raise ValueError("Rewriter needs a model spec or a client")
            client = make_client(spec)
        self.client = client
        root = Path(cache_dir or os.environ.get("WCB_CACHE_DIR") or ".wcb-cache")
        self.cache = root / "gen-llm"
        self.stats = {"calls": 0, "cached": 0, "accepted": 0, "rejected": 0}

    # ------------------------------------------------------------ model calls with a cache
    def _complete(self, prompt: str, max_tokens: int) -> str:
        key = hashlib.sha256((SYSTEM + "\n" + prompt).encode("utf-8")).hexdigest()
        path = self.cache / key[:2] / f"{key}.json"
        if path.is_file():
            self.stats["cached"] += 1
            return json.loads(path.read_text(encoding="utf-8"))["output"]
        self.stats["calls"] += 1
        out = self.client.complete(prompt, system=SYSTEM, temperature=0.0, max_tokens=max_tokens)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"model": getattr(self.client, "spec", ""), "output": out}), encoding="utf-8")
        return out

    # ------------------------------------------------------------ public
    def rewrite(self, text: str, *, keywords: list[str], secrets: list[str], register: str = "email") -> str:
        """The rewritten text if it passes verification, else `text` unchanged."""
        if not text.strip():
            return text
        prompt = REWRITE_PROMPT.format(register=register, keywords=json.dumps(keywords), secrets=json.dumps(secrets),
                                       text=text)
        out = self._complete(prompt, max_tokens=max(256, len(text) // 2)).strip()
        ok = self.check(text, out, keywords, secrets)
        if ok:
            verdict = self._complete(VERIFY_PROMPT.format(original=text, rewrite=out), max_tokens=5)
            ok = verdict.strip().upper().startswith("NO")
        self.stats["accepted" if ok else "rejected"] += 1
        return out if ok else text

    @staticmethod
    def check(original: str, rewrite: str, keywords: list[str], secrets: list[str]) -> bool:
        """Deterministic checks: keywords and secrets kept, no new dates or names."""
        if not rewrite or len(rewrite) > 3 * len(original) + 200:
            return False
        if not has_keywords(rewrite, keywords):
            return False
        if any(s not in rewrite for s in secrets):
            return False
        before = {m.lower() for m in _DATEISH.findall(original)}
        if any(m.lower() not in before for m in _DATEISH.findall(rewrite)):
            return False
        low = original.lower()
        return all(w.lower() in low for w in _CAPWORD.findall(rewrite) if w not in _COMMON_CAPS)


_COMMON_CAPS = frozenset(
    "Thanks Thank Here Hope Just Quick Please Let Sorry Also Happy Sure Okay Sending Attached Following "
    "Could Can Would Will When Once Before After Since Great Good Hi Hello Hey Dear Best Kind Regards Cheers "
    "That This These Those There They We You Our Your The And But For With From Have Has Any Not Still "
    "Small Change Correction Heads Note Update Looks Looping Forwarding See Reminder Decision Agreed".split()
)


def act_keywords(ctx: Any, comm: Any) -> list[str]:
    """Keywords of every commitment and decision a communication creates."""
    out: list[str] = []
    for a in comm.acts:
        e = ctx.events[a.event]
        if e["type"] in ("commitment.create", "decision.make"):
            out += [k for k in e.get("keywords") or [] if k not in out]
    return out
