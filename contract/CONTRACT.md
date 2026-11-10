# Store contract (Track A)

Contract version: 1.0

You maintain a **knowledge store** for one person, called **the worker**. The store is a directory of Markdown files that records the worker's projects, open loops (tasks, asks and decisions), people and organizations, plus a daily log of what changed.

This contract says **what** the store must contain and which rules it must follow. It does not prescribe **how** you work. Use any procedure, tools or intermediate files you like.

## 1. Layout

```text
<store root>/
  CONTRACT.md        this file; do not edit
  people/            one record per person; people/me.md is the worker
  orgs/              one record per organization or team
  projects/          one record per project
  loops/             one record per loop (task, ask or decision)
  logs/              one append-only file per day: logs/YYYY-MM-DD.md
  sources/           optional: archived copies of inputs, named by artifact ID
  notes/             optional: anything else you find useful
  inbox/             inputs for the current session only; do not edit
```

During an ingestion session, new inputs are in `inbox/<date>/`, described by `inbox/<date>/manifest.json`. Each input has a stable **artifact ID** such as `em-0193`. The inbox is removed after the session. Copy anything you need later into the store, for example under `sources/`.

## 2. Records

Every file in `people/`, `orgs/`, `projects/`, `loops/` and `logs/` is a **record**: a Markdown file with YAML front matter.

```markdown
---
id: people/marisol-teague
type: person
name: Marisol Teague
aliases: [Dana, M. Teague, marisol.teague@brenwick.example]
updated: 2027-03-02
---
Body in Markdown.
```

- **ID.** A record's `id` is its path relative to the store root, without `.md`. For example, `people/marisol-teague` lives at `people/marisol-teague.md`.
- **File names.** File names are lowercase slugs matching `[a-z0-9][a-z0-9-]*`.
- **Links.** Fields that refer to another record hold that record's ID, for example `owner: people/me`. Links must point to records that exist. In body text, link with the ID in double brackets, for example `[[projects/thistledown]]`.
- **Dates.** Use absolute dates in `YYYY-MM-DD` form. Resolve relative dates such as "next Tuesday" against the date of the input that contains them.
- **Citations.** Cite inputs by artifact ID in square brackets, for example `[src: em-0193]` or `[src: em-0193, mt-0057]`.

### 2.1 Person: `people/<slug>.md`

| Field | Required | Value |
|---|---|---|
| `id`, `type: person` | yes | |
| `name` | yes | Full name as best known |
| `aliases` | yes | Every other way this person is referred to: first name, nickname, initials, email address, chat handle, role phrase. May be empty. |
| `updated` | yes | Date of the last change |
| `org` | no | Organization ID, for example `orgs/brenwick` |
| `role` | no | Job title or role |
| `email` | no | Email address, or a list of addresses |
| `relationship` | no | Relationship to the worker: `manager`, `report`, `peer`, `stakeholder`, `executive`, `assistant`, `vendor`, `partner`, `candidate`, `advisor` or `other` |

Body sections, in this order:

- `## Context`: durable knowledge about the person.
- `## Threads`: the projects and loops currently shared with the worker, as links.
- `## Log`: dated entries, append-only, newest last.

The worker's own record is `people/me.md` with `id: people/me`. Its `name` is the worker's real name.

### 2.2 Organization: `orgs/<slug>.md`

| Field | Required | Value |
|---|---|---|
| `id`, `type: org` | yes | |
| `name` | yes | |
| `aliases` | yes | Other names, abbreviations and email domains. May be empty. |
| `updated` | yes | |
| `kind` | no | `internal` (a team or unit inside the worker's company), `vendor`, `customer`, `partner` or `other` |
| `domain` | no | Email domain |

### 2.3 Project: `projects/<slug>.md`

| Field | Required | Value |
|---|---|---|
| `id`, `type: project` | yes | |
| `name` | yes | |
| `aliases` | yes | Code names, informal names and abbreviations. May be empty. |
| `status` | yes | `active`, `paused`, `dormant`, `done`, `cancelled` or `merged` |
| `owner` | yes | Person ID of the accountable owner |
| `updated` | yes | |
| `people` | no | Person IDs of people involved |
| `orgs` | no | Organization IDs involved |
| `target_date` | no | Current target or deadline |
| `parent` | no | Project ID this project was split from |
| `split_into` | no | Project IDs this project was split into |
| `merged_into` | no | Project ID this project was merged into; requires `status: merged` |

Body sections, in this order:

- `## Current state`: **exactly one paragraph** beginning `As of YYYY-MM-DD:`. It states the current status, the latest change, blockers, and the next dated step, with citations. When the state changes, **replace** this paragraph and move the superseded state into the log.
- `## Knowledge`: durable context such as goals, constraints, history and background. Not the current status.
- `## Log`: dated bullets, append-only, newest last: `- YYYY-MM-DD: what happened [src: em-0193]`.

### 2.4 Loop: `loops/<slug>.md`

A **loop** is anything still to be done or decided, or already done or decided, that involves the worker:

- `task`: something to be done.
- `ask`: a request someone made of someone else.
- `decision`: a choice that is pending or has been made.

| Field | Required | Value |
|---|---|---|
| `id`, `type: loop` | yes | |
| `kind` | yes | `task`, `ask` or `decision` |
| `title` | yes | Short imperative description, for example "Send Dana the revised vendor scorecard" |
| `owner` | yes | Person ID of who must act. For a decision, who decides. |
| `counterparty` | yes | Person ID of who the loop is owed to or who asked for it. `null` is allowed only for decisions. |
| `status` | yes | See below |
| `accepted` | yes | `true` if the loop is a real commitment; `false` if it is only suggested (see rule 7) |
| `evidence` | yes | At least one evidence entry (see below) |
| `created`, `updated` | yes | Dates |
| `project` | no | Project ID |
| `due` | no | Hard due date, `YYYY-MM-DD` |
| `others` | no | Person IDs of other people involved |
| `outcome` | decision only | What was decided |
| `decided_on`, `reversed_on` | decision only | Dates |

**Status** for tasks and asks:

| Status | Meaning |
|---|---|
| `open` | The owner still has to act. |
| `waiting` | The owner has acted, or cannot act until someone else responds or approves. |
| `blocked` | Cannot proceed until an obstacle is removed. |
| `done` | Fulfilled, with evidence that it happened. |
| `dropped` | Will not be done: explicitly cancelled, declined or made moot. |

Decisions use `open` (pending), `done` (decided; set `outcome` and `decided_on`), `reversed` (a decision that was later undone; set `reversed_on`) or `dropped` (no longer needs deciding).

**Evidence** is a list of entries, one per source that created or changed the loop:

```yaml
evidence:
  - {source: em-0193, basis: received, date: 2027-03-01}
  - {source: mt-0057, basis: reported, date: 2027-03-03, note: "Dana confirmed receipt"}
```

`basis` is one of:

- `sent`: the worker sent it.
- `received`: the worker received it directly.
- `reported`: someone reported it, for example in a meeting or status update.
- `scheduled`: a calendar entry.
- `inferred`: you inferred it without a direct statement.

Body: a one-line description, then `## Log` with dated bullets, newest last.

### 2.5 Daily log: `logs/YYYY-MM-DD.md`

| Field | Required | Value |
|---|---|---|
| `id` (`logs/YYYY-MM-DD`), `type: log` | yes | |
| `date` | yes | The session date |

Body: one bullet per input processed that day: `- em-0193 (email): what changed, with links to affected records`. Inputs that changed nothing still get a bullet, for example `- em-0201 (email): newsletter, no change`. A day's log is written during that day's session and never rewritten afterwards.

## 3. Rules

1. **One record per real entity.** Before creating a person, organization or project, check whether it already exists under another name: a nickname, an email handle, a code name or a role phrase such as "the new PM". If it exists, add the new name to `aliases` instead of creating a duplicate.
2. **Never merge different entities.** Two different people can share a first name. Keep them as separate records with distinct slugs, such as `people/sam-reyes` and `people/sam-patel`, and list only the aliases that unambiguously belong to each.
3. **Current state lives in one place.** A record's front matter and its `Current state` section, for projects, hold the current state. Logs are append-only history. Do not leave a superseded value presented as current anywhere.
4. **Evidence for every change.** Every loop cites at least one input. A status change adds an evidence entry for the input that justifies it.
5. **A calendar entry is not an occurrence.** A scheduled or accepted meeting does not prove that it happened or that it produced an outcome. Do not mark a loop `done` because a meeting about it was on the calendar.
6. **Drafts are not sent.** A draft that the worker has not sent creates no commitment and resolves nothing.
7. **Endorsement.** A loop that someone else suggests for the worker, or that you infer, gets `accepted: false` until the worker commits to it. The worker commits by agreeing ("I'll do it", "yes, go ahead"), by asking for it, or by taking it on in their own notes. Loops the worker owes because they explicitly promised them, and asks the worker makes of others, are `accepted: true`.
8. **The worker's notes are authoritative.** Inputs written by the worker, such as notes and directives, are instructions about the state of their work, for example "drop the beta" or "go with option 1".
9. **Supersession and corrections.** When a later input changes or corrects an earlier one, update the current state and log the change. Resolve conflicts in favour of the most recent reliable statement.
10. **Restructuring.** When a project splits or two projects merge, set `split_into`, `parent` or `merged_into` accordingly and move affected loops by updating their `project` field.
11. **Privacy.** Never write credentials, passwords, API keys, one-time codes, meeting join links, dial-in numbers or meeting passcodes anywhere in the store, including `sources/` and `notes/`. Write `[redacted]` instead.
12. **No invention.** Every recorded fact must trace to an input. Leave a field empty rather than guess.
13. **Noise.** Newsletters, social chatter and unrelated threads need only a daily-log bullet.

## 4. Validation

The benchmark validates stores with `wcb validate store <dir>`, which checks:

- front matter against the JSON Schemas in the benchmark's `contract/schemas/`;
- that each `id` matches its path and each link resolves;
- that each project's `Current state` is a single paragraph beginning `As of`;
- privacy patterns such as join links and passcodes.

Stores are also compared against hidden ground truth for duplicates, wrong merges, stale state, missing loops and unsupported claims.
