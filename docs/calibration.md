# Calibration targets

Status: v1. These targets steer the [world generator](generator.md) and the hand-authored pilot. They extend the rounded aggregates in [plan §1](plan.md#1-what-the-real-store-teaches) with a second pattern-level review of a private, agent-maintained knowledge store.

Only aggregate statistics and abstract shapes appear here. The source contains no content that is copied, paraphrased or disguised (see [AGENTS.md](../AGENTS.md)). Figures are rounded, and the setting of every benchmark world is invented.

## Scale and flow per weekday

| Quantity | Target |
|---|---|
| Inputs per weekday | 15–20 artifacts in the benchmark, scaled down from about 30 emails, about 100 chat messages and 4–6 meetings in real life |
| Email that is noise | about 50% (newsletters, notifications, FYI threads) |
| Evidence by channel | chat about 45%, email about 30%, meetings about 15%, other about 10% |
| Meetings per weekday | 2–5, of which 1–3 are recorded |
| New loops per weekday | 5–9 on average, rising over the period |
| Weekend | about one third of weekday volume, never zero |
| Heaviest days | Monday and Tuesday |

## Loops

| Field | Distribution |
|---|---|
| Kind | task about 56%, ask about 41%, decision about 3% |
| Owner | worker about 45%, others about 48%, joint about 7% |
| Status at a snapshot | done about 42%, waiting 28%, open 26%, dropped 4%, blocked 1% |
| Basis | reported about 47%, received 31%, sent 19%, scheduled 2%, inferred under 1% |
| Suggested, not yet endorsed | about 11% (two thirds are incoming asks) |
| Hard due date | about 8% |
| People per loop | median 2, rarely more than 5 |

Coupling: `waiting` loops are almost always owed by others; `open` loops are mostly owed by the worker.

**Lifetimes are bimodal.** Closed loops have a median lifetime of about 1 business day, and many open and close on the same day; the 90th percentile is about 2 weeks. Live loops have a median age of about 3 weeks. The median time since the last evidence is about 10 days, with a stale tail of about 7 weeks.

**Transitions.** Relative frequencies:

| Transition | Relative frequency |
|---|---|
| open → done | 100 |
| waiting → done | 45 |
| open ↔ waiting | 25 |
| → dropped | 15 |
| owner transfer | 15 |
| task ↔ ask | 12 |
| reopen | 2 |

Endorsements of suggested loops are common, at about 30 per 100 open → done.

**Origins of commitments:**

| Origin | Share |
|---|---|
| Explicit request | 45% |
| Agreement in a meeting | 15% |
| Accepted proposal | 15% |
| Follow-on from a decision | 10% |
| Offer | 8% |
| Explicit promise | 7% |
| Hedged intent | 7% |
| Inferred owner | 5% |
| Worker says "track this" | 5% |

**Drop reasons**, most common first:

1. folded into an umbrella loop;
2. superseded by a decision;
3. project closed;
4. mistaken or duplicate;
5. obsolete.

## Projects

- **Skew.** One flagship holds about 35% of loops and the top two hold about 50%. The median project has about 15 loops and 5–12 people; the flagship has 40–70 people.
- **Activity.** In a typical week about two thirds of projects see activity. The flagship's weekly activity can grow tenfold over the period; other projects show one or two bursts separated by quiet weeks.
- **Meetings.** About 40% of meetings belong to no project and 25% to two or more.
- **Status lag.** Status labels lag reality, and quiet projects stay labelled active.
- **Restructuring.** Splits, merges, and closures that spawn successors happen several times a quarter.
- **Naming churn.** Projects carry code names, unit acronyms, repository names and working names that later become final names.

**Archetypes**, abstract shapes only:

- flagship pilot build with gates
- unit discovery
- pivoting discovery
- background advisory that fades
- portfolio-wide supplier negotiation
- event preparation that spawns a successor
- internal product incubation
- economics or measurement model
- shared-platform blocker hub
- strategic framework that carves out sub-efforts
- hiring pipeline that reopens
- education programme revived by one booking
- placeholder
- stalled discovery cited only as evidence
- adjacent spin-off
- reference-architecture hub
- vendor-pair evaluation
- operational incident
- peer review exchange
- relationship thread
- delegated asks

**Complexity drivers:**

- **Parallel sub-threads.** The flagship can run about 15 at once: data, hosting, identity, security package, privacy, test plans, evaluation, component approval, cost, staffing and load testing.
- **Hub-and-spoke dependencies.**
- **Competing stakeholder interests.** A unit prefers to build internally, security forbids production data, finance ties approval to who pays, and legal limits sharing with vendors.
- **Phase triggers.** Phases change when a held meeting replaces a scheduled one, a document arrives, a leadership directive narrows scope, a new hire picks up a dormant thread, a recurring meeting is cancelled repeatedly, an unsigned agreement gates access, a security reviewer pauses a step, or the worker returns from an absence.

## Cast

- **Shape.** A small central team and several semi-autonomous units of varying receptiveness, plus vendors and partners, assistants and schedulers, a shared mailbox that behaves like a person, candidates and outside researchers.
- **Concentration.** One collaborator is on about 35% of loops and the next three on 13–15% each. About 12 people appear in 30 or more loops; about 45% of the cast appears in 5 or fewer.
- **Direction.** The worker waits on others in about 40% of loops, owns about 45%, and receives inbound asks in about 10%. With the sponsor, most loops are assigned to the worker; with connectors, most are the worker's asks.
- **Surface forms.** Bare first names outnumber full names by 20–40 to 1. Core people have 3–6 surface forms.
- **Ambiguity.** Plant first-name collisions across organizations, homophones spelled differently, transcription-mangled names, role changes (a candidate becomes a peer, temporary cover becomes permanent), and people known only by first name until later.
- **Cadences.** A weekly leads call, an every-other-week 1:1 with the main collaborator, daily build standups for the flagship, and a fortnightly cross-unit forum.

## Inputs

**Meeting coverage:**

| Coverage | Share |
|---|---|
| Full transcript | 55% |
| Synthesis or recap only | 25% |
| Worker-supplied notes or a spoken debrief only | 15% |

One meeting can yield several partly disagreeing artifacts, such as a recording, an organizer's AI recap and a later correction.

**Transcript defects:**

- missing openings;
- fragment restarts;
- speaker labels that drift;
- mangled names that recaps repeat;
- one recording spanning two meetings.

About 35% of segments are backchannels and 5–15% of airtime is small talk.

**Speech:**

- Commitments are first-person, in passing and undated. "I'll" is about three times as common as any time anchor.
- Collective "we'll" has no named owner, and hedges are common.
- Decisions are implied by assent. Seniors state preferences that are not decisions, and many items are deferred to another channel.
- Explicit action-item lists are rare.

**Email and chat:**

- More than half of emails are replies, and most carry quoted history, some 5–18 levels deep.
- Chat threads have 4–19 replies, and edits after posting change facts.
- Attachments are often missing.

**The worker's own writing:**

- terse lowercase chat;
- spoken brain-dumps after unrecorded meetings;
- pasted bullet outlines;
- one-line directives;
- relayed second-hand feedback.

**Scatter.** A single commitment typically spreads over 3–6 channels and 2–10 days: a verbal acceptance with a vague deadline, an unsent draft, second-hand criticism with a new deadline, delivery by a chat post, and a third party's correction the next day.

## Failure modes to plant

Ranked by observed frequency and severity:

1. **Evidence inflation.** A reported state ("it's deployed") is recorded as fact, or a broadcast is taken as proof of individual receipt.
2. **Draft vs sent.** Unsent drafts, failed sends that left duplicate drafts, and sends claimed but never verified.
3. **Calendar as occurrence.** An acceptance later superseded by a tentative reply, attendance unknown, call metadata without content.
4. **Misattribution.** Someone else's promise is put on the worker's list, generic transcript speakers create phantom dependencies, misheard names.
5. **Wrong or over-broad closure.** A two-part promise is closed when one part is done, or a project-closure cascade sweeps up live loops.
6. **Duplicates.** Narrower follow-ups, re-asked questions, and recurring period reminders that should be new loops rather than reopened ones.
7. **Stale status.** Project paragraphs diverge from loop status.
8. **Invisible loops.** Next steps found but never surfaced, or answers that show only a sample.
9. **Invented tasks.** Reply tasks created for questions already answered.
10. **Instruction injection.** Source content treated as instructions to the agent.

Also plant:

- a joke deadline corrected in the same exchange;
- relative and cross-timezone dates;
- totals inside one document that disagree;
- supersession chains;
- a change discussed in chat that never happened on the tracker;
- a delegate during an absence;
- recurring obligations;
- consolidation, where merged loops are not done;
- an evidence upgrade with no status change;
- a rejected spec rewritten with its deadline superseded.

## Questions workers actually ask

Weight checkpoint queries toward the most common categories:

- per-person ledgers (what each person owes and is owed);
- weekly review of what changed and what is due;
- top-N priorities with reasons;
- status and briefs for a project or person, including meeting prep and return-from-absence briefs;
- "did we make or share X";
- manager updates focused on deliverables and the next 2–3 milestones.

Ingestion requests are the most common write workload overall.
