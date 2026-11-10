"""Phrase banks: how each kind of world event is put into words (docs/generator.md, "Renderers").

Renderers never invent facts. Each **act** of a communication (a world event plus a `how`) is
turned into sentences here, in one of four registers:

- `written`: an email or chat message from its author to its audience ("I'll send you...");
- `spoken`: meeting dialogue, possibly several speakers ("Can you...?" / "Yep, will do.");
- `note`: the worker's own terse shorthand ("- me: send Ana the risk register");
- `recap`: an AI meeting recap in the third person ("Ana Velloq will send...").

Every sentence that conveys a commitment or decision contains its `what` (with names turned
into pronouns only where no keyword depends on them), so the keywords that graders match are
always present verbatim. `voice` styles a message for its author: formal, terse, chatty or
lowercase.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from wcb.render.context import RenderContext, day_words
from wcb.util.dates import add_days, parse_date
from wcb.util.text import contains_phrase, normalize
from wcb.world.comms import Act, Communication
from wcb.world.simulator import PARTICLES, PAST

# ---------------------------------------------------------------- generic banks
# Acknowledgements that never read as someone accepting an ask ("Sure." would).
BACKCHANNELS = ("Mm-hmm.", "Yeah.", "Right.", "Okay.", "Got it.", "Uh-huh.", "Mm.", "Makes sense.", "Right, right.",
                "Okay, yeah.", "Yeah, true.", "Mm, okay.", "I see.", "Fair.")
SMALL_TALK = (
    ("Can everyone hear me okay?", "Yep, you're fine."),
    ("Sorry, I was on mute.", "No worries."),
    ("How was the weekend?", "Good, quiet. Too much gardening."),
    ("Is the recording on?", "I think so, the light's on."),
    ("Let's give people a minute to join.", "Sure."),
    ("Did anyone else lose the video link?", "It's in the invite, bottom of the description."),
    ("Busy week?", "Aren't they all."),
    ("Are we waiting for anyone else?", "I think that's everyone."),
    ("My camera's being weird, bear with me.", "We can hear you, that's what matters."),
    ("Has anyone tried the new coffee machine?", "It's better than the old one, low bar."),
)
OFF_TOPIC = (
    "Unrelated, but is anyone going to the all-hands on Thursday?",
    "Side note, the third-floor printer is jammed again.",
    "Before I forget, the parking permits renew next month.",
    "Random question, does anyone know who books the big room now?",
    "Also, cake in the kitchen if anyone wants some.",
)
CUT_OFFS = ("So the thing with the—", "I was going to say, if we—", "Can we just—", "The only issue is—",
            "I think the—", "Wait, is that the—")
RESTARTS = ("Sorry, go ahead.", "No, you go.", "Sorry, you first.", "Go on.")
OPENERS = {
    "formal": ("I hope you are well.", "Thank you for your time earlier.", "Following up on our conversation.",
               "I wanted to share a short update.", "I hope the week is going smoothly.", "Apologies for the slow reply.",
               "Thank you for your patience on this.", "", ""),
    "terse": ("Quick one.", "", "", "", "Short note.", "One thing from me.", "Brief one."),
    "chatty": ("Hope your week's going well!", "Hope you had a good weekend!", "Quick one from my side!",
               "Thanks again for earlier, really helpful.", "Hope you survived the meeting marathon!",
               "Sorry this took a while!", ""),
    "lowercase": ("", "quick one", "", "fyi", "", "short one"),
}
CLOSERS = {
    "formal": ("Please let me know if you have any questions.", "Many thanks.", "Thank you in advance.",
               "I am happy to discuss further.", "With thanks for your help on this.", "", "I appreciate your time."),
    "terse": ("Thx.", "", "Shout if issues.", "", "", "Any problems, let me know.", "That's all for now.", "Ping me if unclear."),
    "chatty": ("Thanks so much!", "Shout if anything's unclear!", "Speak soon!", "Thanks a million!", "Have a good one!",
               "Let me know what you think!", ""),
    "lowercase": ("thx", "", "lmk", "ty", "", "cheers"),
}
SIGNOFFS = {
    "formal": ("Kind regards,", "Best regards,", "Regards,", "With thanks,"),
    "terse": ("", "Thanks,", "-", ""),
    "chatty": ("Cheers,", "Thanks!", "Best,", "Talk soon,"),
    "lowercase": ("", "-", "thanks", ""),
}
# Chat acknowledgements by what they answer and who answers (docs/generator.md, "Chat").
CHAT_ACKS = {
    "asked_yes": ("will do", "on it", "sure, can do", "yep, on it", "no problem"),  # the debtor, agreeing
    "asked_maybe": ("let me check and get back to you", "maybe, need to see how the week goes", "can I come back to you on this?"),
    "promised_to": ("thanks!", "perfect, thanks", "great, thank you", "appreciate it", "that'd be great"),  # the creditor
    "done_for": ("thanks!", "got it, thanks", "perfect", "thank you!", "great, thanks"),
    "fyi": ("noted", "ok", "good to know", "thanks for the heads up", "got it"),
    "decision": ("sounds good", "makes sense", "agreed", "ok, works for me", "noted"),
}
CHAT_CHIME = ("+1", "thanks for flagging", "following", "good to know", "nice", "thanks for the update")
CHAT_SMALL = (
    ("how's your week going?", "busy, but fine. you?"),
    ("are you in the office tomorrow?", "remote, but online all day"),
    ("did you catch the all-hands?", "only the first half"),
    ("thanks again for earlier", "anytime"),
    ("sorry, was in back-to-backs", "no worries"),
    ("is the shared drive slow for you too?", "yeah, it's been crawling all morning"),
    ("ok, talk later", "later!"),
    ("did the link work for you?", "yep, all good"),
)
REACTIONS = ("+1", "eyes", "white_check_mark", "pray", "raised_hands", "tada", "heavy_check_mark", "thumbsup")
# Social posts: (opener, replies, earliest minute, latest minute, weekdays or None). A post about
# a time of day goes up before that time; "happy friday" only on Fridays.
SOCIAL_CHAT = (
    ("anyone up for coffee at 3?", ("me!", "can't today, back to back", "yes please"), 8 * 60, 14 * 60 + 30, None),
    ("there's leftover cake in the kitchen on 4", ("on my way", "what kind?", "the lemon one is gone already"),
     11 * 60, 16 * 60 + 30, None),
    ("is the wifi on the second floor down for anyone else?", ("yep, same here", "works for me", "it's been flaky all morning"),
     8 * 60, 17 * 60 + 30, None),
    ("happy friday everyone", ("happy friday!", "made it", ""), 8 * 60, 12 * 60, (4,)),
    ("lost a blue umbrella, might be in the big meeting room", ("will keep an eye out", "", "there's one at reception"),
     8 * 60, 17 * 60 + 30, None),
    ("who's going to the all-hands later?", ("I'll dial in", "me", "is it in person this time?"), 8 * 60, 11 * 60 + 30,
     (0, 1, 2, 3)),
    ("reminder that the fire drill is at 11", ("thanks for the heads up", "again?", ""), 8 * 60, 10 * 60 + 40, (0, 1, 2, 3, 4)),
    ("any lunch recommendations near the office?", ("the noodle place on the corner", "the salad bar is decent", ""),
     10 * 60, 12 * 60 + 30, None),
    ("the elevator on the east side is out again", ("stairs it is", "classic", ""), 8 * 60, 17 * 60 + 30, None),
    ("does anyone have a spare laptop charger (usb-c)?", ("I have one, desk by the window", "", "check the supply cupboard"),
     8 * 60, 17 * 60 + 30, None),
    ("is it just me or is it freezing on 3 today?", ("not just you", "bring a jumper", ""), 8 * 60, 15 * 60, None),
    ("who left a lunchbox in the fridge since last week?", ("not me!", "", "it's been there a while"), 11 * 60, 17 * 60, None),
    ("anyone else in today?", ("just me and the cleaners", "here till 1", ""), 8 * 60, 14 * 60, (5,)),
    ("good morning all", ("morning!", "morning", ""), 7 * 60 + 30, 10 * 60 + 30, None),
)


# ---------------------------------------------------------------- small text helpers
def lower_first(s: str) -> str:
    w = s.split(" ", 1)[0]
    if len(w) > 1 and (w.isupper() or (w[:1].isupper() and any(c.isupper() for c in w[1:]))):
        return s
    return s[:1].lower() + s[1:]


def upper_first(s: str) -> str:
    return s[:1].upper() + s[1:]


def sentence(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    s = upper_first(s)
    return s if s[-1] in ".!?:" else s + "."


def has_keywords(text: str, keywords: list[str]) -> bool:
    """True if every keyword occurs in `text` (case- and accent-insensitive, as graders match)."""
    low = normalize(text)
    return all(normalize(k) in low or contains_phrase(text, k) for k in keywords)


def missing_keywords(text: str, keywords: list[str]) -> list[str]:
    low = normalize(text)
    return [k for k in keywords if not (normalize(k) in low or contains_phrase(text, k))]


def lowercase_keep(text: str, keep: list[str]) -> str:
    """Lowercase `text` except for the literal strings in `keep` (secrets, links, codes)."""
    if not keep:
        return text.lower()
    pattern = "|".join(re.escape(k) for k in sorted(set(keep), key=len, reverse=True) if k)
    if not pattern:
        return text.lower()
    out, pos = [], 0
    for m in re.finditer(pattern, text):
        out.append(text[pos:m.start()].lower())
        out.append(m.group(0))
        pos = m.end()
    out.append(text[pos:].lower())
    return "".join(out)


# ---------------------------------------------------------------- naming within one artifact
@dataclass
class Namer:
    """Turns person IDs into words for one artifact, from one point of view.

    `speaker` is "I"; a single `audience` member is "you". People this artifact introduces
    are named in full (with their role) the first time; everyone else by the communication's
    name form for them, usually a bare first name.
    """

    ctx: RenderContext
    comm: Communication
    speaker: str | None = None
    audience: list[str] = field(default_factory=list)
    third_person: bool = False  # recap register: never "I" or "you"
    fresh: set[str] = field(default_factory=set)
    introduced: set[str] = field(default_factory=set)
    them: set[str] = field(default_factory=set)  # people referred to as "they" in this sentence

    def __post_init__(self) -> None:
        if not self.fresh:
            self.fresh = {e for e in self.ctx.introduces(self.comm) if e.startswith("p-")}

    def view(self, speaker: str | None, audience: list[str] | None = None, *, them: set[str] | None = None) -> Namer:
        """The same artifact from another speaker's point of view (shares introductions)."""
        n = Namer(self.ctx, self.comm, speaker, list(audience or []), self.third_person, self.fresh,
                  self.introduced, set(them or ()))
        return n

    def vocative(self, pid: str) -> str:
        """How a speaker addresses someone by name ('Ana, could you...'): never a pronoun."""
        if pid in self.fresh and pid not in self.introduced:
            self.introduced.add(pid)
            return self.ctx.full(pid)
        base = self.ctx.call_name(pid, self.comm)
        if self.speaker and pid != self.speaker and base == self.ctx.first(self.speaker):
            return self.ctx.full(pid)
        return base

    def you(self, pid: str | None) -> bool:
        return not self.third_person and len(self.audience) == 1 and pid == self.audience[0]

    def name(self, pid: str | None, case: str = "obj", *, full: bool = False) -> str:
        if pid is None:
            return "someone"
        if not self.third_person and pid == self.speaker:
            return {"subj": "I", "obj": "me", "poss": "my"}[case]
        if self.you(pid):
            return {"subj": "you", "obj": "you", "poss": "your"}[case]
        if pid in self.them:
            return {"subj": "they", "obj": "them", "poss": "their"}[case]
        if pid in self.fresh and pid not in self.introduced:
            self.introduced.add(pid)
            base = self.ctx.full(pid)
            if case != "poss" and not self.ctx.is_bot(pid):
                role = self.ctx.short_role(pid)
                org = self.ctx.org_of(pid)
                if role:
                    at = f" at {org['short']}" if org and org["role"] not in ("central", "umbrella") else ""
                    base = f"{base} ({role}{at})"
        elif full or self.third_person and pid in self.ctx.collisions:
            base = self.ctx.full(pid)
        else:
            base = self.ctx.form(pid, self.comm)
            # Never a bare first name that the speaker or the person addressed also answers to.
            mine = {self.ctx.first(x) for x in (self.speaker, *self.audience) if x and x != pid}
            if base in mine:
                base = self.ctx.full(pid)
        return base + "'s" if case == "poss" else base

    def subj(self, pid: str | None) -> str:
        return self.name(pid, "subj")

    def will(self, pid: str | None) -> str:
        s = self.subj(pid)
        return {"I": "I'll", "you": "you'll"}.get(s, f"{s} will")

    def mentioned(self, pid: str) -> None:
        if pid in self.fresh:
            self.introduced.add(pid)


# ---------------------------------------------------------------- verb phrases from `what`
_PAST_EXTRA = {"take": "took", "make": "made", "lead": "led", "give": "gave", "find": "found",
               "build": "built", "send": "sent", "write": "wrote", "keep": "kept", "bring": "brought"}


def names_in(ctx: RenderContext, text: str) -> list[str]:
    return [f for f in sorted(ctx.first_names, key=len, reverse=True) if re.search(rf"\b{re.escape(f)}\b", text)]


def resolve_first(ctx: RenderContext, first: str, roles: list[str | None]) -> str | None:
    """The person a first name in a loop's text refers to (preferring the loop's parties)."""
    for pid in roles:
        if pid and ctx.first(pid) == first:
            return pid
    cands = ctx.by_first.get(first, [])
    return cands[0] if len(cands) == 1 else None


def vp(ctx: RenderContext, namer: Namer, what: str, keywords: list[str], roles: list[str | None]) -> str:
    """`what` as a verb phrase for this point of view: 'Send Ana the plan' -> 'send me the plan'.

    Names (full or first) are swapped for pronouns or name forms unless a keyword contains them."""
    out = what
    kws = [k.lower() for k in keywords]
    for first in names_in(ctx, what):
        if any(first.lower() in k for k in kws):
            continue
        pid = resolve_first(ctx, first, roles)
        if pid is None:
            continue
        full = ctx.full(pid)
        last = full[len(first):].strip()
        tail = rf"(?:\s+{re.escape(last)})?" if last else ""
        pat_poss = re.compile(rf"\b{re.escape(first)}{tail}'s\b")
        pat = re.compile(rf"\b{re.escape(first)}{tail}\b")
        if pat_poss.search(out):
            out = pat_poss.sub(lambda _m, pid=pid: namer.name(pid, "poss"), out, count=1)
        elif pat.search(out):
            out = pat.sub(lambda _m, pid=pid: namer.name(pid, "obj"), out, count=1)
    out = lower_first(out)
    return out if has_keywords(out, keywords) else lower_first(what)


def past_vp(ctx: RenderContext, namer: Namer, what: str, roles: list[str | None]) -> str:
    """'Send Ana the plan' -> 'sent you the plan' (no subject)."""
    v = vp(ctx, namer, what, [], roles)
    verb, _, rest = v.partition(" ")
    pv = PAST.get(verb.lower()) or _PAST_EXTRA.get(verb.lower())
    if pv is None:
        return f"finished: {v}"
    return f"{pv} {rest}".strip()


def subject_of(ctx: RenderContext | set[str], what: str) -> str:
    """A noun phrase for a loop: 'Send Ana the Heron risk register' -> 'the Heron risk register'.

    `ctx` is a render context or a plain set of first names."""
    first_names = ctx if isinstance(ctx, (set, frozenset)) else ctx.first_names
    words = what.split()
    if len(words) < 2:
        return what
    i = 1
    if i < len(words) and words[i].lower() in PARTICLES:
        i += 1
    if i < len(words) and (words[i] in first_names or words[i] in ("me", "you", "them")):
        i += 1
    if i < len(words) and words[i].lower() in PARTICLES:
        i += 1
    rest = words[i:]
    # drop a trailing "with Ana" naming a person (only at the very end of the phrase)
    if len(rest) >= 2 and rest[-2].lower() in ("with", "for", "to") and rest[-1] in first_names:
        rest = rest[:-2]
    if not rest:
        return lower_first(what)
    if rest[0].lower() in ("the", "a", "an", "our", "my"):
        return " ".join(["the", *rest[1:]]) if rest[0].lower() != "a" else " ".join(rest)
    if rest[0].endswith("'s"):
        return " ".join(rest)
    if rest[0].lower() in ("to", "with", "for", "about", "on", "in"):
        return lower_first(what)
    return "the " + " ".join(rest)


def subject_with_keywords(ctx: RenderContext, what: str, keywords: list[str]) -> str:
    s = subject_of(ctx, what)
    return s if has_keywords(s, keywords) else lower_first(what)


def subject_for(ctx: RenderContext, namer: Namer, what: str, keywords: list[str], roles: list[str | None]) -> str:
    """`subject_with_keywords` from a point of view: names left in the phrase become pronouns
    ('the plan after Ana's comments' said by Ana -> 'the plan after my comments')."""
    s = subject_with_keywords(ctx, what, keywords)
    out = vp(ctx, namer, s, keywords, roles)
    return out if has_keywords(out, keywords) else s


def due_words(due: str | None, ref: str, rng: random.Random, *, prefix: str = " by ") -> str:
    if not due:
        return ""
    if due == add_days(ref, 1) and rng.random() < 0.3:
        return prefix + "tomorrow"
    d, r = parse_date(due), parse_date(ref)
    if 0 < (d - r).days < 6 and d.weekday() > r.weekday() and rng.random() < 0.3:
        return prefix + d.strftime("%A")
    return prefix + day_words(due, rng.choice([0, 0, 1, 2, 3]))


def reason_of(summary: str) -> str:
    m = re.search(r"\(([^()]*)\)\s*$", summary)
    if m:
        return m.group(1)
    if ": " in summary:
        return summary.split(": ", 1)[1]
    return ""


DELIVERY_VERBS = ("Send", "Share", "Write", "Draft", "Assemble", "Turn", "Circulate", "Summarize", "Pull")

STATUS_WORDS = {
    "active": ("active again", "back in progress"),
    "paused": ("on hold", "paused"),
    "dormant": ("dormant", "stalled"),
    "done": ("complete", "done"),
    "cancelled": ("cancelled", "shelved"),
}


# ---------------------------------------------------------------- the phraser
@dataclass
class Line:
    """One utterance: who says it (None: the artifact's author) and the text."""

    speaker: str | None
    text: str
    act: str | None = None  # event id the line conveys


class Phraser:
    """Sentences for the acts of one communication."""

    def __init__(self, ctx: RenderContext, comm: Communication, rng: random.Random):
        self.ctx = ctx
        self.comm = comm
        self.rng = rng
        self.ref = comm.t[:10]

    # ------------------------------------------------------------ dispatch
    def lines(self, act: Act, namer: Namer, register: str) -> list[Line]:
        """Lines conveying `act`. `namer.speaker` is the author for written and note registers.

        The `report` register (a status report) is the note register with resolutions in the
        past tense."""
        e = self.ctx.events[act.event]
        if register == "report" and e["type"] == "commitment.resolve" and e["status"] == "done":
            lp = self._loop(e["commitment"], e["id"])
            roles = [lp["debtor"], lp["creditor"], *(lp.get("others") or []), self.ctx.worker]
            pv = past_vp(self.ctx, namer, lp["what"], roles)
            return [Line(None, f"- {upper_first(namer.name(lp['debtor'], 'subj'))} {pv}", act.event)]
        if self.is_repeat(act) and e["type"] in ("commitment.create", "commitment.resolve", "decision.make") \
                and register in ("written", "spoken"):
            out = self._recap_line(e, act, namer, register)
            for ln in out:
                ln.act = act.event
            return out
        fn = getattr(self, "_" + e["type"].replace(".", "_"))
        out = fn(e, act, namer, "note" if register == "report" else register)
        for ln in out:
            ln.act = act.event
        return out

    def created_here(self, cid: str) -> bool:
        """Whether this communication also reveals the loop's creation."""
        create = self.ctx.loop_create.get(cid)
        return create is not None and any(a.event == create["id"] for a in self.comm.acts)

    def is_repeat(self, act: Act) -> bool:
        """The act restates an event from an earlier day that an earlier input already revealed."""
        e = self.ctx.events[act.event]
        first = self.ctx.first_revealer.get(act.event)
        return first is not None and first != self.comm.id and e["t"][:10] < self.ref

    def when(self, e: dict) -> str:
        """'yesterday', 'Friday' (within six days) or '2 April'."""
        d, r = parse_date(e["t"][:10]), parse_date(self.ref)
        if (r - d).days == 1:
            return "yesterday"
        if 0 < (r - d).days < 7:
            return d.strftime("%A")
        return day_words(e["t"][:10], 3)

    def _recap_line(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        """A restatement of an earlier event, framed in the past so it asserts nothing new."""
        ctx = self.ctx
        parts = [p for p in dict.fromkeys([self.comm.sender, *self.comm.participants]) if p]
        sp = nm.speaker if reg == "written" else (act.by if act.by in parts else self.comm.sender)
        v = nm if reg == "written" else nm.view(sp, [])
        when = self.when(e)
        on = when if when == "yesterday" else "on " + when
        if e["type"] == "decision.make":
            w = lower_first(e["what"])
            return [Line(sp, self.choose([f"Recap from {when}: we decided to {w}.", f"As agreed {on}, we'll {w}."]))]
        if e["type"] == "commitment.create":
            D, Cr = e["debtor"], e["creditor"]
            roles = [D, Cr, *(e.get("others") or []), ctx.worker]
            X = vp(ctx, v, e["what"], list(e.get("keywords") or []), roles)
            who = v.name(D, "subj")
            if not ctx.accepted_at(e["commitment"], self.comm):
                # Never agreed (as far as anything delivered so far shows): say it was only asked.
                asker = v.name(Cr, "subj")
                return [Line(sp, self.choose([
                    f"Recap from {when}: {asker} asked {v.name(D)} to {X}; nothing agreed yet.",
                    f"Just to recap, {on} {asker} raised whether {who} could {X}. Not agreed yet.",
                ]))]
            if e.get("kind") == "task" and D != Cr:
                return [Line(sp, self.choose([f"Recap from {when}: {who} offered to {X}.",
                                              f"Just to recap, {on} {who} said {who if who in ('I', 'you') else 'they'}'d {X}."]))]
            return [Line(sp, self.choose([f"Recap from {when}: {who} agreed to {X}.",
                                          f"Just to recap, {on} {who} said {who if who in ('I', 'you') else 'they'}'d {X}."]))]
        lp = self._loop(e["commitment"], e["id"])
        roles = [lp["debtor"], lp["creditor"], *(lp.get("others") or []), ctx.worker]
        if e["status"] == "dropped":
            subj = subject_for(ctx, v, lp["what"], lp.get("keywords") or [], roles)
            return [Line(sp, f"Recap: we dropped {subj} {on}.")]
        pv = past_vp(ctx, v, lp["what"], roles)
        return [Line(sp, self.choose([f"For the record, {v.name(lp['debtor'], 'subj')} {pv} {on}.",
                                      f"Recap from {when}: {v.name(lp['debtor'], 'subj')} {pv}."]))]

    def choose(self, options: list[str] | tuple[str, ...]) -> str:
        opts = [o for o in options if o is not None]
        return self.rng.choice(opts)

    # ------------------------------------------------------------ loops
    def _loop(self, cid: str, before_event: str | None = None) -> dict:
        if before_event and before_event in self.ctx.loop_before:
            return self.ctx.loop_before[before_event]
        e = self.ctx.loop_create[cid]
        return {k: e.get(k) for k in ("what", "debtor", "creditor", "others", "project", "status", "due",
                                      "accepted", "kind", "keywords")}

    def _commitment_create(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx, rng = self.ctx, self.rng
        D, Cr = e["debtor"], e["creditor"]
        others = list(e.get("others") or [])
        kws = list(e.get("keywords") or [])
        roles = [D, Cr, *others, ctx.worker]
        due = due_words(e.get("due"), self.ref, rng)
        how = act.how
        accepted = ctx.accepted_at(e["commitment"], self.comm)
        S = nm.speaker
        if reg == "recap":
            nm3 = nm
            X = vp(ctx, nm3, e["what"], kws, roles)
            Dn = nm3.name(D, "subj", full=True)
            if not accepted or how == "implied":
                return [Line(None, self.choose([f"Possible follow-up: {Dn} to {X}{due}.",
                                                f"Suggested action: {Dn} may {X}{due}."]))]
            return [Line(None, self.choose([f"{Dn} will {X}{due}.", f"{Dn} to {X}{due}.",
                                            f"{Dn} agreed to {X}{due}."]))]
        if reg == "note":
            X = vp(ctx, nm, e["what"], kws, roles)
            if not accepted:
                if D == ctx.worker:
                    return [Line(None, self.choose([f"- {nm.name(Cr)} wants me to {X} - haven't said yes",
                                                    f"- maybe: {X}? not committed yet"]))]
                return [Line(None, f"- possible: {nm.name(D)} to {X}{due} (not confirmed)")]
            if D == ctx.worker:
                if how == "hedged":
                    return [Line(None, f"- try to {X}{due} (soft)")]
                return [Line(None, self.choose([f"- me: {X}{due}", f"- todo: {X}{due}", f"- {X}{due} (mine)"]))]
            if Cr == ctx.worker:
                return [Line(None, self.choose([f"- {nm.name(D)} to {X}{due}", f"- waiting on {nm.name(D)}: {X}{due}",
                                                f"- asked {nm.name(D)} to {X}{due}"]))]
            return [Line(None, f"- {nm.name(D)} owes {nm.name(Cr)}: {X}{due}")]

        # written and spoken registers
        if reg == "spoken":
            return self._create_dialogue(e, act, nm, D, Cr, others, kws, roles, due)
        X = vp(ctx, nm, e["what"], kws, roles)
        if S == D:
            if how == "implied":
                subj = subject_with_keywords(ctx, e["what"], kws)
                opts = [f"Let me take a look at {subj}.", f"Leave {subj} with me.", f"I'll dig into {subj}."]
                if subj == lower_first(e["what"]):
                    opts = [f"Let me {X}.", f"I'll see about it: {X}."]
                return [Line(S, self.choose(opts))]
            if how == "hedged":
                return [Line(S, self.choose([f"I can try to {X}{due}, no promises on timing.",
                                             f"I'll see if I can {X}{due}.",
                                             f"Let me try to {X}{due}, it might slip a bit."]))]
            if not accepted:
                return [Line(S, self.choose([f"I could {X}{due} if that helps?",
                                             f"Happy to {X} if useful, let me know."]))]
            if others:
                return [Line(S, self.choose([f"{nm.name(others[0], 'subj')} and I will {X}{due}.",
                                             f"I'll {X}{due}, with {nm.name(others[0])}."]))]
            return [Line(S, self.choose([f"I'll {X}{due}.", f"I can {X}{due}.", f"On it, I'll {X}{due}.",
                                         f"Leave it with me, I'll {X}{due}.", f"Will {X}{due}."]))]
        if S == Cr:
            if nm.you(D) or (len(nm.audience) == 1 and D in nm.audience):
                if e.get("kind") == "task" and accepted and D != ctx.worker:
                    return [Line(S, self.choose([f"Thanks for offering to {X}{due}, that would be great.",
                                                 f"You mentioned you'd {X}{due}, that works for me.",
                                                 f"Great if you can {X}{due}."]))]
                return [Line(S, self.choose([f"Could you {X}{due}?", f"Can you {X}{due}?",
                                             f"Would you be able to {X}{due}?",
                                             f"When you get a chance, could you {X}{due}?"]))]
            if D == ctx.worker and not nm.you(D):
                return [Line(S, f"I've asked {nm.name(D)} to {X}{due}.")]
            return [Line(S, self.choose([f"I've asked {nm.name(D)} to {X}{due}.",
                                         f"{upper_first(nm.will(D))} {X}{due}."]))]
        # someone else reports it (second-hand, FYI, a relayed ask)
        Dw = nm.will(D)
        if D == ctx.worker and nm.you(D):
            Xt = vp(ctx, nm.view(S, nm.audience, them={Cr}), e["what"], kws, roles)
            return [Line(S, self.choose([f"{upper_first(nm.name(Cr, 'subj'))} is expecting you to {Xt}{due}.",
                                         f"{upper_first(nm.name(Cr, 'subj'))} asked if you could {Xt}{due}."]))]
        if not accepted:
            if nm.you(Cr):
                return [Line(S, self.choose([f"{upper_first(nm.name(D, 'subj'))} might {X}{due}, nothing confirmed yet.",
                                             f"{upper_first(nm.name(D, 'subj'))} could probably {X}{due}, not agreed though."]))]
            return [Line(S, f"{upper_first(nm.name(Cr, 'subj'))} would like {nm.name(D)} to {X}{due}, not agreed yet.")]
        return [Line(S, self.choose([f"FYI {Dw} {X}{due}.", f"Heads up: {Dw} {X}{due}.",
                                     f"From the sync earlier, {Dw} {X}{due}.",
                                     f"{upper_first(Dw)} {X}{due}, as discussed."]))]

    def _create_dialogue(self, e, act, nm: Namer, D, Cr, others, kws, roles, due) -> list[Line]:
        """A commitment made in a meeting, as dialogue.

        An ask is put to the debtor by name and answered by the debtor straight away; an offer
        or promise is made by the debtor. If the debtor is not in the room, an accepted loop is
        reported ("Ana said she'd...") and an unaccepted one is only floated."""
        ctx, rng = self.ctx, self.rng
        parts = set(self.comm.participants) | {self.comm.sender}
        how = act.how
        accepted = ctx.accepted_at(e["commitment"], self.comm)
        present = D in parts
        out: list[Line] = []
        if how == "implied" and present:
            raiser = Cr if Cr in parts and Cr != D else self._someone_else(D)
            subj = subject_for(ctx, nm.view(raiser), e["what"], kws, roles) if raiser else \
                subject_with_keywords(ctx, e["what"], kws)
            if raiser:
                out.append(Line(raiser, self.choose([f"We're still seeing problems with {subject_of(ctx, e['what'])}.",
                                                     f"Has anyone looked at {subj}?",
                                                     f"The other thing is {subj}, it's still not right."])))
            out.append(Line(D, self.choose([f"Let me take a look at {subj}.", f"Yeah, leave {subj} with me.",
                                            f"Okay, let me look into {subj}."])))
            return out
        if present and e.get("kind") == "ask" and Cr in parts and Cr != D and how != "hedged" and rng.random() < 0.8:
            v = nm.view(Cr, [D])
            X = vp(ctx, v, e["what"], kws, roles)
            voc = v.vocative(D)
            out.append(Line(Cr, self.choose([f"{voc}, could you {X}{due}?", f"{voc}, can you {X}{due}?",
                                             f"{voc}, would you be able to {X}{due}?", f"Could you {X}{due}, {voc}?"])))
            v2 = nm.view(D, [Cr])
            if accepted:
                out.append(Line(D, self.choose(["Yep, will do.", "Sure, I can do that.", "Yeah, no problem.",
                                                "Okay, I'll get that done.", f"Sure, I'll {vp(ctx, v2, e['what'], kws, roles)}."])))
            else:
                out.append(Line(D, self.choose(["Let me check what I've got on and come back to you.",
                                                "Maybe, I need to see how this week goes.", "I'll think about it.",
                                                "Possibly. Can I get back to you on that?"])))
            return out
        if present:
            v = nm.view(D, [Cr] if Cr in parts and len(parts) == 2 and Cr != D else [])
            X = vp(ctx, v, e["what"], kws, roles)
            if how == "hedged":
                txt = self.choose([f"I can probably {X}{due}, maybe next week.", f"I'll try to {X}{due}, no promises.",
                                   f"I could look at it, I mean, {X}{due}, sometime next week?"])
            elif not accepted:
                txt = self.choose([f"I could {X}{due}, if that's useful?", f"Maybe I should {X}{due}."])
            elif others:
                txt = f"{upper_first(v.name(others[0], 'subj'))} and I can {X}{due}."
            else:
                txt = self.choose([f"I'll {X}{due}.", f"I can {X}{due}.", f"Okay, I'll {X}{due}.",
                                   f"Yeah, I'll {X}{due}.", f"Let me {X}{due}."])
            out.append(Line(D, txt))
            if Cr in parts and Cr != D and accepted and how != "hedged" and rng.random() < 0.5:
                out.append(Line(Cr, self.choose(["That'd be great, thanks.", "Perfect, thank you.", "Great, thanks.",
                                                 "Thanks, that helps."])))
            return out
        # The debtor is not in the room.
        speaker = act.by if act.by in parts else (Cr if Cr in parts else self.comm.sender)
        v = nm.view(speaker, [])
        X = vp(ctx, v, e["what"], kws, roles)
        Dn = upper_first(v.name(D, "subj"))
        if accepted:
            txt = self.choose([f"{Dn} said they'd {X}{due}.", f"I spoke to {v.name(D)}, they'll {X}{due}.",
                               f"{Dn} has agreed to {X}{due}."])
        else:
            txt = self.choose([f"It would help if {v.name(D)} could {X}{due}, but nothing's agreed.",
                               f"I'd like {v.name(D)} to {X}{due}; I haven't asked yet.",
                               f"Could {v.name(D, 'subj')} {X}{due}? Worth asking."])
        out.append(Line(speaker, txt))
        return out

    def _someone_else(self, pid: str) -> str | None:
        opts = [p for p in self.comm.participants if p != pid]
        return self.rng.choice(opts) if opts else None

    def _commitment_resolve(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx = self.ctx
        lp = self._loop(e["commitment"], e["id"])
        D, Cr = lp["debtor"], lp["creditor"]
        roles = [D, Cr, *(lp.get("others") or []), ctx.worker]
        kws = list(lp.get("keywords") or [])
        subj = subject_for(ctx, nm, lp["what"], kws, roles)
        S = nm.speaker
        if e["status"] == "dropped":
            reason = reason_of(e.get("summary", ""))
            r = f" ({reason})" if reason else ""
            if reg == "note":
                return [Line(None, self.choose([f"- drop: {subj}{r}", f"- not doing {subj} any more{r}"]))]
            if reg == "recap":
                return [Line(None, f"{upper_first(subj)} was dropped{r}.")]
            return [Line(S, self.choose([f"Let's drop {subj}{', ' + reason if reason else ''}.",
                                         f"I'm going to park {subj}{r}.",
                                         f"No need for {subj} any more{', ' + reason if reason else ''}."]))]
        if reg == "note":
            pv = past_vp(ctx, nm, lp["what"], roles)
            return [Line(None, self.choose([f"- done: {nm.name(D, 'subj')} {pv}", f"- x {subj} (done)",
                                            f"- {subj}: done"]))]
        if reg == "recap":
            n3 = nm
            return [Line(None, f"{n3.name(D, 'subj', full=True)} confirmed {subj} is done.")]
        if act.how == "indirect":
            return [Line(S, self.choose(indirect_closure(lp["what"], subj, ctx.call_name(D, self.comm))))]
        speaker = S
        if reg == "spoken":
            parts = set(self.comm.participants) | {self.comm.sender}
            speaker = D if D in parts else (act.by if act.by in parts else self.comm.sender)
            nm = nm.view(speaker, [])
            subj = subject_for(ctx, nm, lp["what"], kws, roles)
        pv = past_vp(ctx, nm, lp["what"], roles)
        verb = lp["what"].split(" ", 1)[0]
        if self.created_here(e["commitment"]):
            return [Line(speaker, self.choose([f"Okay, {subj} is done now.", f"That's {subj} done, by the way.",
                                               f"Update: {nm.name(D, 'subj')} {pv} just now."]))]
        if speaker == D and self.comm.kind == "email" and verb in DELIVERY_VERBS and act.how == "direct":
            return [Line(speaker, self.choose([f"Here's {subj}, as promised.", f"Sending over {subj}.",
                                               f"As promised, here's {subj}."]))]
        if speaker == D:
            return [Line(speaker, self.choose([f"I {pv}.", f"Just {pv}.", f"Done, I {pv}.",
                                               f"I {pv} earlier today." if e["t"][:10] == self.ref else f"I {pv}."]))]
        if speaker == Cr and nm.you(D):
            return [Line(speaker, self.choose([f"Thanks for {subj}, got it.", f"Received {subj}, thank you!",
                                               f"Got {subj}, thanks."]))]
        return [Line(speaker, self.choose([f"FYI {nm.name(D, 'subj')} {pv}.", f"{upper_first(nm.name(D, 'subj'))} {pv}, so that one's done.",
                                           f"Looks like {nm.name(D, 'subj')} {pv}."]))]

    def _commitment_update(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx = self.ctx
        lp = self._loop(e["commitment"], e["id"])
        ch = e.get("changes") or {}
        D, Cr = lp["debtor"], lp["creditor"]
        roles = [D, Cr, *(lp.get("others") or []), ctx.worker, ch.get("debtor")]
        kws = list(lp.get("keywords") or [])
        S = nm.speaker
        summ = e.get("summary", "")
        if reg == "spoken":
            parts = set(self.comm.participants) | {self.comm.sender}
            S = act.by if act.by in parts else (D if D in parts else self.comm.sender)
            nm = nm.view(S, [])
        subj = subject_for(ctx, nm, lp["what"], kws, roles)
        def say(txt: str) -> list[Line]:
            return [Line(None if reg in ("note", "recap") else S, txt)]

        if act.how == "second_hand" and reg in ("written", "spoken") and "due" not in ch:
            return say(self._relayed_update(lp, ch, summ, subj, nm))

        if "debtor" in ch:
            new = ch["debtor"]
            if reg == "note":
                return say(f"- {subj}: now with {nm.name(new)} (was {nm.name(D)})")
            if reg == "recap":
                return say(f"{upper_first(subj)} moves from {nm.name(D, full=True)} to {nm.name(new, full=True)}.")
            if S == D:
                return say(self.choose([f"I'm handing {subj} over to {nm.name(new)}, {nm.will(new)} take it from here.",
                                        f"{upper_first(nm.name(new, 'subj'))} is taking over {subj} from me.",
                                        f"Passing {subj} to {nm.name(new)}, who's closer to it."]))
            return say(f"{upper_first(nm.name(new, 'subj'))} is picking up {subj} from {nm.name(D)}.")
        if "accepted" in ch:
            due = due_words(ch.get("due"), self.ref, self.rng)
            X = vp(ctx, nm, lp["what"], kws, roles)
            if reg == "note":
                if D == ctx.worker:
                    return say(self.choose([f"- ok, I'll {X}{due}", f"- agreed: {X}{due}", f"- yes to {X}{due}"]))
                return say(f"- confirmed: {nm.name(D)} to {X}{due}")
            if reg == "recap":
                return say(f"Confirmed: {nm.name(D, 'subj', full=True)} will {X}{due}.")
            if S == D and not nm.audience:
                return say(self.choose([f"Decided I'll {X}{due}.", f"Okay, I'm taking this on: {X}{due}."]))
            if S == D:
                return say(self.choose([f"Yes, happy to {X}{due}.", f"Okay, I'll take it: {X}{due}."]))
            return say(f"Let's make it official: {nm.will(D)} {X}{due}.")
        if "due" in ch:
            new_due = ch["due"]
            old = lp.get("due")
            nd = day_words(new_due, self.rng.choice([0, 1, 2, 3]))
            od = f" (was {day_words(old, 3)})" if old else ""
            if act.how == "correction":
                if reg in ("note", "recap"):
                    return say(f"Correction: {subj} is due {nd}{od}.")
                return say(self.choose([f"Correction to what I said earlier: {subj} is actually due {nd}{', not ' + day_words(old, 3) if old else ''}.",
                                        f"Small correction, {subj} is due {nd}{od}."]))
            if act.how == "second_hand":
                if reg not in ("note", "recap"):
                    return say(f"FYI {nm.name(Cr, 'subj')} needs {subj} by {nd}.")
            if reg == "note":
                return say(f"- {subj}: now due {nd}{od}")
            if reg == "recap":
                return say(f"{upper_first(subj)} is now due {nd}{od}.")
            return say(self.choose([f"Small change: we need {subj} by {nd}{od}.",
                                    f"Can we move {subj} to {nd}{od}?" if S == Cr else f"{upper_first(subj)} is now due {nd}{od}.",
                                    f"{upper_first(subj)} is now due {nd}{od}."]))
        if "status" in ch:
            new = ch["status"]
            reason = reason_of(summ)
            if new == "blocked":
                if reg in ("note", "recap"):
                    return say(f"{'- ' if reg == 'note' else ''}{subj}: blocked, {reason}")
                return say(self.choose([f"{upper_first(subj)} is blocked, {reason}.",
                                        f"I'm stuck on {subj}: {reason}."]))
            if new == "waiting":
                other = Cr if D == ctx.worker else D
                if reg == "note":
                    return say(f"- {subj}: waiting on {nm.name(other)}")
                if reg == "recap":
                    return say(f"{upper_first(subj)} is waiting on {nm.name(other, full=True)}.")
                if D == ctx.worker:
                    return say(self.choose([f"Before I can finish {subj} I need your input, over to you for now."
                                            if nm.you(other) else f"I'm waiting on {nm.name(other)} before I can finish {subj}.",
                                            f"{upper_first(subj)} is on hold until I hear back from {nm.name(other)}."]))
                return say(self.choose([f"Just checking in on {subj}, I'm waiting on this from {nm.name(other)}.",
                                        f"Any news on {subj}? I'm blocked until it lands."]))
            if summ.startswith("Correction") or act.how == "correction":
                if reg in ("note", "recap"):
                    return say(f"{'- ' if reg == 'note' else ''}correction: {subj} is not done after all, open again")
                return say(self.choose([f"Correction to what I said earlier: {subj} isn't done after all. "
                                        f"The change was rolled back, so it's open again.",
                                        f"Sorry, I was wrong before: {subj} didn't hold and has been rolled back. "
                                        f"It's back on the list."]))
            if summ.startswith("Reopened"):
                r = f": {reason}" if reason else ""
                if reg in ("note", "recap"):
                    return say(f"{'- ' if reg == 'note' else ''}reopened {subj}{r}")
                return say(self.choose([f"Reopening {subj}{r}.", f"I need to reopen {subj}{r}."]))
            # back to open
            if reg in ("note", "recap"):
                return say(f"{'- ' if reg == 'note' else ''}{subj}: back in progress")
            return say(self.choose([f"Picking {subj} back up now.", f"Got what I needed, {subj} is moving again.",
                                    f"{upper_first(subj)} is back on, sorry for the delay."]))
        if reg in ("note", "recap"):
            return say(f"{'- ' if reg == 'note' else ''}{lower_first(summ)}")
        return say(sentence(summ))

    def _relayed_update(self, lp: dict, ch: dict, summ: str, subj: str, nm: Namer) -> str:
        """Someone other than the parties reports a change to a loop."""
        ctx = self.ctx
        D, Cr = lp["debtor"], lp["creditor"]
        if "debtor" in ch:
            return f"FYI {subj} has moved from {nm.name(D)} to {nm.name(ch['debtor'])}."
        if "accepted" in ch:
            return f"FYI {nm.name(D, 'subj')} {'are' if nm.you(D) else 'is'} now down to do {subj}."
        new = ch.get("status")
        if new == "waiting":
            other = Cr if D == ctx.worker else D
            return f"FYI {subj} is waiting on {nm.name(other)}."
        if new == "blocked":
            return f"FYI {subj} is blocked: {reason_of(summ)}."
        if summ.startswith(("Reopened", "Correction")):
            return f"FYI {subj} has been reopened."
        return f"FYI {subj} is moving again."

    # ------------------------------------------------------------ decisions
    def _decision_make(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        w = lower_first(e["what"])
        if reg == "note":
            return [Line(None, self.choose([f"- decided: {w}", f"- decision: {w}", f"- going with: {w}"]))]
        if reg == "recap":
            return [Line(None, f"Decision: {upper_first(w)}.")]
        if reg == "spoken":
            parts = list(dict.fromkeys([self.comm.sender, *self.comm.participants]))
            by = [p for p in e.get("by") or [] if p in parts]
            speaker = by[0] if by else self.comm.sender
            other = next((p for p in parts if p != speaker), None)
            out = [Line(speaker, self.choose([f"So I think we {w}.", f"Okay, let's {w}.",
                                              f"Proposal: we {w}. Any objections?", f"Let's just {w}, then."]))]
            if other:
                out.append(Line(other, self.choose(["Agreed.", "Works for me.", "Yeah, fine by me.", "No objections."])))
            return out
        if act.how == "second_hand":
            by = [p for p in e.get("by") or [] if p != nm.speaker]
            if not by or any(nm.you(p) for p in by):
                return [Line(nm.speaker, f"Noting for the record that we'll {w}.")]
            return [Line(nm.speaker, f"FYI {nm.name(by[0], 'subj')} decided to {w}.")]
        return [Line(nm.speaker, self.choose([f"We've agreed to {w}.", f"Decision: {w}.", f"Let's {w}.",
                                              f"Confirming we'll {w}."]))]

    def _decision_reverse(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        d = self.ctx.dec_create.get(e["decision"], {})
        w = lower_first(d.get("what", "the earlier plan"))
        reason = e.get("reason") or reason_of(e.get("summary", ""))
        sp = nm.speaker if reg == "written" else (self.comm.sender if reg == "spoken" else None)
        if sp:
            reason = first_person(reason, self.ctx.first(sp))
        if reg == "note":
            return [Line(None, f"- reversed: no longer {w} ({reason})")]
        if reg == "recap":
            return [Line(None, f"The earlier decision to {w} was reversed ({reason}).")]
        if reg == "spoken":
            sp = self.comm.sender
            return [Line(sp, f"I want to revisit the decision to {w}. {sentence(reason)} So let's not do that."),
                    Line(self._someone_else(sp) or sp, self.choose(["Okay, understood.", "Fair enough.", "Makes sense."]))]
        return [Line(nm.speaker, self.choose([f"Change of plan: we're no longer going to {w}. {sentence(reason)}",
                                              f"We're reversing the decision to {w}. {sentence(reason)}"]))]

    # ------------------------------------------------------------ project facts
    def _fact_set(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx = self.ctx
        attr, value = e["attribute"], e.get("value")
        if attr in ("summary", "members", "orgs"):
            return []
        P = ctx.pname(e["subject"]) or e["subject"]
        before = ctx.proj_before.get(e["id"], {})
        old = before.get(attr)
        sp = None if reg in ("note", "recap") else (nm.speaker if reg != "spoken" else self._fact_speaker(e))
        dash = "- " if reg == "note" else ""
        if attr == "target_date":
            new = day_words(value, self.rng.choice([0, 2, 3])) if value else "no date"
            was = f" (was {day_words(old, 3)})" if old else ""
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P}: target date now {new}{was}")]
            return [Line(sp, self.choose([f"The {P} target date is moving to {new}{was}.",
                                          f"Heads up, {P} now targets {new}{was}.",
                                          f"We're pushing {P} to {new}{', from ' + day_words(old, 3) if old else ''}."]))]
        if attr == "phase":
            if value in ("done", "closed", "complete", "collected"):
                return []  # said by the status change
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P}: now in {value}")]
            return [Line(sp, self.choose([f"{P} is moving into {value}.", f"We're now in {value} on {P}.",
                                          f"{P} has moved to the {value} phase."]))]
        if attr == "status":
            words = STATUS_WORDS.get(str(value), (str(value), str(value)))
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P}: {words[0]}")]
            if value == "paused":
                txt = self.choose([f"We're putting {P} on hold for now.", f"{P} is paused until further notice."])
            elif value == "dormant":
                txt = self.choose([f"{P} has gone quiet, treat it as dormant for now.", f"{P} is stalled, nothing moving."])
            elif value == "done":
                txt = self.choose([f"{P} is complete, thanks all.", f"That's {P} done."])
            elif value == "cancelled":
                txt = self.choose([f"{P} is cancelled.", f"We're shelving {P}."])
            else:
                txt = f"{P} is {words[0]}."
            return [Line(sp, txt)]
        if attr == "blocker":
            if value is None:
                txt = f"{dash}{P}: unblocked" if reg in ("note", "recap") else self.choose(
                    [f"The {P} blocker is cleared.", f"{P} is unblocked now."])
                return [Line(sp, txt)]
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P}: blocked, {value}")]
            return [Line(sp, self.choose([f"{P} is blocked: {value}.", f"Blocker on {P}: {value}."]))]
        if attr == "next_step":
            if value is None:
                return []
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P} next step: {lower_first(value)}")]
            return [Line(sp, self.choose([f"Next step on {P}: {lower_first(value)}.",
                                          f"Next up for {P}: {lower_first(value)}."]))]
        if attr == "owner":
            if reg in ("note", "recap"):
                return [Line(None, f"{dash}{P}: owner now {nm.name(value, full=reg == 'recap')}")]
            return [Line(sp, f"{upper_first(nm.name(value, 'subj'))} is now the owner of {P}.")]
        if attr == "sponsor":
            return [Line(sp, f"{dash}{upper_first(nm.name(value, 'subj'))} is sponsoring {P}.")]
        return [Line(sp, f"{dash}{P}: {attr.replace('_', ' ')} is now {value}.")]

    def _fact_speaker(self, e: dict) -> str | None:
        p = self.ctx.project(e["subject"])
        parts = [self.comm.sender, *self.comm.participants]
        owner = (p or {}).get("attrs", {}).get("owner")
        return owner if owner in parts else self.comm.sender

    # ------------------------------------------------------------ entities and structure
    def _entity_create(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        if e["kind"] != "project" or e["entity"] not in self.ctx.projects:
            return []  # people and orgs are introduced where they are first named
        ent = self.ctx.projects[e["entity"]]
        parent = ent["attrs"].get("parent")
        if any(self.ctx.events[a.event]["type"] == "project.split" and e["entity"] in (self.ctx.events[a.event].get("into") or [])
               for a in self.comm.acts):
            return []  # the split sentence introduces it
        desc = _project_desc(ent)
        sp = None if reg in ("note", "recap") else (nm.speaker if reg != "spoken" else self.comm.sender)
        if parent:
            return [Line(sp, f"We're spinning up {ent['name']} as a follow-on to {self.ctx.pname(parent)}. {desc}")]
        return [Line(sp, f"{ent['name']}: {desc}")]

    def _project_split(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx = self.ctx
        src = ctx.pname(e["project"])
        new = [ctx.pname(p) for p in e.get("into") or []]
        moved = [subject_with_keywords(ctx, ctx.loop_create[c]["what"], ctx.loop_create[c].get("keywords") or [])
                 for c in (e.get("moves") or {})]
        mv = f" {upper_first(' and '.join(moved))} {'move' if len(moved) > 1 else 'moves'} over with it." if moved else ""
        sp = None if reg in ("note", "recap") else (nm.speaker if reg != "spoken" else self.comm.sender)
        if reg == "note":
            return [Line(None, f"- split {', '.join(new)} out of {src}.{mv}")]
        return [Line(sp, f"We're splitting {' and '.join(new)} out of {src} as its own project, so it can move at its own pace.{mv}")]

    def _project_merge(self, e: dict, act: Act, nm: Namer, reg: str) -> list[Line]:
        ctx = self.ctx
        srcs = [ctx.pname(p) for p in e.get("projects") or []]
        into = ctx.pname(e["into"])
        if reg == "note":
            return [Line(None, f"- fold {' and '.join(srcs)} into {into}. no separate tracking any more, its open items move across")]
        sp = None if reg == "recap" else nm.speaker
        return [Line(sp, f"We're folding {' and '.join(srcs)} into {into}; its open items move across.")]


def first_person(text: str, first: str) -> str:
    """'Ana wants a wider trial' said by Ana -> 'I want a wider trial'."""
    m = re.match(rf"{re.escape(first)} (\w+)(.*)$", text)
    if not m:
        return text
    verb = {"wants": "want", "needs": "need", "prefers": "prefer", "has": "have", "is": "am",
            "thinks": "think", "asks": "ask"}.get(m.group(1), m.group(1))
    return f"I {verb}{m.group(2)}"


def indirect_closure(what: str, subj: str, debtor: str) -> list[str]:
    """Sentences that show a loop is done only through a side effect (silent closure)."""
    verb = what.split(" ", 1)[0].lower()
    head = " ".join(subj.lower().split()[-2:])
    if any(w in head for w in ("access", "login", "credentials", "tenant", "account")):
        return [f"I'm in now ({subj}), starting on the testing this afternoon.",
                f"Logged in fine, so {subj} is sorted. Starting the walkthrough tomorrow.",
                f"Now that I have {subj} sorted, I can start the dry run."]
    if verb in ("book", "schedule", "set", "line", "hold", "register"):
        return [f"Saw the calendar hold for {subj}, thanks {debtor}.",
                f"Got the invite for {subj}, see you there."]
    if verb in ("fix", "rotate", "deploy", "configure", "provision"):
        return [f"{upper_first(subj)} looks fine on my side now.", f"No more trouble with {subj} since this morning."]
    if verb in ("review", "comment", "check", "approve"):
        return [f"Thanks for the comments on {subj}, folding them in now."]
    return [f"I'm working from {subj} now, it covers what I needed.",
            f"Pulled {subj} into the deck, thanks {debtor}.",
            f"Got {subj}, building on it this week."]


def _project_desc(ent: dict) -> str:
    summary = str(ent["attrs"].get("summary") or "")
    return summary


# ---------------------------------------------------------------- voices
def style_written(text: str, voice: str, keep: list[str]) -> str:
    """Apply a voice to a whole message body. Secrets and links in `keep` are never altered."""
    if voice == "lowercase":
        return lowercase_keep(text, keep)
    if voice == "formal":
        for a, b in (("I'll ", "I will "), ("can't", "cannot"), ("won't", "will not"), ("it's ", "it is "),
                     ("Thx.", "Thank you."), ("FYI ", "For your information, "), ("Heads up", "Please note")):
            text = text.replace(a, b)
        return text
    if voice == "terse":
        for a, b in (("Could you please ", "Can you "), ("Would you be able to ", "Can you "),
                     ("When you get a chance, could you ", "Can you "), (", that would be great", ""),
                     ("Thank you", "Thx")):
            text = text.replace(a, b)
        return text
    if voice == "chatty":
        return re.sub(r"\.(\s|$)", r"!\1", text, count=1)
    return text


def style_chat(text: str, voice: str, keep: list[str], rng: random.Random) -> str:
    """Chat register: shorter, looser punctuation; lowercase voices drop capitals."""
    if voice == "lowercase" or (voice == "terse" and rng.random() < 0.5):
        text = lowercase_keep(text, keep)
        if text.endswith(".") and not text.endswith(".."):
            text = text[:-1]
    elif voice == "chatty":
        if text.endswith(".") and rng.random() < 0.6:
            text = text[:-1] + "!"
        if rng.random() < 0.3:
            text = text + " :)"
    elif voice == "formal":
        text = text.replace("FYI ", "For info, ")
    return text


def mentions_name(ctx: RenderContext, text: str, pid: str) -> bool:
    """Whether a text names a person by any of their names (full, first, nickname, email)."""
    p = ctx.person(pid)
    forms = [p.get("name", ""), p.get("email", "")]
    if p.get("last"):
        forms += [p["first"], p.get("nickname") or ""]
    return any(f and contains_phrase(text, f) for f in forms)


def intro_line(ctx: RenderContext, pid: str, rng: random.Random, register: str) -> str:
    """A sentence that introduces a person not otherwise named in an artifact."""
    name, role = ctx.full(pid), ctx.short_role(pid)
    org = ctx.org_of(pid)
    at = f" at {org['name']}" if org else ""
    if register == "note":
        return f"- {name}: {role}{at}"
    return rng.choice([f"For context, {name} is {_article(role)} {role}{at}.",
                       f"(Adding {name}, {role}{at}, for visibility.)",
                       f"{name} ({role}{at}) is in the loop on this too."])


def org_line(ctx: RenderContext, oid: str, register: str) -> str:
    o = ctx.orgs[oid]
    if register == "note":
        return f"- {o['name']} ({o['short']}): {o['kind']}"
    return f"(This involves {o['name']}.)"


def _article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


# ---------------------------------------------------------------- composing whole artifacts
def act_lines(ctx: RenderContext, comm: Communication, phraser: Phraser, namer: Namer, register: str,
              acts: list[Act] | None = None) -> list[Line]:
    """Lines for a communication's acts, in act order.

    A phase change that comes with a status change for the same project at the same moment is
    said once, by the status line."""
    acts = list(comm.acts if acts is None else acts)
    status_at = {
        (ctx.events[a.event]["subject"], ctx.events[a.event]["t"])
        for a in acts
        if ctx.events[a.event]["type"] == "fact.set" and ctx.events[a.event]["attribute"] == "status"
        and ctx.events[a.event].get("value") != "active"
    }
    out: list[Line] = []
    for a in acts:
        e = ctx.events[a.event]
        if e["type"] == "fact.set" and e["attribute"] == "phase" and (e["subject"], e["t"]) in status_at:
            continue
        out += [ln for ln in phraser.lines(a, namer, register) if ln.text]
    return out


def coverage_gaps(ctx: RenderContext, comm: Communication, text: str, acts: list[Act] | None = None) -> dict:
    """What an artifact's text fails to show of the events it reveals.

    Returns {"people": [...], "orgs": [...], "projects": [...], "loops": [create events]}."""
    gaps: dict[str, list] = {"people": [], "orgs": [], "projects": [], "loops": []}
    for a in comm.acts if acts is None else acts:
        e = ctx.events[a.event]
        if e["type"] == "entity.create":
            ent = e["entity"]
            if e["kind"] == "person":
                if ent != ctx.worker and not mentions_name(ctx, text, ent):
                    gaps["people"].append(ent)
            elif e["kind"] == "org":
                o = ctx.orgs.get(ent)
                if o and not (contains_phrase(text, o["name"]) or contains_phrase(text, o["short"])):
                    gaps["orgs"].append(ent)
            elif e["kind"] == "project":
                if not contains_phrase(text, e["name"]):
                    gaps["projects"].append(ent)
        elif e["type"] in ("commitment.create", "decision.make"):
            if not has_keywords(text, list(e.get("keywords") or [])):
                gaps["loops"].append(e)
    return gaps


def gap_lines(ctx: RenderContext, gaps: dict, rng: random.Random, register: str) -> list[str]:
    """Plain sentences that fill coverage gaps (people, orgs, projects, missing keywords)."""
    out: list[str] = []
    for pid in gaps["people"]:
        out.append(intro_line(ctx, pid, rng, register))
    for oid in gaps["orgs"]:
        out.append(org_line(ctx, oid, register))
    for pid in gaps["projects"]:
        ent = ctx.projects.get(pid)
        if ent:
            out.append(("- " if register == "note" else "") + f"{ent['name']}: {ent['attrs'].get('summary', '')}".strip())
    for e in gaps["loops"]:
        out.append(("- " if register == "note" else "") + f"(Re: {e['what']})")
    return out

