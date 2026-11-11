# Worlds

Status: v0.1. How a world is laid out, built and checked, and how to write one by hand. The file formats themselves are specified in [formats](formats.md); this page does not repeat them.

## What a world is

A **world** is one synthetic episode: a worker, their colleagues, projects, commitments and decisions, and the inputs (emails, chats, transcripts, notes, calendar entries, documents) through which an agent learns about them. It has two halves:

- **Authored files**: the source of truth, written by hand or by `wcb generate`.
  - `world.yaml`: metadata: worker, seed window, episode days, checkpoints ([formats §1.1](formats.md#11-worldyaml)).
  - `world.jsonl`: the hidden, event-sourced timeline ([formats §1.2](formats.md#12-worldjsonl)).
  - `questions.yaml`: question specs per checkpoint ([formats §3.1](formats.md#31-questionsyaml-spec-hidden)).
  - `inbox/<date>/<artifact>`: the input files, one directory per delivery date.
- **Derived files**: written by `wcb world build`. Never edit them by hand.
  - `inbox/<date>/manifest.json`: the agent-visible list of each day's inputs.
  - `gold/`: everything graders need (see below).

Worlds live in `worlds/<split>/<world-id>/` (`pilot`, `dev`, `test`). A small complete example is the test fixture [`tests/fixtures/mini-world`](../tests/fixtures/mini-world).

## Commands

| Command | What it does |
|---|---|
| `wcb world list` | Lists the worlds under `worlds/` with their episode days and checkpoints. |
| `wcb world check <world>` | Runs the consistency checks below. Exit code 1 if there are errors. `--json` prints issues as JSON. |
| `wcb world build <world>...` | Checks each world, then regenerates manifests and `gold/`. Writes nothing for a world whose check finds errors. `--all` builds every world under `worlds/`; `--if-stale` skips worlds whose gold is current. |
| `wcb world stats <world>` | Prints calibration statistics as JSON (the same content as `gold/calibration.json`). |
| `wcb world questions <world> [--checkpoint cp1]` | Prints the built questions, flagging unanswerable ones. |

`<world>` is a path to a world directory or a name under `worlds/`, such as `pilot` or `dev/w01`.

## What `wcb world build` writes

The build is deterministic: rebuilding an unchanged world rewrites identical bytes, so a rebuild shows no diff. Derived files for dates or checkpoints that no longer exist are removed.

| Output | Content |
|---|---|
| `inbox/<date>/manifest.json` | For every delivery date and every episode day: the day's artifacts sorted by `received_at`, then ID ([formats §1.5](formats.md#15-inboxdatemanifestjson)). |
| `gold/state/<date>.json` | The knowable gold state at the end of each date in the seed window that has deliveries, `seed.end`, and every episode day ([formats §2](formats.md#2-gold-state-goldstatedatejson)). |
| `gold/oracle-store/<date>/` | A correct Track A store for `seed.end` and every episode day (see below). The `seed.end` store is the seed store that Track A episodes start from. |
| `gold/questions/<cp>.json` | Questions with gold answers per checkpoint ([formats §3.2](formats.md#32-goldquestionscpjson-hidden)). |
| `gold/calibration.json` | Calibration statistics (see below). |
| `gold/BUILD.json` | Written last, only if the build succeeded: `gold_version` and `sources_sha256`, a digest of `world.yaml`, `world.jsonl`, `questions.yaml` and every inbox file except the manifests. |

Built gold is not committed for worlds under `worlds/` (it is several megabytes per world and fully derived). `wcb run` rebuilds a world when `gold/BUILD.json` is missing, its digest no longer matches the sources, or its `gold_version` differs from `GOLD_VERSION` in [`wcb/world/build.py`](../wcb/world/build.py). Bump `GOLD_VERSION` in any change that alters built gold, and rebuild the committed test fixture with `wcb world build tests/fixtures/mini-world`; a test fails until you do.

Gold state applies only **knowable** events: those revealed by an artifact delivered on or before the date ([formats §1.3](formats.md#13-knowability)). Gold is what an ideal ingestor could know, not the full hidden truth.

### Oracle stores

An oracle store is what a perfect ingestor would have written by the end of a date. It is used as the Track A seed store, and to measure synthesis alone: each checkpoint's questions are also answered against it ([scoring](scoring.md#error-attribution-track-a)). It follows [CONTRACT.md](../contract/CONTRACT.md) and passes `wcb validate store`, except that `CONTRACT.md` itself is added by the runner. The renderer is [`wcb/store/oracle.py`](../wcb/store/oracle.py).

- **Record IDs are stable across dates.** The worker is `people/me`. Other people, orgs and projects use the slug of their canonical name (`people/cora-velez`). A commitment uses the slug of the `what` in its create event, so rewording does not rename it; a decision uses the slug of its `what`. Collisions get `-2`, `-3` in the order the objects become knowable (first reveal date, then world event order), so a suffix never hints at an object that is not knowable yet.
- **People**: one record per knowable person, except minor people (`attrs._minor`). Aliases are the surface forms that some artifact delivered by the date has used (contract rule 12; see `World.form_first_seen`), plus the email address, minus any alias that another knowable entity also uses (two people called Sam both lose "Sam", per contract rule 2, but only once both are knowable, so the seed store does not hint at a namesake who appears later). The body has `## Context`, `## Threads` (the projects shared with the worker, by the [`person_brief` rule](questions.md#person_brief): owner, sponsor or member of a project that is not done, cancelled or merged, or a shared accepted active loop on it; then the person's active loops) and `## Log` (every knowable event involving them, including a hand-off of their loop to someone else).
- **Orgs**: kind, domain, the people who work there, and a log.
- **Projects**: front matter from the project's attributes (status defaults to `active`); `people` is the owner, sponsor, members, everyone on the project's loops and its decision makers. Aliases follow the people rule. `## Current state` is one paragraph: `As of <date of the latest project event>:` followed by the `summary` attribute, status, phase, target date, blocker and next step, with citations. `## Knowledge` lists the sponsor, organizations, members and other durable attributes. `## Log` lists every knowable event on the project.
- **Loops**: one per knowable commitment, with the current owner (debtor), counterparty (creditor), status, due date and acceptance. Evidence has one entry per artifact behind the loop's history; the first uses the loop's `basis`, later ones derive it from the channel (calendar: `scheduled`; transcript, meeting notes: `reported`; email, chat, document: `received`; note: `sent`).
- **Decisions**: loops with `kind: decision`, `status: done` or `reversed`, `outcome`, `decided_on` and `reversed_on`. The first decider is the owner; the others go in `others`.
- **Daily logs**: `logs/<date>.md` for every delivery date so far, one bullet per artifact: `- <id> (<channel>): <title>: <what it revealed>`, or `no change`.

Attributes whose key starts with `_` are never rendered. A fact that is never revealed, such as an unobservable budget, never appears.

### Calibration statistics

`gold/calibration.json` and `wcb world stats` summarize a world against the targets in [plan §1](plan.md#1-what-the-real-store-teaches). Flow counts come from the full timeline; loop shape and status come from the gold state at the last date.

| Section | Content |
|---|---|
| `dates` | Seed window, number of seed delivery days, episode days and checkpoints. |
| `entities` | People (non-minor, minor, and how many appear on loops), orgs, projects. |
| `artifacts` | Totals, channel mix, noise share, mean per episode day, and per-day counts by channel. |
| `commitments` | Commitments created per day and per workday. |
| `loops` | Kind (task, ask, decision), owner (worker, others, or joint when `others` is set), evidence basis, accepted and suggested shares, hard-due share, final status, people and log entries per loop, lifetime in business days (median, p75, p90), loops per project. |
| `events_by_type`, `challenges` | Event counts by type; planted-challenge tags across artifacts. |
| `questions` | Questions by checkpoint, template and type, and the unanswerable share. `null` before the first build. |

## Authoring a world by hand

1. **Plan on paper.** Pick a worker, 10 to 15 people, a few orgs and 3 to 5 projects. Decide the arcs: which commitments are created, transferred, resolved or silently dropped, which decisions are reversed, which facts are superseded, and which planted challenges each arc exercises ([formats §1.4](formats.md#14-planted-challenge-tags)). All content must be synthetic; see [AGENTS.md](../AGENTS.md). Use `.example` email domains.
2. **Write `world.yaml`.** The seed window holds the history before the episode; episode days must be sorted and after `seed.end`; every checkpoint date must be an episode day.
3. **Write `world.jsonl` events in time order.** Create every entity with `entity.create` before anything refers to it. Give each commitment at least two distinctive `keywords` that actually appear in the artifacts that reveal it. Give each non-artifact event a one-line `summary` from the worker's point of view; summaries become oracle-store log lines and change-question gold. If a project's `summary` attribute mentions a date or status that later changes, add a `fact.set` for `summary` at the same time.
4. **Write the artifacts and their `artifact.emit` events.** Put each file at `inbox/<date of received_at>/<artifact id>.<ext>`. List in `reveals` every event the file actually carries, and make sure:
   - an artifact never reveals an event that happens after it is received;
   - an update, resolution, reversal or `fact.set` is never revealed before the event that creates its object;
   - when an artifact reveals a commitment, the people and project it names are revealed by the same or an earlier artifact;
   - every string in `secrets` occurs literally in the file.
5. **Leave some things unobservable on purpose**, such as a budget no input mentions, and ask about them: the gold answer is to abstain.
6. **Write `questions.yaml`** using the templates in [formats §3.1](formats.md#31-questionsyaml-spec-hidden).
7. **Run `wcb world check`, fix every error, then `wcb world build`.** Read the oracle store for the last day: it is the clearest picture of what an agent should end up with. Commit the authored files and the inbox manifests; `gold/` is ignored by git.

## Check reference

`wcb world check` reports these issue codes. Errors block `wcb world build`; warnings do not.

| Code | Severity | Problem |
|---|---|---|
| `meta.file`, `events.file` | error | `world.yaml` or `world.jsonl` is missing or unreadable. |
| `meta.missing` | error | A required `world.yaml` field is missing: `id`, `worker`, `seed.start`, `seed.end`, `episode.days`, `checkpoints`. |
| `meta.seed`, `meta.episode` | error | Seed start after seed end; episode days unsorted, duplicated or not after `seed.end`. |
| `meta.checkpoint` | error | A checkpoint lacks an ID or date, repeats an ID, or its date is not an episode day. |
| `meta.worker` | error | The worker has no person `entity.create`. |
| `meta.timezone` | warning | `timezone` is not of the form `-08:00`. |
| `world.load` | error | `world.jsonl` cannot be loaded at all. |
| `event.id`, `event.duplicate` | error | An event ID is malformed (`e-NNNN`) or used twice. |
| `event.time` | error | `t` or `received_at` is not an ISO datetime with the world's offset. |
| `event.order` | warning | `world.jsonl` is not sorted by `t`. |
| `event.type` | error | Unknown event type. |
| `event.summary` | error | A non-artifact event has no `summary`. |
| `event.field` | error | A required field is missing or has the wrong type, or a value is not allowed (loop kind or status, basis, due date, update keys, contract enums such as `relationship`, org `kind` and project `status`, a project without `owner`). |
| `entity.prefix` | error | An entity ID does not match its kind: `p-` person, `o-` org, `pr-` project. |
| `object.id`, `object.duplicate` | error | A commitment or decision ID is malformed (`c-NNN`, `d-NNN`), or an entity, commitment, decision or artifact is created twice. |
| `ref.missing` | error | A reference (`debtor`, `creditor`, `others`, `project`, `by`, `subject`, `into`, `moves`, `projects`, entity-valued attributes) names nothing, or names the wrong kind of object. |
| `ref.order` | error | An event changes an object before the object is created. |
| `ref.unknowable` | error / warning | A loop or decision names a person or project that is not yet knowable when the loop is (error). For entity-valued attributes such as `org` or `members`, a warning. |
| `reveal.missing` | error | `reveals` names an unknown event or an `artifact.emit`. |
| `reveal.future` | error | An artifact reveals an event that happens after its `received_at`. |
| `reveal.before_create` | error | An update, resolution, reversal, `fact.set`, split or merge is revealed before the event creating its object is knowable; gold would silently drop it. |
| `artifact.channel`, `artifact.prefix` | error | Unknown channel, or the artifact ID prefix does not match the channel. |
| `artifact.path`, `artifact.date` | error | `path` is not `inbox/<date>/<id>.<ext>`, is shared by two artifacts, or its date is not the date of `received_at`. |
| `artifact.missing_file` | error | The file does not exist. |
| `artifact.schedule` | error | Delivered on a date that is neither in the seed window nor an episode day. |
| `artifact.parent` | error | `parent` is not an artifact ID. |
| `artifact.format`, `artifact.challenge` | warning | Unusual file extension for the channel; unknown challenge tag. |
| `inbox.undeclared` | error | A file under `inbox/` is not declared by any `artifact.emit` (manifests excepted). |
| `secret.missing` | error | A `secrets` string does not occur literally in the file. Binary formats are skipped. |
| `keyword.count` | warning | A commitment has fewer than two keywords. |
| `keyword.absent` | warning | A commitment or decision keyword occurs in none of the artifacts that reveal it. Text is read from text files, and from the XML of `.docx`, `.xlsx` and `.pptx` files. |
| `summary.stale` | warning | A project's date attribute changed but its `summary` still mentions the old date. |
| `summary.superseded` | warning | A decision was reversed and replaced the same day by one that changes a count ("three courses" to "four courses"), but at the end of some later day the project's `summary` still states the old count and not the new one. Add a `fact.set` for `summary` when the replacement is made. |
| `question.file`, `question.id`, `question.duplicate` | error | `questions.yaml` is not a list of mappings, or a question ID is missing or repeated. |
| `question.checkpoint`, `question.template`, `question.param` | error | Unknown checkpoint or template, or a parameter names no existing person, project, org, commitment, decision or event (or `since` is not a date). |
| `question.challenge` | warning | Unknown challenge tag on a question. |
| `question.since` | warning | A `project_changes` spec `text` reads as including the `since` day, which gold leaves out: it names that day's weekday ("since Friday" with `since` on a Friday), or says "this week" while `since` falls in the checkpoint's week. Set `since` to the day before. |

The build adds two more after rendering oracle stores: `oracle.secret` (a planted secret reached an oracle store) and `oracle.<code>` (the contract validator found a problem in an oracle store). Both indicate a bug in the world or the renderer. `questions.skipped` (warning) means the question builder was unavailable.
