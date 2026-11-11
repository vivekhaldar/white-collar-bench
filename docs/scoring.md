# Scoring and run protocol

Status: draft. See [design](design.md) for task structure and [plan](plan.md) for construction.

## How to run the benchmark

A competitor supplies an **adapter**: a small config that tells the runner how to invoke their agent and harness. The runner owns the episode loop, the workspace, the clock and the grading. The agent only ever sees the workspace.

### 1. Install and fetch worlds

```bash
git clone <this repository> && cd white-collar-bench
uv venv && uv pip install -e .     # or: pip install -e .
wcb world list                     # the pilot and dev worlds ship in worlds/, with gold
```

### 2. Write an adapter

```yaml
# adapter.yaml
name: my-agent
version: 0.3.1
model: provider/model-name        # reported on the leaderboard
ingest:
  cmd: ["my-agent", "run", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]
  timeout_s: 1800
query:
  cmd: ["my-agent", "run", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]
  timeout_s: 900
env_passthrough: [MY_PROVIDER_API_KEY]
```

The runner fills in `{workspace}` and `{prompt}`. The prompt is a file of fixed benchmark text. Adapters may wrap it with their own system prompt, but must not add knowledge specific to a world.

### 3. Run and score

```bash
wcb run   --adapter adapter.yaml --split dev --track A --repeats 3 --out runs/my-agent
wcb score runs/my-agent            # writes report.json and report.md
```

For the leaderboard, submit a container image plus `adapter.yaml`. Maintainers run it on the private test split (see [Submission](#submission-and-verification)).

## Episode protocol

```mermaid
sequenceDiagram
  participant R as Runner
  participant A as Agent (adapter)
  participant W as Workspace
  R->>W: copy seed store (Track A) or empty dir + seed inputs (Track B)
  loop each simulated day
    R->>W: place inbox/<date>/
    R->>A: ingest session (fresh process, WCB_DATE=<date>)
    A->>W: read inbox, update store
    R->>W: remove inbox/, snapshot store (git commit)
    opt checkpoint
      R->>W: read-only copy + .wcb/questions.json
      R->>A: query session (fresh process)
      A->>W: write .wcb/answers.json
      R->>R: discard copy, keep answers
    end
  end
  R->>R: grade
```

Rules:

- **Fresh process per session.** No memory carries over outside the workspace. On the leaderboard, each session runs in a new container.
- **Inbox is drained.** Inputs are available only during their ingestion session. The agent may archive copies inside the store. Raw archiving followed by search at query time is a legitimate strategy; Track A's store grading measures whether curation also happened.
- **Query sessions are read-only.** The runner discards any changes made to the store.
- **Clock.** `WCB_DATE` and the prompt give the simulated date. The agent must treat it as "today".
- **No outside data.** The network is limited to model endpoints. Gold and world files are never mounted.
- **Budgets.** Each session has a wall-clock timeout. Timeouts and crashes leave the store as it was (ingestion) or count as empty answers (query). So does a session that leaves a store the runner cannot read or copy. No process of a session outlives it, and the store cannot change between sessions: the runner reverts any change it finds before the next session ([running](running.md#5-run)).

### Standard prompts

**Ingestion:**

> Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). Incorporate them into the store following `CONTRACT.md`. Inputs will not be available after this session.

**Query:**

> Today is {date}. Answer every question in `.wcb/questions.json` using the store. Write `.wcb/answers.json` following `.wcb/answer-schema.json`. Cite sources. Abstain when the store does not support an answer. Do not modify the store.

In Track B, `CONTRACT.md` is replaced by a one-paragraph goal statement, `GOALS.md` (from [`contract/GOALS-TRACK-B.md`](../contract/GOALS-TRACK-B.md)), and the prompts refer to "your files" instead of "the store":

**Track B seed ingestion** (one session before the first episode day, with every seed date's inputs at once):

> Today is {date}. Your inputs so far, up to and including today, are in {inbox_dirs}, one directory per date (each has a `manifest.json`). Incorporate them into your files following `GOALS.md`. Inputs will not be available after this session.

**Track B ingestion:**

> Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). Incorporate them into your files following `GOALS.md`. Inputs will not be available after this session.

**Track B query:**

> Today is {date}. Answer every question in `.wcb/questions.json` using your files. Write `.wcb/answers.json` following `.wcb/answer-schema.json`. Cite sources. Abstain when your files do not support an answer. Do not modify your files.

The texts live in [`wcb/runner/prompts.py`](../wcb/runner/prompts.py).

## Answer format

```json
{
  "q-0412": {
    "type": "list",
    "abstain": false,
    "items": [
      {
        "text": "Send Marisol the revised vendor scorecard",
        "counterparty": "Marisol Teague",
        "direction": "i_owe",
        "status": "open",
        "due": "2027-03-05",
        "cites": ["em-0193", "loops/send-marisol-vendor-scorecard.md"]
      }
    ]
  },
  "q-0413": {
    "type": "status",
    "abstain": false,
    "summary": "Thistledown is waiting on Brenwick's security questionnaire...",
    "claims": [
      {"text": "Vendor shortlist cut to two on 3 Mar", "cites": ["mt-0057"]}
    ]
  },
  "q-0414": {"type": "point", "abstain": true}
}
```

Each type has a JSON Schema in `contract/answers/`. Answers that fail validation score 0.

## Query scoring

Each question scores between 0 and 1.

| Type | Score |
|---|---|
| **Point fact** | 1 if the answer resolves to the gold entity or value, using the world's alias table and normalized dates or numbers; otherwise 0. |
| **List** (owes, owed, open loops) | Soft F1. Predicted items are matched to gold items one-to-one (see Matching). Each match earns attribute credit `a` = fraction correct of status, due date and counterparty. Soft precision = Σa / predicted; soft recall = Σa / gold. |
| **Status / relationship brief** | Checklist coverage. Gold has weighted checklist items (current status, latest change, blockers, open asks with owners, next dated step; critical items weigh 2, others 1). Judge marks each item *covered*, *missing* or *contradicted*. Score = max(0, (Σw·covered − Σw·contradicted) / Σw). Presenting a superseded fact as current counts as contradicted. |
| **Change since T** | F1 over gold change events (status changes, new or closed loops, decisions) between T and now. |
| **Temporal** | 1 for the exact date or event; 0.5 within one business day; otherwise 0. |
| **Prioritization** | Recall of the gold must-include set (overdue or due-next-day items owned by the worker) in the top k, multiplied by (1 − share of listed items that are closed or not the worker's). |
| **Unanswerable** | 1 for abstaining; 0 for any substantive answer. |

**Abstention on answerable questions scores 0.** There is no partial credit for hedging.

### Citations

Each claim or item cites artifact IDs and, in Track A, store paths. Citation precision `c` is the fraction of citations that exist and support what they are attached to: in list and change answers, the item; otherwise the answer as a whole. Supporting artifact IDs come from the world model; store paths are judged against the record's content. The final question score is:

```text
q_final = q × (0.75 + 0.25 × c)
```

Missing citations give `c = 0`, which caps the question at 0.75. A question with no supporting artifacts, such as an answerable list whose correct answer is empty, has nothing to cite: `c` does not apply and the score is `q`.

### Matching

List and change items are matched to gold in two steps:

1. **Candidates:** gold items sharing a cited artifact or the same counterparty.
2. **Confirmation:** a pinned judge model answers one narrow yes/no question per candidate pair: "Do these describe the same commitment?"

The final one-to-one assignment maximizes confirmed matches. Judge prompts, model, version and temperature are fixed per release: temperature 0 for a single sample, and 1.0 when voting over 3 samples. The default `wcb score` judge is the deterministic heuristic judge; `--judge llm` selects a pinned model. See [judges](judge.md) for prompts, thresholds and model pinning.

### Aggregation

```text
checkpoint score  = macro-average over question types present at that checkpoint
episode score     = mean over checkpoints
WCB score (track) = 100 × mean over episodes and repeats
```

Macro-averaging by type prevents list questions, which are numerous, from dominating. Reports include 95% bootstrap confidence intervals over episodes. Two entries whose intervals overlap are reported as tied.

## Store integrity (Track A)

After every ingestion day `d`, the store is compared with the knowable gold state `G_d`.

| Metric | Definition |
|---|---|
| **Entity F1** | People and project records mapped to world entities via names and aliases (judge for ambiguous cases). A duplicate record counts as a false positive; a wrongly merged record counts as a false negative for the entity it absorbed. |
| **Loop F1** | Loop records matched to knowable commitments, using the same matching as list questions. |
| **Field accuracy** | On matched loops: status, owner direction, counterparty, due date and accepted flag, equally weighted. |
| **Freshness** | 1 − share of matched loops and projects whose state reflects a superseded fact. |
| **Groundedness** | 1 − share of records or claims that no delivered artifact supports. |
| **Validity** | 1 − min(1, contract-validator errors / records). |

```text
SIS_d = 100 × mean(Entity F1, Loop F1, Field accuracy, Freshness, Groundedness, Validity)
SIS   = mean of SIS_d over days; final-day SIS reported separately
```

## Error attribution (Track A)

Each checkpoint's questions also run against the oracle store for that date, in a separate query session with the same adapter.

```text
Synthesis score  = WCB score on oracle stores
Ingestion cost   = Synthesis score − WCB score (end-to-end)
```

A small ingestion cost means the agent kept the store about as good as a perfect one. The report also shows each checkpoint's score against episode day, so error growth over time is visible.

## Efficiency

The runner records wall time and tool or command counts. Token use and cost come from either:

- **Metered mode:** model calls go through the runner's proxy (`wcb run --meter`; see [running](running.md#7a-metered-runs)). This is required for a *verified* leaderboard badge.
- **Self-reported mode:** the adapter writes `.wcb/usage.json` after each session.

Reported per simulated day of ingestion and per checkpoint of querying, alongside a cost-versus-score plot.

## Report

`wcb score` produces:

- **Headline:** WCB score (Track A and/or B), with confidence interval.
- **Track A:** SIS, Synthesis score, Ingestion cost.
- **Breakdowns:** by question type, planted challenge, checkpoint position and episode length.
- **Efficiency:** tokens, cost and time per simulated day.
- **Failure samples:** worst-scoring questions with gold and predicted answers, for debugging on dev worlds only.

## Submission and verification

1. Develop against the `dev` split, which includes gold, locally.
2. Submit a container image, `adapter.yaml` and model identifiers.
3. Maintainers run Track A and/or B on the private `test` split: 3 repeats, metered mode, fresh container per session.
4. Results are published with the harness version, model, date and cost. Test worlds are refreshed each release, and older results are marked with their release.

## Validating the scoring

Before release, the scoring must show:

- **Ordering:** null baseline < raw retrieval < reference agents < oracle-store ceiling on dev.
- **Sensitivity:** deliberately corrupted stores (duplicated person, stale status, dropped loop) lower SIS and the scores on dependent questions.
- **Judge agreement:** κ ≥ 0.8 with human graders on matching and coverage decisions.
- **Stability:** re-grading identical answers changes scores by less than 1 point.

## Implementation notes (v0.1)

This section records the concrete choices made by the v0.1 grader: `wcb/grade/integrity.py` (store integrity), `wcb/grade/score.py` (run scoring and aggregation) and `wcb/grade/report.py` (report rendering). Where it differs from the sections above, this section describes what the code does.

### Scales

Per-question scores and the six SIS sub-metrics are in [0, 1]. Every aggregate (checkpoint, episode, world and WCB scores, Synthesis, Ingestion cost, SIS, and the breakdown tables) is on a 0-100 scale.

### Store integrity

SIS is computed for every **episode day** that has a snapshot (`<run>/<world>/r<k>/snapshots/<date>/`), against the gold state of that date (`gold/state/<date>.json`, or `state_at` when the file is missing). The seed-end snapshot is not scored: in Track A it is the oracle seed store. SIS is Track A only, and is skipped for `--skip-ingest` runs.

**Store-to-world mapping (Entity F1).**

- Gold is every knowable person, org and project at the date, except minor entities (`attrs._minor`). The worker counts as a person.
- A record's *forms* are its `name`, `aliases`, `email` (people; a string or a list) and `domain` (orgs). An entity's forms are its `name`, `surface_forms`, `attrs.email` and `attrs.domain`.
- Forms are compared as whole normalized phrases: lowercase ASCII words joined by spaces, so case, accents, punctuation and a leading `@` do not matter, and a leading "the" is optional. `Marisol.Teague@brenwick.example` is the phrase `marisol teague brenwick example`. Forms are only compared with entities of the record's own kind (`people/` with persons, `orgs/` with orgs, `projects/` with projects). The record's file name is not used.
- A form that names several knowable entities of that kind (a first name two people share) is *ambiguous* and names no one. Ambiguity is decided among entities knowable at the date, so "Sam" identifies Sam Patel until a second Sam becomes knowable.
- `people/me` always maps to the worker.
- One entity named by the record's unambiguous forms: **mapped**. Several: **wrong merge**. The record maps to the entity its `name` names, else to the one named by the most forms (ties: lowest entity ID), and *absorbs* the others. Only ambiguous forms: **unresolved**. No matching form: **unmatched**. Only minor entities: **minor**, which is ignored on both sides.
- When several records map to the same entity, one keeps the mapping and the others are **duplicates**. The keeper is `people/me`, then a cleanly mapped record before a wrong merge, then the lowest record ID.
- TP = knowable entities that some record maps to. FP = every other counted record: duplicates, unresolved and unmatched records. FN = knowable entities that no record maps to. An absorbed entity is therefore a false negative unless another record maps to it. Entity F1 = 2·TP / (2·TP + FP + FN), and 1 when the store and gold both have no entities.
- v0.1 has no judge for ambiguous cases. An unresolved record is a false positive.

**Loop F1.** Gold is every knowable commitment, in any status and including suggested ones (`accepted: false`), plus every knowable decision. Each loop record becomes a predicted item:

- `text`: the `title`, or the first body line when the title is missing;
- `owner`: the owner record's `name`;
- `counterparty`: the name of the *other party*, meaning the person on the far side of the loop from the worker. That is the record's counterparty when the worker owes, and its owner when the worker is owed;
- `cites`: the evidence `source` IDs.

Each gold item carries `what`, `keywords`, `support` (the loop's evidence artifacts) and the other party computed the same way: the creditor when the worker owes, the debtor when the worker is owed, otherwise the creditor. Decisions have no counterparty. Items are matched one-to-one with `wcb.grade.matching.match_items` (kind `loop`), using the run's judge. Using the other party rather than the creditor keeps the worker from becoming a shared counterparty that would make every loop owed to the worker a candidate for every other one. Leaving status and due date out of the items lets an LLM judge's cache serve the same pair on every day. Loop F1 = F1 of the matched pairs against the loop records and the gold loops.

**Field accuracy.** Each matched loop gets the mean credit of its fields. Field accuracy is the mean of that over matched loops. With no matches it is 1 if the store and gold both have no loops, else 0.

- Commitments, five fields, equally weighted:
  - `status`: 1 when equal; 0.5 when both are active (`open`, `waiting`, `blocked`); else 0.
  - `owner`: 1 when the owner link maps (through the entity mapping) to the gold debtor.
  - `counterparty`: 1 when it maps to the gold creditor.
  - `due`: 1 when the dates are equal or both are empty.
  - `accepted`: 1 when it is a boolean equal to gold's.
- Decisions, status only: `done` for a made decision, `reversed` for a reversed one.
- A link maps to an entity when it is `people/me` or names an existing record that maps to an entity. Duplicates and wrong merges map to their entity.

**Freshness.** The records checked are the matched loops plus every project record mapped to a project entity.

- A matched commitment is stale when its `status`, `due` or owner equals a *superseded* value, meaning a value from the loop's `history` changes that differs from the current one.
- A matched decision is stale when gold has reversed it and the record still says `done`.
- A project is stale when its `status` or `target_date` equals a superseded value from the entity's `attr_history`.
- Empty values never count as superseded. A missing due date is an omission, which field accuracy grades, not a stale fact.
- Freshness = 1 − stale / checked, and 1 when nothing is checked. In v0.1 project owners are not checked.

**Groundedness.** 1 − the share of loop records with no evidence `source` among the artifacts delivered by the date. Evidence entries may be mappings or bare strings. With no loop records it is 1. In v0.1 it covers loop records only, not every record or claim.

**Validity.** `wcb.contract.validate.validate_store`, with the gold state's `secrets`, so a leaked planted secret is an error, and its `delivered` set. Validity = 1 − min(1, error-severity issues / max(1, records)). Records are every file in `people/`, `orgs/`, `projects/`, `loops/` and `logs/`. Warnings do not count.

`SIS_d = 100 × mean of the six`. An episode's SIS is the mean over its scored days. The final-day SIS is the SIS of its last scored day. Both are averaged over repeats, then over worlds.

### Per-question grading

`wcb/grade/answers.py` grades one answer at a time. Where these rules differ from the tables above, they describe the code.

**Framing.** Answers often mention an old value next to the current one. A value after a history word in the same clause (`from`, `was`, `previously`, `formerly`, `originally`, `not`, `no`, `never`, `instead` and a few others) is *framed as history*; a value after `to`, `now`, `currently`, `new` or `->` is *framed as current*. A clause ends at `. , ; : ( ) [ ] ! ?`. The word lists are `HISTORY_MARKERS` and `CURRENT_MARKERS` in `wcb/util/text.py`.

**Point facts.** Normalized equality with the gold value or an `accept` string always counts. Otherwise, by gold `kind`:

- *entity*: among entities of the gold one's kind (person, org, project), the answer names exactly the gold entity. Names framed as history are skipped ("Cora Velez (took it over from Sam Reyes)" is fine), and so are worker pronouns (`me`, `you`, ...) right after a preposition ("owes it to me"). Other names count, so "Cora Velez or Sam Reyes" and "Cora Velez or me" score 0. So does a name shared by several entities of that kind unless the gold entity is one of them: "Cora Velez or Sam" hedges with a Sam even though "Sam" alone names no one.
- *date*: every date in the answer is found (ISO, `m/d`, `Feb 5`, `5 February 2027`). Dates framed as history are dropped. If one date remains it is the answer; if several remain, the one framed as current is the answer when there is exactly one ("Moved on 1/11 to Feb 5"); otherwise the answer is ambiguous and scores 0 ("Feb 5 or Feb 12"). A date without a year takes the year that puts it between three months before and nine months after the checkpoint date, so "December 30" at a January checkpoint is the previous December.
- *number*: the same, for numbers. Dates, numbers glued to letters (`Q3`, `FY2027`, `v2`) and, when another number remains, bare years are skipped. Among several different numbers, the one framed as current wins, else the one marked as money or with a `k`/`m` suffix ("$180k for 3 campuses").
- *text*, for a project's `status` (`project_attr` with `attribute: status`): a closed vocabulary. The answer must name exactly the gold status among the six statuses and their synonyms (the status synonyms in [questions](questions.md#project_status)), not counting ones framed as history, and contain no hedge word. "In progress" and "Active (no longer paused)" are right; "active, paused, dormant, done or cancelled", "active or paused" and "not active" are wrong.
- *text*, otherwise: names of people, orgs and projects are compared as entities, not words. The answer must contain every other content word of the gold value; may add at most half as many other content words or entities as the value has content words, not counting words and entities of the question; must not name, instead of an entity in the value, another entity of its kind; and must contain no hedge word (`or`, `either`, `maybe`, `perhaps`, `possibly`, `probably`, `unclear`, `unsure`) that the value lacks. Words framed as history do not count. Finally, for `project_attr` and `person_attr` questions, the answer must not state a *rival* value: the same attribute of another entity of the subject's kind, or the subject's earlier value. A rival is stated when every content word it does not share with the gold value or the question occurs in the answer, not framed as history. So for "Registrar, TU Saltmarren", "Registrar" and "Registrar at Saltmarren" are right; "Registrar at Kestrow", "Former registrar, now Provost", "Registrar or Provost" are wrong. For Sam Reyes's role "Solutions engineer", "Solutions engineer / Data engineer" (Sam Patel's role) is wrong and "Solutions engineer, not a data engineer" is right.

**Temporal.** A `date` that matches the schema's `YYYY-MM-DD` pattern but is not a calendar date (`2027-02-30`) scores 0, with `details.problem` set.

**Lists and changes.** A predicted item that repeats an earlier one (the same content words in `text` and `counterparty`, the same `due` and `date`) cannot match, however many gold items the judge would confirm it for, and still counts as predicted. Counterparty credit needs the predicted name to name exactly the gold counterparty, by the entity rule above: "Cora Velez" and "Cora (Tessellate)" earn it for Cora; "Sam", "Cora Velez, Ben Okoro" and a list of everyone do not. `direction` is not graded: it is not one of the three attributes, and for `i_owe` and `owed_to_me` questions the question fixes it.

**Prioritization.** The top `k` items are matched one-to-one against the worker's loops (must-include and other worker-active ones); a repeated item cannot match. An item is a distractor only when the judge confirms it against some distractor and against none of the worker's loops; each such item counts, duplicates included. The factor is 1 − distractor items / *loop items*, where loop items are the top items the judge confirms against some gold loop (worker's or distractor). An item that describes no loop ("Catch up on email") counts neither way, so filler neither dilutes the penalty nor costs anything.

**Status and brief.** The judge sees the `summary` followed by each claim's `text`. The heuristic judge's rules are in [judges](judge.md#rubric): a superseded value presented as current contradicts its item even when the current value is there too ("29 Jan or 5 Feb", "vendor evaluation or pilot planning"), and an answer whose content words and dates are mostly not in the question's gold `facts` covers nothing, so a generic list of every status, date, role and loop scores 0.

**Citations.**

- Cites are grouped into *units*, and `c` = valid cites / cites counted over all units. A source cited twice in one unit counts once; `loops/x` and `./loops/x.md` are the same record.
- **List and change answers** are checked per item. Each predicted item is a unit, checked against the `support` of the gold item it was matched to (Matching above), or against the question's `support` when it matched none (an extra or repeated item). Top-level `cites` (and any `claims`) form one more unit, checked against the question's `support`. A source cited on several items counts once per item and must support each of them, so global deduplication cannot hide a misattached citation. A cite that supports another gold item of the question but not its own is `wrong_item`.
- **Point, status, brief, temporal and priority answers** are checked against the question as a whole: all cites (top-level, items, claims) form one unit checked against the question's `support`. Their claims are not item-structured; whether each prose claim is supported by its own cites is not checked.
- An artifact ID is valid when it is in the unit's support. Support is widened at build time to every delivered artifact about the same commitment, decision or attribute ([formats §3.2](formats.md#32-goldquestionscpjson-hidden)), so an artifact that reports a later update to a loop is valid evidence for that loop. An artifact that does not exist or is not yet delivered (`not_delivered`), or that is delivered but about something else (`not_in_support`), is invalid.
- A store path (Track A) is valid when the record exists in the store the answers came from and its text names an artifact of the unit's support: in its `evidence`, a `[src: ...]` note or a log line. This is how "judged against the record's content" is implemented. A record that cites none of them is invalid (`record_unsupported`, or `wrong_item` when it names only another item's support); a missing record is `no_such_record`.
- `people/me` is never valid (`worker_record`). Every answer relates to the worker, so citing it is not specific evidence.
- When the question's `support` is empty, `citation` is `null` and the score is the base score. This covers answerable empty lists, change questions with no changes, and priority questions with no worker loops.
- `details.citations` gives `scope` (`item` or `question`), `total`, `valid` and `invalid` (`{cite, why}`, plus `item`, the predicted item's index, for item units).

Example: two gold loops, A supported by `em-1` and B by `mt-2`. An answer lists both, correctly, with A citing `mt-2` and B citing `mt-2`. Units: A {`mt-2`} (wrong item), B {`mt-2`} (valid), so `c` = 1/2 and the score is `q x 0.875`. Citing `em-1` on A gives `c` = 1. If one artifact genuinely reveals both loops, it is in both items' support and citing it on both is 2/2.

**Grader errors.** If an answer passes validation but a grader raises a value error on it, the question scores 0, `details.grader_error` says why, and a line is added to `notes`. Errors raised by the judge itself, such as an unreachable model, still stop `wcb score`.

### Answers and aggregation

- Agent answers come from `answers/<cp>.json` and are graded with store-path citations resolved against `snapshots/<cp date>/`. Oracle answers come from `answers/<cp>.oracle.json` and are resolved against the world's `gold/oracle-store/<cp date>/`. The context's entities and delivered artifacts come from `gold/state/<cp date>.json`. Questions come from `gold/questions/<cp>.json`, or are built from `questions.yaml` with a note when that file is missing.
- With `options.max_days` in `run.json`, only checkpoints within the played days are scored. After `wcb run --resume`, `options` covers every invocation: `max_days` is the largest given (none if any invocation had none) and `skip_ingest` is true only if every invocation used it, so a resume that extends a run is scored in full ([running](running.md#6-resume)).
- **Buckets.** A question's bucket is its type. Every unanswerable question goes to the bucket `unanswerable`, whatever its type.
- **Checkpoint score** = the mean over the buckets present of each bucket's mean question score. **Episode score** = the mean over checkpoints. **World score** = the mean over repeats. **WCB** = 100 × the mean over worlds, so every world weighs the same even when repeat counts differ.
- **Confidence interval.** A 95% percentile bootstrap over worlds: 2000 resamples of the world scores with replacement, `random.Random(20270101)`, taking the 2.5th and 97.5th percentiles of the resampled means. With one world the interval is degenerate `[score, score]`. Repeats are averaged before resampling and are not resampled.
- **Oracle stores** hold only what the inputs delivered by their date show ([worlds](worlds.md#oracle-stores)): an alias appears once some input has used it, a first name is dropped as ambiguous only once a namesake is knowable, and record-ID suffixes follow reveal order. A person's `## Threads` uses the `person_brief` notion of a shared project (owner, sponsor or member of a live project, or a shared accepted active loop), and a project's `people` includes its sponsor, so an oracle answer finds the same shared projects as the gold.
- **Synthesis score**: the same aggregation over oracle answers. These are scored when `run.json` has `oracle: true`, or, without that key, when any `*.oracle.json` file exists. Track B has none. **Ingestion cost** = Synthesis − WCB, at every level: world, episode, checkpoint and question type.
- **Missing pieces.** A missing or unreadable answers file scores every question of its checkpoint 0. A missing episode directory scores all its answers 0 and has no SIS. A missing snapshot skips SIS for that day and makes store-path citations invalid. An answer the grader cannot handle scores 0 (see Grader errors above). A `--skip-ingest` run (`options.skip_ingest`) reports only Synthesis: WCB, SIS and Ingestion cost are `null`. Every gap adds a line to `notes`.
- **Gold drift.** Before scoring, a world whose gold is missing or stale is rebuilt (as `wcb run` does). If the world's `gold/BUILD.json` differs from the one `run.json` recorded when the run was made, because the world or the gold version changed, a note says so: answers are always graded against the current gold, so compare such scores with care.

### Efficiency

Read from every `sessions/*/session.json`. Sessions fall into three groups:

- `ingest`: phase `ingest`, including the Track B seed session;
- `query`: agent store;
- `query_oracle`: store `oracle`.

For each group the report gives the session count, `ok` / `timeouts` / `failures` counts, how many sessions reported usage, and the total and mean of `wall_s`, `input_tokens`, `output_tokens`, `cost_usd` and `tool_calls`. Means are taken over the sessions that report the value. Token counts come from `metered_usage` for sessions run with `wcb run --meter` (input tokens include cache reads and writes) and from the agent's own `usage.json` otherwise. `usage_metered` counts the metered sessions. `per_episode` is the total of agent sessions (ingest + query) divided by the number of episodes. `per_ingest_day` (by world and date) and `per_query_session` (by world, checkpoint and store) give means over repeats.

### `report.json`

| Key | Content |
|---|---|
| `report_version`, `scored_at`, `scorer` | Report layout version (`0.1`), UTC time of scoring, `{version, wcb_version}` |
| `run` | `{dir, track, adapter, wcb_version, status, started_at, finished_at, options, scored: {agent, oracle}}` from `run.json` |
| `judge` | `{kind, name, model, calls}`; `calls` counts LLM calls made (cache misses × samples) |
| `output` | `{dir}` where the report was written |
| `headline` | `{track, wcb, wcb_ci95, synthesis, synthesis_ci95, ingestion_cost, sis, sis_final, n_worlds, n_episodes, n_questions}`; `n_questions` counts graded agent question instances (oracle ones for `--skip-ingest`) |
| `worlds[]` | `{id, path, days, n_days, checkpoints[] (with day_index), score, synthesis, ingestion_cost, sis, sis_final, repeats[]}` |
| `worlds[].repeats[]` | `{repeat, score, synthesis, ingestion_cost, checkpoints[], sis}`; each checkpoint is `{id, date, label, day_index, n_questions, score, score_buckets, synthesis, synthesis_buckets, ingestion_cost}`; `sis` is `null` or `{days[], mean, final, final_date}` |
| `worlds[].repeats[].sis.days[]` | `{date, sis, entity_f1, loop_f1, field_accuracy, freshness, groundedness, validity, errors: {entity_fp, entity_fn, wrong_merges, loop_fp, loop_fn, stale, ungrounded, validator_errors}, missing_entities, false_positive_records, missing_loops, unmatched_loop_records, stale_records}` |
| `breakdowns.by_type` | bucket → `{n, wcb, synthesis, ingestion_cost}`, mean question score × 100 over all checkpoints and repeats, in the order point, list, status, brief, change, temporal, priority, unanswerable |
| `breakdowns.by_challenge` | planted-challenge tag → the same fields; a question counts once for each of its tags |
| `breakdowns.by_checkpoint[]` | `{world, checkpoint, date, label, day_index, n_days, n_questions, wcb, synthesis, ingestion_cost}`, averaged over repeats |
| `sis_by_day[]` | `{world, date, n_repeats, sis, <six metrics>}`, averaged over repeats |
| `efficiency` | `{summary: {ingest, query, query_oracle}, per_episode, per_ingest_day[], per_query_session[]}` (see Efficiency above) |
| `failures[]` | Up to 10 agent questions (oracle ones for `--skip-ingest`) scoring below 1, lowest first (ties by world, repeat, checkpoint, ID): `{world, repeat, checkpoint, store, id, type, template, text, answerable, challenges, score, base, citation, gold (without facts, or "abstain"), predicted, details}` |
| `questions[]` | One row per graded question instance, agent and oracle: `{world, repeat, checkpoint, store, id, type, bucket, template, challenges, answerable, valid, abstained, base, citation, score}` |
| `notes[]` | Gaps and caveats: missing answers, snapshots or gold files, Track B or `--skip-ingest` limits |

`report.md` renders the same data in this order: run header, headline table, scores by world and repeat, the three breakdowns, SIS per day with final-day store errors, efficiency tables, failure samples (gold and predicted JSON, truncated to 1500 characters) and notes. `wcb score` prints `Report.summary_text()`, which shows the headline numbers and where the files went. LLM judge decisions are cached in `<out>/judge-cache.jsonl`.

### Test helper: perfect answers

`wcb.baselines.gold_answers.perfect_answers(gold_doc, store_ids=None)` turns a gold questions document into answers that score about 1.0. It reads gold, so it is not a baseline:

- point: the gold value;
- list: one item per gold item, with its `what`, counterparty name, direction, status and due date;
- status and brief: the rubric texts plus the first alternative of every keyword group;
- change: each summary with its keywords;
- temporal: the gold date;
- priority: the must-include loops, then the other worker-owned active loops;
- unanswerable: abstain.

Every answer cites its gold `support`. With `store_ids` (`wcb.store.oracle.record_ids`), items also cite their loop records. The tests use it to check that correct answers score at least 0.95 on every question and about 100 end to end.
