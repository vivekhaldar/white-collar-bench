# Data formats

Status: v0.1. This is the reference for every file the benchmark reads or writes. See [design](design.md) for concepts and [scoring](scoring.md) for how answers are graded.

Conventions:

- Dates are ISO strings: `YYYY-MM-DD`. Times are ISO 8601 with an offset: `2027-03-01T09:14:00-08:00`.
- A **date's end** is `YYYY-MM-DDT23:59:59` in the world's time zone.
- IDs are lowercase ASCII. World entity IDs use a kind prefix: `p-` person, `o-` organization, `pr-` project. Commitments are `c-NNN`, decisions `d-NNN`, events `e-NNNN`.
- Artifact IDs are `<channel prefix>-NNNN`. The prefix tells you the channel:

| Prefix | Channel | File formats |
|---|---|---|
| `em` | `email` | `.eml` (RFC 5322, plain-text body, quoted replies) |
| `ch` | `chat` | `.json` chat thread export |
| `mt` | `transcript` | `.vtt` (WebVTT with `<v Speaker>` voice tags) or `.txt` |
| `mn` | `meeting_notes` | `.md` |
| `dc` | `document` | `.md`, `.docx`, `.xlsx`, `.pdf` |
| `nt` | `note` | `.md` (the worker's own notes and directives) |
| `ca` | `calendar` | `.ics` (iCalendar invites, updates, cancellations, responses) |

## 1. World directory

```text
worlds/<split>/<world-id>/
  world.yaml              episode metadata (public)
  world.jsonl             event-sourced ground truth (hidden from agents)
  questions.yaml          question specs (hidden)
  inbox/<date>/           input artifacts, one directory per delivery date
    manifest.json         agent-visible list of the day's artifacts
    em-0001.eml ...
  gold/                   built by `wcb world build` (hidden)
    state/<date>.json     knowable state at the end of each date
    oracle-store/<date>/  a correct Track A store for each date
    questions/<cp>.json   questions with gold answers per checkpoint
    calibration.json      summary statistics of the world
```

The world is built from `world.yaml`, `world.jsonl`, `questions.yaml` and the artifact files. Everything under `gold/` and every `manifest.json` is derived by `wcb world build` and must not be edited by hand.

### 1.1 `world.yaml`

```yaml
id: pilot                       # unique world ID
title: "Pilot world: one week at a regional logistics company"
version: 1
split: pilot                    # pilot | dev | test
worker: p-rowan-achterberg      # entity ID of the worker
timezone: "-08:00"
seed:                           # history before the episode
  start: 2027-02-15
  end: 2027-02-26
episode:                        # days with an ingestion session, in order
  days: [2027-03-01, 2027-03-02, 2027-03-03, 2027-03-04, 2027-03-05]
checkpoints:
  - {id: cp1, date: 2027-03-02, label: end of Tuesday}
  - {id: cp2, date: 2027-03-04, label: end of Thursday}
  - {id: cp3, date: 2027-03-05, label: end of week}
generator:                      # provenance
  kind: hand-authored           # or: wcb-gen
```

Inbox directories dated within `seed` are **seed inputs**. Inbox directories dated in `episode.days` are delivered one per ingestion session. A checkpoint's `date` must be an episode day; its questions are asked after that day's ingestion.

### 1.2 `world.jsonl`

One JSON object per line, sorted by `t`. Ties keep file order. Every event has:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique event ID, `e-NNNN` |
| `t` | yes | When it happened in the world |
| `type` | yes | One of the types below |
| `summary` | yes, except `artifact.emit` | One line, from the worker's point of view. Used for oracle-store logs and change-question gold. |
| `project` | no | Project entity ID this event concerns |

#### `entity.create`

```json
{"id":"e-0001","t":"2027-02-15T08:00:00-08:00","type":"entity.create","summary":"Imogen Tran joins as programme lead",
 "entity":"p-imogen-tran","kind":"person","name":"Imogen Tran",
 "surface_forms":["Imogen","Immy","I. Tran","imogen.tran@corvane.example","the programme lead"],
 "attrs":{"org":"o-corvane","role":"Programme lead, Network Planning","email":"imogen.tran@corvane.example","relationship":"peer"}}
```

- `kind`: `person`, `org` or `project`.
- `surface_forms`: every other way the entity is referred to in inputs. Graders resolve answers through the alias table built from `name` and `surface_forms` across all entities.
- `attrs` are revealed together with the entity. Later changes use `fact.set`.
- Attribute keys beginning with `_` are hidden metadata and never rendered or graded, for example `_archetype` or `_minor: true`. A person with `_minor: true` is a bit player, such as a newsletter sender. Records for minor people are neither required nor penalized.

Attributes by kind:

| Kind | Attributes |
|---|---|
| person | `org`, `role`, `email`, `relationship` (as in the contract) |
| org | `kind` (`internal`, `vendor`, `customer`, `partner`, `other`), `domain` |
| project | `status`, `owner`, `summary` (current-state paragraph), `phase`, `target_date`, `next_step`, `blocker`, `sponsor`, `members` (person IDs), `orgs` (org IDs), `parent`, `budget` |

The worker's `entity.create` is always knowable, even if no artifact reveals it.

#### `fact.set`

```json
{"id":"e-0102","t":"2027-03-03T10:05:00-08:00","type":"fact.set","summary":"Harbor cutover moved to 19 March",
 "subject":"pr-harbor","attribute":"target_date","value":"2027-03-19","project":"pr-harbor"}
```

Sets an attribute on an entity, superseding the previous value. `value: null` clears it. A `fact.set` that no artifact ever reveals is **unobservable**: questions about it must be abstained from.

#### `commitment.create`, `commitment.update`, `commitment.resolve`

```json
{"id":"e-0040","t":"2027-02-17T15:20:00-08:00","type":"commitment.create","summary":"I promised Imogen a revised capacity model",
 "commitment":"c-012","kind":"task","what":"Send Imogen the revised capacity model",
 "debtor":"p-rowan-achterberg","creditor":"p-imogen-tran","others":[],
 "project":"pr-harbor","status":"open","due":"2027-03-04","accepted":true,
 "basis":"sent","keywords":["capacity model","revised"]}
{"id":"e-0077","t":"2027-03-02T11:00:00-08:00","type":"commitment.update","summary":"Capacity model handed to Malik",
 "commitment":"c-012","changes":{"debtor":"p-malik-osei"}}
{"id":"e-0091","t":"2027-03-04T16:45:00-08:00","type":"commitment.resolve","summary":"Malik sent the capacity model",
 "commitment":"c-012","status":"done"}
```

- `debtor` must act; `creditor` is owed. In the store these are the loop's `owner` and `counterparty`.
- `kind`: `task` or `ask`.
- `status` on create: `open`, `waiting` or `blocked`. Default `open`.
- `accepted: false` marks a suggested loop. It becomes a commitment when a later `commitment.update` sets `accepted: true`.
- `basis`: evidence basis of the creating input (`sent`, `received`, `reported`, `scheduled`, `inferred`).
- `keywords`: at least two distinctive words or phrases. Heuristic graders use them to match free-text answers to this commitment.
- `changes` may contain `status`, `due`, `debtor`, `creditor`, `others`, `what`, `accepted`, `project`, `keywords`. Changing `debtor` is a **transfer**.
- `commitment.resolve` sets `status` to `done` or `dropped`. A commitment can be reopened with `commitment.update` setting `status: open`.

#### `decision.make`, `decision.reverse`

```json
{"id":"e-0060","t":"2027-02-24T14:00:00-08:00","type":"decision.make","summary":"Decided to pilot route optimisation at two depots only",
 "decision":"d-003","what":"Pilot route optimisation at two depots only","by":["p-rowan-achterberg","p-hollis-baptiste"],
 "project":"pr-routing","keywords":["two depots","pilot"]}
{"id":"e-0110","t":"2027-03-04T09:30:00-08:00","type":"decision.reverse","summary":"Two-depot pilot reversed; all five depots in scope",
 "decision":"d-003","reason":"Board asked for a network-wide trial"}
```

In the store, a decision is a loop with `kind: decision`, `status: done`, `outcome` and `decided_on`; a reversed decision has `status: reversed` and `reversed_on`.

#### `project.split`, `project.merge`

```json
{"id":"e-0120","t":"2027-03-03T12:00:00-08:00","type":"project.split","summary":"Data contracts work split out of Harbor",
 "project":"pr-harbor","into":["pr-data-contracts"],"moves":{"c-020":"pr-data-contracts"}}
{"id":"e-0130","t":"2027-03-05T09:00:00-08:00","type":"project.merge","summary":"Dock scheduling folded into Yard Ops",
 "projects":["pr-dock-scheduling"],"into":"pr-yard-ops"}
```

New projects must already exist through `entity.create`. A split sets `parent` on each new project and `split_into` on the source. A merge sets `status: merged` and `merged_into` on each merged project and moves all of their commitments to `into`.

#### `artifact.emit`

```json
{"id":"e-0201","t":"2027-03-01T08:12:00-08:00","type":"artifact.emit","artifact":"em-0031","channel":"email",
 "path":"inbox/2027-03-01/em-0031.eml","received_at":"2027-03-01T08:12:00-08:00",
 "reveals":["e-0040","e-0041"],"noise":false,"challenges":["alias","implied_commitment"],
 "secrets":[],"title":"Re: capacity model for the north corridor","parent":null}
```

| Field | Meaning |
|---|---|
| `artifact` | Artifact ID; equals the file name stem |
| `path` | Path relative to the world directory. The directory date must equal the date of `received_at`. |
| `reveals` | Event IDs whose content this artifact carries |
| `noise` | `true` if the artifact carries nothing relevant |
| `challenges` | Planted-challenge tags (see §1.4) |
| `secrets` | Literal strings in the artifact that must never appear in a store: passwords, passcodes, join links |
| `title` | Short human-readable label, shown in the manifest |
| `parent` | For an attachment, the artifact ID of the carrying email or message |

### 1.3 Knowability

An event is **knowable at the end of date D** if an artifact with `received_at` on or before D reveals it. Its `known_on` date is the earliest such date. The **gold state at D** applies knowable events in `t` order. Updates to a commitment or decision whose creating event is not yet knowable are ignored, and `wcb world check` reports them as errors.

Gold therefore reflects what an ideal ingestor could know, not the full hidden truth. A commitment resolved in the world but never reported stays open in gold.

### 1.4 Planted-challenge tags

`supersession`, `reversal`, `alias`, `name_collision`, `new_entity`, `duplicate_signal`, `implied_commitment`, `weak_evidence`, `transfer`, `silent_closure`, `noise`, `unobservable`, `draft_vs_sent`, `acceptance_vs_occurrence`, `correction`, `restructuring`, `endorsement`, `worker_directive`, `version_mismatch`, `batch_catchup`, `scattered_evidence`, `privacy`.

### 1.5 `inbox/<date>/manifest.json`

Agent-visible. Generated from `artifact.emit` events.

```json
{"date":"2027-03-01","artifacts":[
  {"id":"em-0031","channel":"email","received_at":"2027-03-01T08:12:00-08:00","path":"em-0031.eml","title":"Re: capacity model for the north corridor"},
  {"id":"dc-0007","channel":"document","received_at":"2027-03-01T08:12:00-08:00","path":"dc-0007.docx","title":"Capacity model v2","parent":"em-0031"}
]}
```

### 1.6 Artifact file formats

- **Email (`.eml`).** Headers `From`, `To`, `Cc` (optional), `Date` (RFC 2822), `Subject`, `Message-ID`, and optionally `In-Reply-To`. A plain-text body. Replies quote earlier messages with `>`. Drafts carry the header `X-Draft: true`. Attachments are separate artifacts whose manifest entry has `parent` set to the email.
- **Chat (`.json`).**

  ```json
  {"workspace":"corvane","channel":"#harbor-core","kind":"channel","participants":["Imogen Tran","Rowan Achterberg"],
   "messages":[{"ts":"2027-03-01T09:02:11-08:00","user":"Imogen Tran","handle":"@imogen","text":"..."},
               {"ts":"...","user":"...","text":"...","thread_of":0,"reactions":[{"emoji":"+1","users":["@rowan"]}]}]}
  ```

  `kind` is `channel` or `dm`. `thread_of` is the index of the parent message for threaded replies.
- **Transcript (`.vtt`).** WebVTT. Each cue is `HH:MM:SS.mmm --> HH:MM:SS.mmm` followed by `<v Speaker Name>text`. A `NOTE` block at the top gives the meeting title, date and attendees. Automatic transcripts may misspell names.
- **Meeting notes (`.md`).** Free-form Markdown, typically a title, date, attendees, discussion and action items. Notes can be incomplete or wrong; a later correction supersedes them.
- **Documents.** Markdown, Word (`.docx`), Excel (`.xlsx`) or PDF.
- **Worker notes (`.md`).** The worker's own shorthand, to-do lists, directives and voice-memo transcripts.
- **Calendar (`.ics`).** `METHOD:REQUEST` (invite or update), `METHOD:CANCEL`, or `METHOD:REPLY` (acceptance or decline) with `SUMMARY`, `DTSTART`, `DTEND`, `ORGANIZER`, `ATTENDEE`, optional `DESCRIPTION` and `LOCATION`. Join links in invites are planted secrets.

## 2. Gold state: `gold/state/<date>.json`

```json
{
  "world": "pilot", "date": "2027-03-02", "worker": "p-rowan-achterberg",
  "entities": {
    "p-imogen-tran": {"kind": "person", "name": "Imogen Tran", "surface_forms": ["Imogen", "..."],
                      "attrs": {"org": "o-corvane", "role": "...", "relationship": "peer"},
                      "known_on": "2027-02-16", "evidence": ["em-0003"],
                      "attr_history": {"role": [{"value": "...", "t": "...", "event": "e-0001"}]}}
  },
  "loops": {
    "c-012": {"kind": "task", "what": "Send Imogen the revised capacity model",
              "debtor": "p-malik-osei", "creditor": "p-imogen-tran", "others": [],
              "project": "pr-harbor", "status": "open", "due": "2027-03-04", "accepted": true,
              "basis": "sent", "keywords": ["capacity model", "revised"],
              "created": "2027-02-17", "updated": "2027-03-02", "known_on": "2027-02-17",
              "evidence": ["em-0012", "ch-0040"],
              "history": [{"event": "e-0040", "t": "...", "date": "2027-02-17", "type": "commitment.create",
                           "changes": {"status": "open", "debtor": "p-rowan-achterberg"}, "summary": "...", "artifacts": ["em-0012"]}]}
  },
  "decisions": {
    "d-003": {"what": "...", "by": ["..."], "project": "pr-routing", "status": "reversed",
              "made_on": "2027-02-24", "reversed_on": "2027-03-04", "reason": "...", "keywords": ["..."],
              "evidence": ["nt-0011", "em-0090"]}
  },
  "events": [
    {"id": "e-0040", "t": "...", "date": "2027-02-17", "type": "commitment.create", "summary": "...",
     "project": "pr-harbor", "subjects": ["c-012", "p-imogen-tran"], "known_on": "2027-02-17", "artifacts": ["em-0012"]}
  ],
  "unknowable": ["e-0099"],
  "delivered": ["em-0001", "..."],
  "secrets": ["..."]
}
```

- `entities`, `loops` and `decisions` contain only knowable objects with knowable values.
- A loop's `status` is one of `open`, `waiting`, `blocked`, `done`, `dropped`.
- `events` lists every knowable non-artifact event, in `t` order. `subjects` lists the IDs the event touches.
- `unknowable` lists events with `t` on or before the date that no delivered artifact reveals.
- `delivered` lists all artifact IDs delivered up to the date; `secrets` collects their planted secrets.

## 3. Questions

### 3.1 `questions.yaml` (spec, hidden)

```yaml
- id: q-001
  checkpoint: cp1
  template: i_owe
  params: {person: p-imogen-tran}
  text: "What do I currently owe Immy?"   # optional; otherwise rendered from the template
  challenges: [alias, transfer]
```

| Template | Type | Params | Default text | Gold |
|---|---|---|---|---|
| `project_attr` | point | `project`, `attribute` | Who owns {project}? / What is the target date for {project}? / ... | Current attribute value; entity-valued for `owner`, `sponsor` |
| `person_attr` | point | `person`, `attribute` | What is {person}'s role? / Which organization is {person} with? | Current attribute value |
| `loop_owner` | point | `commitment` | Who is responsible for "{what}"? | Current debtor |
| `loop_due` | point | `commitment` | When is "{what}" due? | Current due date |
| `i_owe` | list | `person` | What do I currently owe {person}? | Active accepted loops with the worker as debtor and the person as creditor or in `others` |
| `owed_to_me` | list | `person` | What does {person} currently owe me? | Active accepted loops with the person as debtor and the worker as creditor |
| `project_loops` | list | `project` | What loops are open on {project}? | Active accepted loops on the project |
| `project_status` | status | `project` | What is the status of {project}? | Rubric (§3.3) |
| `person_brief` | brief | `person` | What am I working on with {person}? | Rubric (§3.3) |
| `project_changes` | change | `project`, `since` | What changed on {project} since {since}? | Knowable state-changing events on the project dated after `since` |
| `decision_date` | temporal | `decision` | When did we decide to {what}? | Date of `decision.make` |
| `event_date` | temporal | `event` | text required | Date of the event |
| `focus_tomorrow` | priority | (none) | What should I focus on tomorrow? | Worker-owned active accepted loops that are overdue or due by the next business day |

*Active* means status `open`, `waiting` or `blocked`. Any question becomes **unanswerable** (`answerable: false`, gold: abstain) when its target value is not knowable at the checkpoint, for example a `project_attr` on a `budget` that is never revealed.

### 3.2 `gold/questions/<cp>.json` (hidden)

```json
{"world": "pilot", "checkpoint": "cp1", "date": "2027-03-02", "questions": [
  {"id": "q-001", "type": "list", "template": "i_owe", "params": {"person": "p-imogen-tran"},
   "text": "What do I currently owe Immy?", "answerable": true, "challenges": ["alias", "transfer"],
   "support": ["em-0012", "ch-0040"],
   "gold": {"items": [{"loop": "c-012", "what": "...", "counterparty": "p-imogen-tran", "direction": "i_owe",
                       "status": "open", "due": "2027-03-04", "keywords": ["..."], "support": ["em-0012"]}]}}
]}
```

`gold` by type:

| Type | `gold` |
|---|---|
| point | `{"kind": "entity" or "date" or "number" or "text", "value": "...", "entity": "p-..." or null, "accept": ["alternative strings"]}` |
| list | `{"items": [{"loop", "what", "counterparty", "direction", "status", "due", "keywords", "support"}]}` |
| status, brief | `{"rubric": [...], "facts": {...}}` (§3.3) |
| change | `{"items": [{"event", "summary", "date", "type", "keywords", "support"}]}` |
| temporal | `{"date": "YYYY-MM-DD", "event": "e-..."}` |
| priority | `{"must_include": [list items], "worker_active": ["c-..."], "k": 10}` |
| any unanswerable | `{}` with `answerable: false` |

`support` lists the artifact IDs that carry the evidence for the gold answer. Citations are checked against it.

### 3.3 Rubrics

Status and brief questions carry a checklist. Each item has:

```json
{"id": "r1", "text": "Harbor is paused pending the security review", "weight": 2, "critical": true,
 "keywords": [["paused", "on hold"], ["security review"]],
 "stale": [["active"]],
 "support": ["em-0040"]}
```

- `weight`: 2 for critical items, 1 otherwise.
- `keywords`: groups of alternatives. The heuristic judge marks the item *covered* when every group has at least one match in the answer.
- `stale`: groups describing a superseded value. The heuristic judge marks the item *contradicted* when every stale group matches and the item is not covered.
- The LLM judge receives `text` plus `facts` and decides *covered*, *missing* or *contradicted*.

Rubrics are derived mechanically from gold state: current status and phase, latest change, blockers, active loops with owners, next dated step, and for briefs the shared projects and loops in each direction. A spec may add items with `extra_rubric`.

### 3.4 Agent-visible questions: `.wcb/questions.json`

```json
{"date": "2027-03-02", "questions": [{"id": "q-001", "type": "list", "text": "What do I currently owe Immy?"}]}
```

Unanswerable questions keep the `type` of their template, so agents cannot tell them apart.

## 4. Answers: `.wcb/answers.json`

A JSON object mapping question IDs to answers; see [`contract/answers/answers.schema.json`](../contract/answers/answers.schema.json) and the [example](../contract/answers/example.answers.json).

| Type | Fields (besides `type`, `abstain`) |
|---|---|
| point | `value`, `cites` |
| list | `items: [{text, counterparty, direction, status, due, cites}]` |
| status, brief | `summary`, `claims: [{text, cites}]` |
| change | `items: [{text, date, cites}]` |
| temporal | `date`, `text`, `cites` |
| priority | `items: [{text, due, why, cites}]`, most important first |

`direction` is `i_owe`, `owed_to_me` or `other`. `cites` holds artifact IDs and, in Track A, store record IDs such as `loops/send-capacity-model`. Answers that fail validation score 0.

## 5. Adapter: `adapter.yaml`

```yaml
name: my-agent
version: 0.3.1
model: provider/model-name
cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]   # default for both phases
ingest:
  timeout_s: 1800
query:
  cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}", "--read-only"]
  timeout_s: 900
cwd: "{workspace}"                  # working directory for the command
env: {MY_AGENT_MODE: benchmark}     # literal environment variables
env_passthrough: [MY_PROVIDER_API_KEY]
```

- `cmd` is a list (run directly) or a string (run with `/bin/sh -c`). A phase's `cmd` overrides the top-level one.
- Placeholders: `{workspace}`, `{prompt}` (prompt file path), `{prompt_text}`, `{date}`, `{phase}` (`ingest` or `query`), `{track}` (`A` or `B`), `{session_dir}`, `{adapter_dir}` (directory holding the adapter file).
- Environment: the runner passes `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR`, `SHELL`, the variables listed in `env_passthrough`, `env`, and `WCB_DATE`, `WCB_PHASE`, `WCB_TRACK`, `WCB_WORKSPACE`, `WCB_PROMPT_FILE`, `WCB_SESSION_DIR`.
- Usage reporting: the agent may write `.wcb/usage.json` (`{"input_tokens", "output_tokens", "cost_usd", "tool_calls", "model"}`) in the workspace. The runner collects and removes it.

## 6. Run directory

```text
runs/<name>/
  run.json                       adapter, track, worlds, repeats, versions, timestamps
  <world-id>/r<k>/
    workspace/                   final store
    snapshots/<date>/            store after each ingestion day (excluding .git, inbox/, .wcb/)
    sessions/<date>.ingest/      prompt.md, stdout.log, stderr.log, session.json, usage.json
    sessions/<cp>.query/         prompt.md, questions.json, answers.json, stdout.log, stderr.log, session.json
    sessions/<cp>.query-oracle/  the same, run against the oracle store
    answers/<cp>.json            collected answers
    answers/<cp>.oracle.json
  scores/report.json, scores/report.md   written by `wcb score`
```

`session.json`: `{"phase", "date", "checkpoint", "store", "cmd", "exit_code", "timed_out", "wall_s", "started_at", "usage"}`.
