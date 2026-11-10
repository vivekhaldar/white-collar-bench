# Questions

Status: v0.1. How checkpoint questions are written, rendered and given gold answers. The file formats are in [formats §3](formats.md#3-questions); how answers are scored is in [scoring](scoring.md#query-scoring). The code is `wcb/questions/templates.py` (one function pair per template), `wcb/questions/rubric.py` (keywords and rubric items) and `wcb/questions/build.py` (called by `wcb world build`).

This page is for two audiences:

- **Competitors**, who want to know exactly what a correct answer contains.
- **World authors**, who write `questions.yaml` and want to know what each template asks and when it becomes unanswerable.

## How a question is built

A world author writes a **spec** in `questions.yaml` ([formats §3.1](formats.md#31-questionsyaml-spec-hidden)):

```yaml
- id: q-005
  checkpoint: cp1
  template: i_owe
  params: {person: p-sam-patel, name_form: Samir}   # name_form is optional
  text: "What do I owe Samir?"                        # optional; replaces the template text
  challenges: [alias, endorsement]
  extra_rubric: []                                    # optional; status and brief only
```

`wcb world build` then, for every checkpoint in `world.yaml`:

1. takes the **gold state** at the checkpoint date ([formats §2](formats.md#2-gold-state-goldstatedatejson)): everything an ideal ingestor could know by the end of that day, and nothing more;
2. renders the question text from the template, unless the spec gives its own `text`;
3. derives the gold answer and its **support** (the delivered artifact IDs that carry the evidence) from the gold state;
4. writes `gold/questions/<cp>.json` ([formats §3.2](formats.md#32-goldquestionscpjson-hidden)), with questions in `questions.yaml` order. Every checkpoint gets a file, even with no questions.

The agent sees only `id`, `type` and `text` ([formats §3.4](formats.md#34-agent-visible-questions-wcbquestionsjson)).

### Conventions

- **The worker** (W) is `world.yaml`'s `worker`. "I" and "me" in question text mean the worker.
- **Active** means status `open`, `waiting` or `blocked`. **Closed** means `done` or `dropped`.
- **Accepted.** Only accepted loops count in list, brief, status and priority golds. A suggested loop (`accepted: false`, such as an ask nobody agreed to) becomes a commitment only when a later event accepts it.
- **Names in text.** Question text uses the entity's canonical `name`, or `params.name_form` when the spec sets one (an alias such as `Samir`, to exercise alias resolution). A spec's own `text` replaces the template text entirely.
- **Support** is listed in delivery order. Question-level support is the union of the supports of the gold's items or rubric items.
- **Keywords** are lowercase. A rubric item's `keywords` is a list of groups: the item is covered when every group has at least one match in the answer. List and change items carry a flat `keywords` list that graders use to match free-text items to gold.

### Unanswerable questions

A question is **unanswerable** when its target is not knowable at the checkpoint. Its gold is `{}`, its support is `[]`, and the only correct answer is to abstain. It keeps its template's `type`, so agents cannot tell it apart from the text.

| Template | Unanswerable when |
|---|---|
| `project_attr`, `person_attr` | The entity is not knowable, or the attribute was never revealed or has been cleared (for example a budget no input mentions). Hidden attributes (`_archetype`, `_minor`) are never answerable. |
| `loop_owner` | The commitment is not knowable. |
| `loop_due` | The commitment is not knowable or has no due date. |
| `i_owe`, `owed_to_me`, `person_brief` | The person is not knowable. |
| `project_loops`, `project_status`, `project_changes` | The project is not knowable. |
| `decision_date` | The decision is not knowable. |
| `event_date` | The event is not knowable (no delivered artifact reveals it). |
| `focus_tomorrow` | Never. |

An **empty list is not unanswerable.** "What do I owe Sam?" with no accepted active loops has the answerable gold `{"items": []}`; the correct answer is an empty list, not an abstention.

## Templates

| Template | Type | Params | Default text |
|---|---|---|---|
| `project_attr` | point | `project`, `attribute` | see [below](#project_attr) |
| `person_attr` | point | `person`, `attribute` | see [below](#person_attr) |
| `loop_owner` | point | `commitment` | Who is responsible for "{what}"? |
| `loop_due` | point | `commitment` | When is "{what}" due? |
| `i_owe` | list | `person` | What do I currently owe {person}? |
| `owed_to_me` | list | `person` | What does {person} currently owe me? |
| `project_loops` | list | `project` | What loops are open on {project}? |
| `project_status` | status | `project` | What is the status of {project}? |
| `person_brief` | brief | `person` | What am I working on with {person}? |
| `project_changes` | change | `project`, `since` | What changed on {project} since {since}? |
| `decision_date` | temporal | `decision` | When did we decide to {what}? |
| `event_date` | temporal | `event` | none: the spec must give `text` |
| `focus_tomorrow` | priority | none | What should I focus on tomorrow? |

`{what}` is the loop's or decision's current `what`. In `decision_date` its first letter is lowercased unless the first word is an acronym. `{since}` is written as weekday, day and month, for example `Friday 8 January`.

### Point questions

Gold: `{"kind", "value", "entity", "accept"}`.

| Kind | When | `value` | `entity` | `accept` |
|---|---|---|---|---|
| `entity` | `owner`, `sponsor`, `org`, `parent`, `merged_into`, or any value that is an entity ID | canonical name | entity ID | name and every surface form |
| `date` | value is `YYYY-MM-DD` | the date | `null` | `[value]` |
| `number` | value is numeric | the value | `null` | `[value]` |
| `text` | anything else | the value | `null` | `[value]` |

Graders resolve entity answers through the world's alias table and normalize dates and numbers ([scoring](scoring.md#query-scoring)).

#### `project_attr`

The project's current `attrs[attribute]`. Support: the delivered artifacts that reveal the event that last set the attribute.

| `attribute` | Text |
|---|---|
| `owner` | Who owns {P}? |
| `sponsor` | Who is the executive sponsor of {P}? |
| `target_date` | What is the current target date for {P}? |
| `budget` | What is the budget for {P}? |
| `phase` | What phase is {P} in? |
| `blocker` | What is currently blocking {P}? |
| `next_step` | What is the next step on {P}? |
| `status` | What is the current status of {P}: active, paused, dormant, done or cancelled? |
| other | What is the {attribute} of {P}? |

#### `person_attr`

The person's current `attrs[attribute]`, with the same support rule.

| `attribute` | Text |
|---|---|
| `role` | What is {X}'s role? |
| `org` | Which organization is {X} with? (entity answer) |
| `email` | What is {X}'s email address? |
| `relationship` | What is my working relationship with {X}? |
| other | What is {X}'s {attribute}? |

#### `loop_owner`, `loop_due`

`loop_owner` is the loop's current debtor, as an entity. A transfer changes the answer. When the worker is the debtor, `accept` also includes `me` and `myself`. `loop_due` is the current due date. Support is the evidence of the latest event that set the debtor or the due date.

### List questions

Gold: `{"items": [...]}`, one item per loop, in loop-ID order:

```json
{"loop": "c-004", "what": "Send Ada Tessellate volume pricing", "counterparty": "p-cora-velez",
 "direction": "owed_to_me", "status": "open", "due": null,
 "keywords": ["volume pricing", "pricing"], "support": ["mt-0001", "em-0004"]}
```

- `direction` is `i_owe` when the worker is the debtor, `owed_to_me` when the worker is the creditor and someone else the debtor, and `other` otherwise.
- `counterparty` is the creditor when the worker is the debtor, and the debtor otherwise.
- `support` is the loop's evidence: every delivered artifact that revealed its creation or a later change.

| Template | Items: accepted, active loops where |
|---|---|
| `i_owe` | the worker is the debtor, and the person is the creditor or in `others` |
| `owed_to_me` | the person is the debtor and the worker is the creditor |
| `project_loops` | the loop's current `project` is the project, whoever owes it |

A loop moved by a split or merge belongs to its new project.

### `project_status`

Gold: `{"rubric": [...], "facts": {...}}`. Rubric items are derived in this order. Critical items weigh 2, others 1.

| # | Aspect | When | Critical | Keywords | Stale |
|---|---|---|---|---|---|
| 1 | `status` | always | yes | status synonyms (see below); for `merged`, also the target project's names | previous status's synonyms, if it changed |
| 2 | `phase` | phase set | no | up to two distinctive words of the phase, one group each | distinctive words of the previous phase not in the current one |
| 3 | `latest_change` | always | yes | derived from the latest change event (see below) | none |
| 4 | `blocker` | blocker set | yes | up to two distinctive words, one group each | words of the previous blocker not in the current one |
| 5 | `target_date` | target date set | yes | one group of date variants | date variants of the previous target date, if it moved |
| 6 | `loop` | up to six accepted active loops on the project, worker-owned first, then earliest due | no | one group: the loop's keywords | none |
| 7 | `next_step` | next step set | no | distinctive words, plus date variants of any ISO date in it | words of the previous next step |

The text of the latest-change item is the event's `summary`. The text of a loop item is `{what} (owner: {debtor name})`.

**Status synonyms**, used as one group:

| Status | Synonyms |
|---|---|
| `active` | active, in progress, underway, on track, ongoing, moving |
| `paused` | paused, on hold |
| `dormant` | dormant, stalled, inactive, quiet |
| `done` | done, complete, completed, finished, closed, delivered |
| `cancelled` | cancelled, canceled, dropped, shelved |
| `merged` | merged, folded into |

**Change events.** An event is a state-changing event on project P when it concerns P (P is its `project` or one of its `subjects`) and it is one of: a `fact.set` of `status`, `phase`, `owner`, `target_date`, `blocker`, `sponsor` or `next_step`; a `commitment.create`, `commitment.update` or `commitment.resolve`; a `decision.make` or `decision.reverse`; a `project.split` or `project.merge`; or the `entity.create` of P itself. Changes to `summary`, `members` and other attributes are not counted. The latest such event gives rubric item 3, with keyword groups:

| Event | Keyword groups |
|---|---|
| commitment create | the loop's keywords |
| commitment update, resolve | the loop's keywords; plus words for a new status (done: done, completed, sent, returned...); the new due date's variants; the new debtor's names on a transfer |
| `decision.make` | the decision's keywords |
| `decision.reverse` | the decision's keywords, and reversal words (reversed, overturned, scrapped, no longer...) |
| `fact.set` | the new value: status synonyms, date variants, an entity's names, or distinctive words; "cleared" words for `null` |
| split, merge | the other projects' names, and split or merge words |
| project `entity.create` | distinctive words of the summary |

`facts`, for the LLM judge: the project's public attributes (entity IDs replaced by names, including the `summary` paragraph), superseded values of status, phase, target date, owner, blocker and next step, active accepted loops with owner and counterparty names, the project's decisions with their status, and the last five change events.

### `person_brief`

Gold: `{"rubric": [...], "facts": {...}}`.

| Aspect | Items | Critical | Keywords |
|---|---|---|---|
| `shared_project` | each project where the person is owner, sponsor or member (unless the project is done, cancelled or merged), or where the person and the worker are both parties to an accepted active loop | no | one group: the project's name and surface forms |
| `i_owe` | up to five accepted active loops the worker owes the person, earliest due first | yes | one group: the loop's keywords |
| `owed_to_me` | up to five accepted active loops the person owes the worker, earliest due first | yes | one group: the loop's keywords |
| `role` | the person's role, if known | no | up to two distinctive words of the role, one group each |

If none apply, a single item says that nothing is shared; an answer saying so ("nothing", "no open loops") covers it. `facts` holds the person's attributes, the shared projects, the loops in each direction and the last five events that involve the person.

### `project_changes`

Gold: `{"items": [...]}`, one item per knowable state-changing event on the project (as defined above) whose world date is after `since`, in world order:

```json
{"event": "e-0020", "summary": "Quillon decision target moved to 5 February", "date": "2027-01-11",
 "type": "fact.set", "keywords": ["target date", "2027-02-05", "feb 5", "..."], "support": ["nt-0002"]}
```

`keywords` are the loop's or decision's keywords; for a `fact.set`, the attribute name plus the value's keywords; otherwise the flattened groups from the table above. `support` lists the artifacts that reveal the event. The date compared with `since` is when the event happened, not when it was revealed.

### `decision_date`, `event_date`

Gold: `{"date": "YYYY-MM-DD", "event": "e-..."}`. For `decision_date`, the date and event of the `decision.make`, even if the decision was later reversed. For `event_date`, the date of the event's `t`. Support: the artifacts that reveal that event. `event_date` has no useful default text. Without a spec `text`, it falls back to quoting the event's summary, which world authors should avoid.

### `focus_tomorrow`

Gold:

```json
{"tomorrow": "2027-01-13", "must_include": [...], "worker_active": [...], "distractors": [...], "k": 10}
```

- `tomorrow`: the next business day after the checkpoint date.
- `worker_active`: every accepted active loop the worker owes, earliest due first.
- `must_include`: the `worker_active` loops due on or before `tomorrow`, including overdue ones.
- `distractors`: knowable loops that are closed, or owed by someone else.
- `k`: how many listed items count.

Items use the list-item shape. Support is the union of the `worker_active` items' support.

## Rubric keywords

Rubric items are derived mechanically from gold state ([formats §3.3](formats.md#33-rubrics)), and every keyword group is chosen so that a correct answer would plausibly contain it.

- **Dates** become one group of prose variants from `wcb.util.dates.text_variants`: `2027-02-05`, `5 feb`, `february 5th`, `2/5` and so on.
- **Entities** become one group of their name and surface forms.
- **Free text** (phase, blocker, next step, role) becomes at most two distinctive words, one group each. Stopwords, generic words (`project`, `update`, `status`, `waiting`...), words of fewer than three letters and the project's or person's own name are skipped. Longer words are preferred.
- **Stale** groups describe a superseded value. The heuristic judge marks an item *contradicted* when every stale group matches and the item is not covered, so presenting an old target date or phase as current costs points. Words shared by the old and new values are dropped from free-text stale groups.

### Extra rubric items

A `project_status` or `person_brief` spec may add hand-written items with `extra_rubric`. They are appended after the derived items and numbered after them:

```yaml
extra_rubric:
  - text: "The pilot now covers the Reno and Sparks depots"
    keywords: [sparks, [reno, "two depots"]]   # a bare string is a one-word group
    critical: true                              # weight 2; default false (weight 1)
    support: [mn-0001]
  - "Mentions the steering meeting"            # text only: judged by the LLM judge
```

## Fields beyond formats §3

The builder adds three fields that formats §3 does not list. Graders may ignore them.

- Every rubric item has an `aspect` (`status`, `phase`, `latest_change`, `blocker`, `target_date`, `loop`, `next_step`, `shared_project`, `i_owe`, `owed_to_me`, `role`, `nothing_shared` or `extra`) for reports and debugging.
- The priority gold has `tomorrow`.
- `loop_owner` gold accepts `me` and `myself` when the worker owns the loop.

## Example

The fixture world `tests/fixtures/mini-world` exercises most templates. At `cp2` (2027-01-12), `What is the status of Quillon?` has this rubric:

| ID | Aspect | Text | Keywords | Stale |
|---|---|---|---|---|
| r1 | status | Quillon is active | active / in progress / ... | |
| r2 | phase | Current phase: pilot planning | pilot; planning | vendor; evaluation |
| r3 | latest_change | I sent Cora the completed security questionnaire | security questionnaire / questionnaire; done / sent / returned / ... | |
| r4 | target_date | Current target date: 2027-02-05 (moved from 2027-01-29) | variants of 2027-02-05 | variants of 2027-01-29 |
| r5 | loop | Send Ada Tessellate volume pricing (owner: Cora Velez) | volume pricing / pricing | |

An answer that still gives 29 January as the target date is contradicted on r4. One that says Quillon is "in progress, now planning the pilot" covers r1 and r2.
