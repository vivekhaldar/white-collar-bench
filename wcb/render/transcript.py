"""Transcript renderer: WebVTT meeting transcripts (docs/formats.md §1.6).

A recorded meeting becomes a `.vtt` file: a `NOTE` block with the title, date and attendees,
then cues `HH:MM:SS.mmm --> HH:MM:SS.mmm` with `<v Speaker>` voice tags. Like real automatic
transcripts they have small talk, backchannels ("Mm-hmm."), cut-offs and restarts, an
off-topic aside, sometimes a missing opening, a speaker label that drifts mid-meeting
("Ana Ruiz" becomes "Ana's iPhone") and misspelled names in the text.
"""

from __future__ import annotations

import random
import re

from wcb.render.context import RenderContext, Rendered, day_words, time_words
from wcb.render.phrases import (
    BACKCHANNELS,
    CUT_OFFS,
    OFF_TOPIC,
    RESTARTS,
    SMALL_TALK,
    Namer,
    Phraser,
    act_lines,
    coverage_gaps,
    has_keywords,
)
from wcb.util.dates import parse_dt
from wcb.world.comms import Communication

WORDS_PER_SECOND = 2.6
# Discussion that carries no facts: a probing question and an answer that fits it, musings
# (including mild pushback and worry), and a closing round. Nothing here commits anyone to anything.
PROBE_PAIRS = (
    ("How's that looking?", ("Mostly on track.", "It's moving, slowly.", "Okay, I think. Ask me again next week.")),
    ("Any blockers there?", ("Nothing major.", "Honestly, it depends on the other teams.", "Not right now, no.")),
    ("Is that still realistic?", ("I think so, yeah.", "It's tight, but yes.", "Probably. I'd rather not promise more.")),
    ("Did we hear back on that?", ("Not yet, still waiting.", "Not that I've seen.")),
    ("Is that written down anywhere?", ("It's in the shared folder somewhere.", "Not properly, it's mostly in people's heads.")),
    ("Does that work for everyone?", ("Works for me.", "Fine by me.", "I think so, yeah.")),
    ("Sorry, you cut out for a second there.", ("Sorry, bad connection. Same as I said before, really.",
                                                "I'm back. Nothing new, just what I said.")),
    ("Who else needs to know about this?", ("Probably just the people here for now.", "The unit leads, eventually.")),
    ("Is that the same as what we talked about last time?", ("More or less, yeah.", "Roughly, with a few tweaks.")),
    ("Are we sure that's the right order to do things in?", ("Not completely, but it's the best we've got.",
                                                            "I'd push back a little, but fine.")),
)
MUSINGS = ("The main thing is just getting people's time.", "There's a lot of interest, which is good.",
           "The documentation is still a bit thin.", "It's mostly waiting on other teams at this point.",
           "People seem positive about it so far.", "We should keep an eye on scope creep.",
           "The feedback from the last session was pretty mixed.", "Last time this took longer than we thought.",
           "I'm not sure everyone's read the latest version yet.",
           "My concern is mostly the timeline, to be honest.", "I'm a bit worried we're overcommitting again.",
           "Unfortunately the people who'd use it aren't in this room.",
           "I'm not sure I agree, but let's see how it lands.", "Finance will have views on this, I expect.",
           "We said the same thing a month ago.", "I'd rather we didn't escalate this yet.",
           "It's a lot of process for a pilot.", "Some of the units are going to see this as us overreaching.")
ROUNDS = ("Nothing from me this week.", "Nothing new from my side.", "All quiet on my end.",
          "Just heads-down on the usual stuff.", "Nothing to flag.", "I'm good, thanks.")


# V1 banks above remain available for replay of the published inboxes. V2 filler
# can discuss the conversation itself but cannot resolve a task, deadline or blocker.
NEUTRAL_PROBES = (
    ("Could you repeat that?", ("Sure, give me a moment.", "Of course.")),
    ("Can everyone hear me?", ("Yes, I can hear you.", "Loud and clear.")),
    ("Would you like a minute?", ("Just a second, thanks.", "Thanks, go ahead.")),
    ("Shall I pause here?", ("One moment, please.", "Thanks, carry on.")),
    ("Was someone else speaking?", ("Go ahead.", "Sorry, I was on mute.")),
)
NEUTRAL_ASIDES = ("Give me a moment to write that down.", "Thanks for walking through that.",
                  "Hang on, my screen went dark.", "I missed the last few words.",
                  "Let me turn my microphone back on.")
NEUTRAL_ROUND = ("Nothing to add from me.", "Thanks for the update.", "Pass for now.")


class _Bag:
    """Draws from a phrase bank without replacement until it runs out, then starts over."""

    def __init__(self, items, rng: random.Random):
        self.items = list(items)
        self.rng = rng
        self.left: list = []

    def draw(self):
        if not self.left:
            self.left = list(self.items)
            self.rng.shuffle(self.left)
        return self.left.pop()


def participants(ctx: RenderContext, comm: Communication) -> list[str]:
    return [p for p in dict.fromkeys([comm.sender, *comm.participants]) if p]


def attendee_list(ctx: RenderContext, people: list[str]) -> str:
    out = []
    for p in people:
        org = ctx.org_of(p)
        if org and org["role"] not in ("central", "umbrella"):
            out.append(f"{ctx.full(p)} ({org['name']})")
        else:
            out.append(ctx.full(p))
    return ", ".join(out)


def mangle(name: str, rng: random.Random) -> str:
    """How speech recognition misspells a name: 'Thandiwe' -> 'Tandiwe', 'Svetlana' -> 'Svet Lana'."""
    rules = [("th", "t"), ("ph", "f"), ("q", "k"), ("ie", "ee"), ("y", "i"), ("c", "k"), ("ei", "ay"),
             ("ou", "oo"), ("sh", "ch"), ("v", "b"), ("j", "g"), ("x", "ks")]
    low = name.lower()
    rng.shuffle(rules)
    for a, b in rules:
        if a in low[1:]:
            i = low.index(a, 1)
            out = name[:i] + b + name[i + len(a):]
            return out
    if len(name) >= 7:
        k = len(name) // 2
        return name[:k] + " " + name[k:].lower()
    for end, rep in (("i", "y"), ("a", "ah"), ("o", "oh"), ("e", "ey"), ("y", "ie"), ("n", "nne"), ("l", "ll")):
        if low.endswith(end):
            return name[: -len(end)] + rep
    return name + "e"


def render(ctx: RenderContext, comm: Communication, aid: str) -> Rendered:
    rng = ctx.rng(aid)
    people = participants(ctx, comm)
    start = parse_dt(comm.extra.get("start") or comm.t)
    end = parse_dt(comm.t)
    duration = max(300.0, (end - start).total_seconds())
    namer = Namer(ctx, comm, None, [])
    ph = Phraser(ctx, comm, rng)
    act_cues = act_lines(ctx, comm, ph, namer, "spoken")
    organizer = comm.sender or people[0]

    def other_than(pid: str) -> str:
        opts = [p for p in people if p != pid]
        return rng.choice(opts) if opts else pid

    # ---------------------------------------------------------------- the script
    segments: list[list[tuple[str, str, str | None]]] = []  # (speaker, text, act)
    missing_opening = rng.random() < 0.22
    if missing_opening:
        segments.append([(rng.choice(people), rng.choice([
            "—and that's basically where we landed last time.", "—sorry, it says recording now.",
            "—so yeah, that's the context.", "—no, the other one, the shared doc."]), None)])
    else:
        a, b = rng.sample(SMALL_TALK, 1)[0]
        p1 = rng.choice(people)
        segments.append([(p1, a, None), (other_than(p1), b, None)])
        segments.append([(organizer, rng.choice(["Okay, let's get started.", "Right, shall we start?",
                                                  "Let's get going, we've got a lot to cover.",
                                                  "Okay, I think we have everyone."]), None)])
    proj = ctx.pname(comm.project)
    if proj and rng.random() < 0.6:
        segments[-1].append((organizer, rng.choice([f"Main thing today is {proj}.", f"Mostly {proj} updates today.",
                                                    f"Let's start with {proj}."]), None))
    legacy = ctx.plan["generator"]["version"] == 1
    backs = _Bag(BACKCHANNELS, rng)
    probes = _Bag(PROBE_PAIRS if legacy else NEUTRAL_PROBES, rng)
    musings = _Bag(MUSINGS if legacy else NEUTRAL_ASIDES, rng)
    multi = len(people) > 1

    def backchannel(after: str, seg: list) -> None:
        """A few short acknowledgements, each from someone other than the previous speaker."""
        prev = after
        for _ in range(rng.choice([1, 1, 2, 2, 3])):
            who = other_than(prev) if prev != after else other_than(after)
            seg.append((who, backs.draw(), None))
            prev = who

    # Group the act lines: everything one act says (an ask and its answer) stays together, and
    # discussion filler only follows once the act is complete.
    groups: list[list] = []
    for ln in act_cues:
        if groups and groups[-1][0].act == ln.act:
            groups[-1].append(ln)
        else:
            groups.append([ln])
    actors: set[str] = set()
    for grp in groups:
        seg: list[tuple[str, str, str | None]] = []
        first_sp = grp[0].speaker if grp[0].speaker in people else organizer
        if rng.random() < 0.1 and multi:
            seg.append((first_sp, rng.choice(CUT_OFFS), None))
            seg.append((other_than(first_sp), rng.choice(RESTARTS), None))
        for ln in grp:
            sp = ln.speaker if ln.speaker in people else organizer
            seg.append((sp, ln.text, ln.act))
            actors.add(sp)
        last = seg[-1][0]
        if multi and rng.random() < 0.9:
            backchannel(last, seg)
        if multi and rng.random() < 0.55:
            q, answers = probes.draw()
            asker = other_than(last)
            seg.append((asker, q, None))
            seg.append((last, rng.choice(answers), None))
            if rng.random() < 0.5:
                backchannel(last, seg)
        for _ in range(rng.choice([0, 1, 1, 2])):
            m = rng.choice(people)
            seg.append((m, musings.draw(), None))
            if multi and rng.random() < 0.9:
                backchannel(m, seg)
        segments.append(seg)
    quiet = [p for p in people if p not in actors and p != organizer]
    if len(people) > 2 and len(quiet) >= 2 and rng.random() < 0.6:
        rbag = _Bag(ROUNDS if legacy else NEUTRAL_ROUND, rng)
        rounds = []
        for p in rng.sample(quiet, min(len(quiet), rng.randint(2, 4))):
            rounds.append((p, rbag.draw(), None))
            if rng.random() < 0.7:
                rounds.append((other_than(p), backs.draw(), None))
        rounds.insert(0, (organizer, rng.choice(["Anything else from anyone?", "Quick round, anything to flag?",
                                                 "Any other updates?"]), None))
        segments.append(rounds)
    gaps = coverage_gaps(ctx, comm, " ".join(t for seg in segments for _, t, _ in seg) + " " + attendee_list(ctx, people))
    for pid in gaps["people"]:
        segments.append([(organizer, f"For context, {ctx.full(pid)} is {ctx.short_role(pid)}"
                          f"{' at ' + ctx.org_of(pid)['name'] if ctx.org_of(pid) else ''}.", None)])
    for oid in gaps["orgs"]:
        segments.append([(organizer, f"This one involves {ctx.orgs[oid]['name']} as well.", None)])
    for pid in gaps["projects"]:
        ent = ctx.projects[pid]
        segments.append([(organizer, f"Quick intro to {ent['name']}: {ent['attrs'].get('summary', '')}", None)])
    for e in gaps["loops"]:
        segments.append([(organizer, f"Just to note it down: {e['what']}.", None)])
    if rng.random() < 0.3 and len(segments) > 2 and len(people) > 2:
        sp = rng.choice(people)
        segments.insert(rng.randint(2, len(segments)), [(sp, rng.choice(OFF_TOPIC), None),
                                                       (other_than(sp), rng.choice(["Ha, yes.", "No idea.", "I think so.", "Mm."]), None)])
    if not act_cues and multi:
        # A meeting where nothing new came up still has some talk.
        seg = []
        for _ in range(rng.randint(2, 4)):
            m = rng.choice(people)
            seg.append((m, musings.draw(), None))
            backchannel(m, seg)
        segments.insert(min(len(segments), 2), seg)
    closers = (["Okay, I think that's it. Thanks everyone.", "Thanks all, talk soon.", "Great, let's wrap there.",
                "Okay, thanks, I'll let you all go."] if len(people) > 2 else
               ["Okay, I think that's it. Thanks.", "Great, talk next week.", "Cool, let's wrap there."])
    segments.append([(organizer, rng.choice(closers), None),
                     (other_than(organizer), rng.choice(["Thanks!", "Bye.", "Cheers.", "Thanks, bye."]), None)])

    # ---------------------------------------------------------------- names: mangling and drift
    keywords_by_act = {a.event: list(ctx.events[a.event].get("keywords") or []) for a in comm.acts}
    mangled: dict[str, str] = {}
    firsts = sorted({ctx.first(p) for p in ctx.people if ctx.person(p).get("last")},
                    key=lambda s: (-len(s), s))  # ties by name: set order varies by process
    for seg in segments:
        for i, (sp, text, act) in enumerate(seg):
            if rng.random() > 0.35:
                continue
            for f in firsts:
                if re.search(rf"\b{re.escape(f)}\b", text):
                    m = mangled.setdefault(f, mangle(f, rng))
                    new = re.sub(rf"\b{re.escape(f)}\b", m, text, count=1)
                    if act is None or has_keywords(new, keywords_by_act.get(act, [])):
                        seg[i] = (sp, new, act)
                    break
    ctx.mangled.setdefault(comm.id, {}).update(mangled)
    labels = {p: ctx.full(p) for p in people}
    drift_from = None
    drifter = None
    if len(people) >= 3 and rng.random() < 0.45:
        drifter = rng.choice([p for p in people if p != organizer])
        drift_from = rng.randint(2, max(2, len(segments) - 1))
        p = ctx.person(drifter)
        drift_label = rng.choice([f"{ctx.full(drifter)} (Guest)", f"{p.get('first', 'Guest')}'s iPhone",
                                  f"{p.get('first', '')} {p.get('last', '')[:1]}.".strip()])

    # ---------------------------------------------------------------- timing
    cues: list[tuple[float, float, str, str]] = []
    natural = sum(_dur(t) + 0.8 for seg in segments for _, t, _ in seg)
    slack = max(0.0, duration * rng.uniform(0.75, 0.92) - natural)
    jumps = [rng.random() for _ in segments]
    total_j = sum(jumps) or 1.0
    t = rng.uniform(120, 300) if missing_opening else rng.uniform(1, 6)
    for k, seg in enumerate(segments):
        if k:
            t += slack * jumps[k] / total_j
        for sp, text, _act in seg:
            d = _dur(text)
            label = labels[sp] if sp in labels else ctx.full(sp)
            if drifter is not None and sp == drifter and drift_from is not None and k >= drift_from:
                label = drift_label
            cues.append((t, t + d, label, text))
            t += d + rng.uniform(0.2, 1.4)
    title = comm.subject or "Meeting"
    date = day_words(comm.t[:10], 0) + " " + comm.t[:4]
    head = ["WEBVTT", "", "NOTE",
            f"Meeting: {title}",
            f"Date: {date}, {time_words(comm.extra.get('start') or comm.t)} to {time_words(comm.t)}",
            f"Attendees: {attendee_list(ctx, people)}",
            "Transcript generated automatically. Speaker names and spellings may be inaccurate.", ""]
    body = []
    for i, (a, b, label, text) in enumerate(cues, 1):
        body += [str(i), f"{_ts(a)} --> {_ts(b)}", f"<v {label}>{text}", ""]
    content = "\n".join(head + body)
    return Rendered(aid, ".vtt", f"{title} (transcript)", content=content, text=content)


def _dur(text: str) -> float:
    return max(1.0, len(text.split()) / WORDS_PER_SECOND)


def _ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


