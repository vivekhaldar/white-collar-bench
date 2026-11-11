# Qwen3.8-27B + Pi: Tracks A and B

Run dates: **10–11 November 2026 UTC**. The workdays and people in the worlds are
synthetic; their 2027 dates are not the actual execution dates.

Benchmark revision: `b66134a773e94bf7e0b6394133e4b167fbc05b69`; WCB 0.1.0,
GOLD_VERSION 3. This record consolidates the original run, subsequent questions and
audits, output-budget experiments, missing-checkpoint retest, full Track B run, and
recommendations. No benchmark/scorer changes were made to obtain these results.

## Executive summary

| Evaluation | WCB / 100 | World-bootstrap 95% CI | Interpretation |
| --- | ---: | --- | --- |
| Original Track A | **72.3421558365** | 65.40–77.38 | Unchanged heuristic scorer; original 32k response cap and failures retained |
| A, nine confirmed false negatives credited, before retest | 73.1068902340 | 66.45–78.14 | Narrow manual counterfactual |
| A, missing 15-question checkpoint replaced by retest | **73.0181753076** | 66.23–77.83 | Hybrid: all other original sessions unchanged |
| A, retest plus those nine corrections | **73.7829097051** | 67.26–78.62 | Hybrid plus manual semantic-credit adjustments |
| Full Track B | **54.9968251634** | 48.24–61.34 | Unchanged heuristic scorer; context-derived output allowances |
| B, three confirmed false negatives credited | **55.3335255001** | Not recomputed | Narrow manual counterfactual, not an exhaustive regrade |

Original Track A Synthesis (oracle-store questions): **84.2704282295**; SIS (store
integrity): **98.4145192837**, final-day SIS **97.87**. These were not rerun or adjusted.

**There is no fully adjudicated substance-based score for either track.** Nine Track A
and three Track B examples have been verified and credited diagnostically. Candidate
false negatives elsewhere have not all been adjudicated. All corrections retain the
original citation penalties; none removes genuine model errors or failed sessions.

These scores evaluate a particular model/provider/runtime/harness combination, not the
model alone. One repeat and public worlds do not support a leaderboard ranking.

## What this benchmark measures

WCB is a longitudinal memory benchmark: a fresh agent ingests each day's email, chat,
meetings, documents, notes, and calendar into durable files. At checkpoints another fresh
session answers questions using those files. Daily inboxes disappear after ingestion;
conversation history does not persist. Challenges include aliases, ownership transfers,
revised dates, reversed decisions, weak commitments, indirect completion, and noisy inputs.

- **Track A:** starts from a correct structured store and must maintain the Markdown/YAML
  [store contract](../../contract/CONTRACT.md). Queries use both the agent-maintained
  store and a separate oracle store. SIS measures store integrity.
- **Track B:** starts from raw seed inputs, constructs its own memory, and may organize
  files arbitrarily. There are no oracle queries or SIS. It is not just Track A with a
  different serialization: seed initialization is also additional work.
- These are the two implemented tracks; Synthesis and SIS are metrics, not other tracks.
- All pilot and ten public dev worlds were used, not the private test split.

WCB is **not percent exactly correct**. It averages question scores within type buckets,
then buckets within checkpoints, checkpoints within episodes, repeats within worlds,
and worlds overall, finally multiplying by 100. Unanswerable questions have their own
bucket. Confidence intervals bootstrap worlds, not repeated model sampling.

## Model, harness, isolation, and assumptions

| Setting | Value |
| --- | --- |
| Model | `Qwen/Qwen3.8-27B`, verified in authenticated provider catalog |
| Provider | Nebius Token Factory, `https://api.tokenfactory.nebius.com/v1` |
| Deployment metadata | FP4; **1,000,000-token context** |
| Token prices observed | $0.45/M uncached input; $0.10/M cached input; $3.00/M output |
| Credential | Existing `TOKEN_FACTORY_API_KEY`; no credential value included |
| Harness | `@earendil-works/pi-coding-agent@1.5.2` |
| Tools | Pi `read`, `bash`, `edit`, `write` |
| Thinking | Explicit `chat_template_kwargs.enable_thinking=true` |
| Sampling | Provider defaults, no seed or explicit reasoning-effort parameter |
| Session state | Fresh processes; no external skills, MCP, personal context discovery, or persistent sessions |
| Limits | 120 assistant turns; ingestion 1,800 s; query 900 s |
| Parallelism | Normally four independent world workers |
| Grader | Unchanged deterministic heuristic judge, not LLM semantic grading |

The user authorized unattended execution, reasonable documented assumptions, and paid
model calls. No world-specific prompt tuning or edits to measured stores were performed.
Smoke/configuration probes were kept separate. Model-caused failures in final measured
configurations were retained, not retried to obtain a better sample.

Docker's daemon was unavailable. Bubblewrap 0.8.0 provided fresh user/PID/mount namespaces,
isolated home and `/tmp`, and workspace/runtime/config mounts. A namespace probe confirmed
the benchmark repository and gold were absent. Network was shared with the orb rather
than endpoint-allowlisted: this was **not leaderboard-verified isolation**.

The tool runtime had Node, shell, and system Python, but not the host benchmark virtualenv.
YAML/PDF parsing dependencies were not all preinstalled. Missing PyYAML and PDF readers
led to ad hoc installation/parser work. This is an experiment-runtime limitation; its
quantitative impact was not isolated.

### Smoke tests and setup

An initial smoke failed because Pi needed writable config/auth lock files; per-session
disposable writable configuration fixed that. A subsequent smoke repeatedly ran a flawed
validator and was excluded. API controls showed tool requests without an explicit thinking
setting returned zero reasoning tokens, while `enable_thinking=true` enabled reasoning.
The successful thinking-enabled mini-world smoke completed all four sessions and produced
13 valid answers: WCB 89.61, SIS 98.81, 118.02 s, approximately $0.28. It did not establish
coverage of all rich-document tooling before the full run.

## Original Track A

All eleven worlds built without errors/warnings. Scope: **100 ingestions, 51 agent-store
queries, 51 oracle-store queries: 202 sessions**. Each query arm covered 745 questions.

- Agent: 730/745 schema-valid; **357 full, 296 partial, 92 zero**. The 15 invalid/missing
  answers all belong to a single missing checkpoint file.
- Oracle: 745/745 valid; **486 full, 240 partial, 19 zero**.
- Two ingestion timeouts; four final length terminations (three ingestions, one query).
  Native JSON-mode exit behavior retained partial writes from those truncated ingestions.
- WCB process statuses: 200 `ok`, two timeout. These operational counts do not imply
  successful task completion; truncation and missing answers are disclosed separately.
- Null control, same Track A worlds/scope: WCB 12.7, Synthesis 12.7, SIS 91.5.

### World breakdown: original A and final B

The A columns below are the original capped run, **not** the hybrid/manual corrections.

| World | A WCB | A Synthesis | A SIS | B WCB |
| --- | ---: | ---: | ---: | ---: |
| pilot | 42.40 | 80.92 | 96.31 | 30.330563 |
| gen-s1-w1 | 81.23 | 86.15 | 99.37 | 64.230508 |
| gen-s2-w1 | 72.69 | 89.66 | 97.02 | 67.536374 |
| gen-s3-w1 | 78.18 | 89.34 | 99.23 | 62.063735 |
| gen-s4-w2 | 71.27 | 85.27 | 97.93 | 51.864010 |
| gen-s5-small | 76.46 | 74.03 | 98.97 | 49.082831 |
| gen-s6-w1 | 79.25 | 85.60 | 99.47 | 69.841913 |
| gen-s7-w2 | 71.86 | 84.17 | 97.83 | 48.916509 |
| gen-s8-w4 | 66.44 | 82.16 | 98.58 | 42.646573 |
| gen-s9-large | 83.02 | 86.52 | 99.45 | 61.207478 |
| gen-s10-w2-small | 72.96 | 83.17 | 98.38 | 57.244582 |

### Question-type breakdown

| Type | Questions per arm | A agent | A oracle | B |
| --- | ---: | ---: | ---: | ---: |
| Point | 187 | 83.82 | 94.55 | 46.702317 |
| List | 165 | 68.73 | 87.16 | 39.669218 |
| Status | 52 | 38.84 | 43.78 | 33.857634 |
| Brief | 77 | 71.06 | 81.16 | 35.564053 |
| Change | 52 | 49.94 | 72.31 | 34.508223 |
| Temporal | 85 | 93.11 | 99.71 | 88.259804 |
| Priority | 51 | 66.34 | 94.94 | 46.366189 |
| Unanswerable | 76 | 96.05 | 98.68 | 93.421053 |

Pilot was already weak at its first two A checkpoints (47.2, 47.3), before its final
ingestion timeout. Status grading was weak even on oracle stores. The A Synthesis–WCB
gap of 11.93 is diagnostic, **not a causal estimate of ingestion damage**: fresh query
sessions can express identical facts differently, receiving different heuristic grades.
The negative gap on gen-s5-small is another warning against that causal interpretation.

### Cost, timing, and recovery

Original A ran **10 November 22:10:15–11 November 00:12:15 UTC**, 122 minutes elapsed,
7.04 hours summed session time across workers. Independent metering and Pi costs agree
at **$65.0098802**: ingestion $48.52, agent queries $8.95, oracle queries $7.54.
All 5,465 generation requests returned HTTP 200. Usage: 14,927,376 uncached input,
346,644,800 cached input, 7,876,027 output, including 5,181,168 reasoning tokens.
There were 9,973 tool invocations.

A gen-s4-w2 query-copy infrastructure exception interrupted its shard before a model
session. Standard resume skipped completed work and retained it; no model failure was
retried. Recovery temporarily created a fifth worker. Final reports were assembled
separately because the orchestrator retained its prior exception. Original shard/recovery
metadata remains in the evidence bundle.

Two ingestion sessions, pilot March 6 and gen-s8 September 22, timed out in model-written
Python front-matter validators. Their loops could `continue` without advancing an index.
Extracted functions reproduced hangs on valid YAML; bounded probes stopped after 0.25 s.
The runner's 1,800-second timeouts restored each prior snapshot, verified byte-for-byte
(204 and 321 files), and cleaned up the CPU-bound children. These were genuine tool-code
failures; neither stores nor scripts were repaired.

## The 32k limit: what happened and why it was removed

**Context size was 1,000,000 tokens, not 32,768.** The original adapter separately imposed
32,768 maximum output tokens per response as a generation-budget guard. There was no
validation justifying that exact cap; it was an experiment choice, not a provider limit.
It was consequential and should not be presented as the model's maximum capability.

The missing gen-s8-w4 cp3 query exited 0 after 60.582 s without writing answers. Its last
response used **32,768 output tokens, all reasoning**, ending `length`; total context
use was only 95,315, far below 1M. All 15 questions scored zero. Three other ingestions
also ended at the cap. Pi 1.5.2's text mode detects final truncation, but JSON-mode native
exit semantics did not; the wrapper mapped `error`/`aborted`, not `length`, to failure.

Another consequential A example: gen-s7-w2's July 5 ingestion truncated while considering
the original in-house Corrie decision. The original decision/date was not persisted;
later memory retained its reversal/replacement. At cp6 q-082, the agent abstained about
the original decision date while the oracle query correctly answered July 5.

### Failed budget configurations, excluded rather than cherry-picked

1. **Omit `max_tokens`:** Nebius silently applies its documented **8,192-token default**.
   Live length endings exposed this. The first retry produced 15 valid answers (10 full,
   four partial, one zero), checkpoint 76.1418, hybrid A 72.9190 or 73.6837 with nine
   corrections. These are **superseded configuration-probe results**, not the credited
   retest. Its B attempt was stopped; this configuration's recorded cost was $1.4698943.
2. **Pi-estimated remaining context:** succeeded for the final A retest below, but some
   large B seed inputs were undercounted. For example, provider input 23,817 plus requested
   output 978,737 overflowed the 1M window by 2,554. Three requests failed validation;
   that B attempt was stopped, at approximately $0.34253795 recorded cost.
3. **Exact provider remainder, final B:** intentionally send `max_tokens: 1000000` to get
   the provider's pre-generation overflow validation with its exact formatted input count.
   Then send the identical generation payload with `max_tokens = 1000000 - input_count`.
   Mock wire and live Pi controls verified payload equivalence and accepted allowances.
   The API has no documented token-count endpoint. `max_tokens: 0` generates zero tokens;
   it is not an unlimited-output setting. This workaround adds latency and expected 400s,
   not generated completions on the validation requests.

### Credited 15-question retest

The user requested removing the cap, retesting the missing questions, adjusting A, then B.
The valid retry used the original saved September 18 store and original questions/schema.
Its input-store hash matched. Gold was not mounted; saved snapshots lack historical Git
metadata. Pi used context-derived allowances of **921,113–994,289**. All requests succeeded.

**15 valid answers: ten full, five partial, none zero.** Checkpoint score **89.2345701841**:
point 100, list 81.25, status 52.0710, brief 88.8889, change 100, temporal 100,
priority 91.6667, unanswerable 100. Runtime 82.563 s; 21 successful calls; **$0.1735983**;
51,022 uncached input, 859,584 cached input, 21,560 output tokens.

Replacing just this checkpoint increases A by **0.6760194711**, to 73.0181753076.
All original ingestion failures/caps remain. Its largest response was only 3,978 tokens:
success **does not prove removing the cap alone caused recovery**, since sampling was
unseeded. The first retry was excluded for configuration error before this retry began,
not selected afterward as a worse candidate. Final B used exact provider counts rather
than this retest's successful Pi-estimated allowance; that distinction is intentional.

## Full Track B

Ran **11 November 06:49:24–09:07:28 UTC**, **8,284 s / 2h 18m 4s**. All eleven worlds,
one repeat: **11 seed ingestions + 100 episode ingestions + 51 queries = 162 sessions**.
All **745 answers schema-valid**: **150 full, 360 partial, 235 zero**.

161 sessions completed; gen-s8-w4 seed ingestion hit the unchanged **120-assistant-turn
budget** after 650.318 s. Its pre-seed workspace was restored and execution continued.
That failure and its consequences remain included; it was not retried. The other 110
ingestions and every query completed. There were zero timeouts or length terminations.

The 4,518 generation requests all returned HTTP 200. Each had a paired expected HTTP 400
token-count validation. **Zero unexpected HTTP errors**; all exact input counts matched
subsequent generation usage, and every input count plus output allowance equaled 1M.
Allowances ranged **697,627–998,109**. The largest response was **140,388 output tokens**,
all reasoning, ending normally in gen-s7-w2 July 6 ingestion. Largest observed combined
input/output context: **303,885 tokens**. This exercised removal of both 32k and 8k caps.

Independent usage/pricing and Pi totals reconcile to **$59.44714395**: ingestion
$51.01357910, queries $8.43356485. Usage: **32,852,495 uncached input**, **275,352,192 cached
input**, **5,709,434 output**, including **3,027,537 reasoning tokens**.

Recorded follow-up cost including B, the valid retest, and excluded probes:
**$61.43317450**. Original A's $65.00988020 is separate. These are published-token-price
estimates, not invoices; negligible separate controls and unreported usage from interrupted
requests are not guaranteed included.

**A versus B is not a clean controlled ablation.** Initialization, output budgets, failure
patterns, and answer style differ, as well as memory format. Some B penalties are real
losses of factual state, some are citation-protocol mistakes, and some are scorer friction.

## Correct, incorrect, and falsely rejected answers

### Genuine successes and mistakes

All examples refer to synthetic sources. These are selected cases, not population estimates.

| Track / case | Outcome | Evidence |
| --- | --- | --- |
| B, gen-s1 cp1 q-012 | Correct: approach-C decision on November 8; full credit | November 8 `nt-0007` |
| A, gen-s7 cp6 q-082 | Agent abstains; oracle correctly answers July 5 | Original decision not persisted after capped July 5 ingestion |
| B, gen-s7 cp1 q-008 | Wrong: July 26 instead of August 3 target | July 6 `mn-0014` explicitly replaces July 26 |
| B, gen-s1 cp2 q-028 | Wrong: Yasmin instead of Nadia owns synthetic resident dataset | November 11 `em-0111`: Nadia will take it from here |
| B, gen-s8 cp8 q-112 | Wrong: Adwoa instead of Marcelo sends service blueprint | September 30 `em-0192` transfers it to Marcelo |
| B, gen-s3 cp2 q-027 | Wrong: Guadalupe instead of Vitoria pulls baseline data | September 22 `em-0099` transfers it to Vitoria |
| B, gen-s2 cp2 q-027 | Wrong: Dina instead of Thibault sends decision memo | March 5 `em-0068` transfer; later `ch-0091` confirms Yael received it from Thibault |
| B, gen-s8 cp8 q-118 | Wrong: Batbayar instead of Adwoa owns retention schedule v2 | September 30 `ch-0160` supersedes September 29 assignment |
| B, gen-s10 cp5 q-052 | Wrong: Akosua instead of Jia sends Noris materials | September 9 `em-0101` handoff; answer's own note acknowledges it |

### Nine verified Track A point-answer false negatives

The audit exhaustively examined the narrow slice of **15 valid, non-abstaining, zero-scored
text-kind point answers**, not all 745 answers. Nine were source-verified semantic false
negatives. They all became base 1 when only `value` was shortened to the canonical wording;
citations were unchanged. Eight then scored 1; Tillie's retained penalty gives 0.9375.

| World / checkpoint / question | Rejected answer's correct core and elaboration | Canonical value | Corrected final |
| --- | --- | --- | ---: |
| pilot / cp1 / q-012 | Privacy Officer at Tarrow University Kestrow, Office of Privacy and Records | Privacy Officer | 1 |
| pilot / cp3 / q-048 | Advising Operations Lead at Saltmarren; leads its advising scheduling work | Advising Operations Lead | 0.9375 |
| gen-s4-w2 / cp2 / q-022 | Information Security Manager at the Systemwide Learning Innovation Office | Information Security Manager | 1 |
| gen-s7-w2 / cp2 / q-027 | Delivery, with transition July 7 and August 16 target | delivery | 1 |
| gen-s3-w1 / cp1 / q-009 | Stakeholder, with Lena's alias, role, and hospital | stakeholder | 1 |
| gen-s5-small / cp1 / q-009 | Executive, with Rodrigo's title and organization | executive | 1 |
| gen-s6-w1 / cp2 / q-022 | Privacy Officer at Dorcliff State College | Privacy Officer | 1 |
| gen-s9-large / cp1 / q-016 | Peer, with Mathieu's role and shared organization | peer | 1 |
| gen-s9-large / cp2 / q-025 | Privacy Officer at Redridge Children's Hospital | Privacy Officer | 1 |

Exact original answers, citations, per-checkpoint changes, and world changes are retained
in [the counterfactual evidence](evidence/track-a-nine-false-negatives.json).
Role/organization qualifiers were checked against source signatures or initial notes;
the delivery transition and target date were checked against source and state.

One further blocker answer had the right core but an additional causal claim not established
by the inspected sources; it was not credited. The other five needed factual/semantic
adjudication (different next action, merged-versus-placeholder phase, peer-versus-stakeholder,
task-versus-project blocker, complete-versus-closed phase). They were not automatically
accepted merely because a terse mutation scores better.

[Issue #3](https://github.com/vivekhaldar/white-collar-bench/issues/3) records these cases,
source checks, scorer code, tested public-world reproduction, exclusions, and acceptance
criteria. No original prediction files or official score reports were rewritten.

### Three verified Track B corrections and broader candidates

In gen-s1-w1 cp3:

| Question | Correct substance rejected | Why the scorer failed | Diagnostic final |
| --- | --- | --- | ---: |
| q-036 | Workshop complete November 10, with follow-on network distinguished | Canonical phase is `closed` | 1 |
| q-040 | Due `2027-11-18`, delivered early November 12 | Date extraction chose the contextual November 12 | 0.7916666667 |
| q-041 | Current target `2027-12-31`, followed by superseded-date history | Date extraction returned no date | 0.875 |

Sources: November 10 `ch-0091`, November 12 `nt-0011`, November 9 `ch-0073` respectively.
Changing only their values retains citation penalties. All three original scores were 0.
Their combined credit is 8/3; three point questions, eight checkpoint buckets, three
checkpoints, and eleven worlds yield **+0.3367003367** aggregate points, hence **55.3335255001**.

The complete B diagnostics list **66 non-abstaining zero-scored point answers**: 38 text,
19 entity, nine date. These are candidates, not 66 adjudicated false negatives. Another
**45 rubric answers (34 brief, 11 status)** match some rubric keywords but fall below the
global 0.5 focus threshold, which can zero every rubric item. In gen-s1 cp3 q-038, four
groups match but focus 0.48 produces zero; disabling only that gate diagnostically gives
base 0.7 / final 0.5541667. That is not a validated correction and was not credited.

Generic file citations such as `commitments.md` can also be unrecognized under the source-ID
or recognized-store-path contract. These are protocol errors, not automatically grader
false negatives. Full details are in [B examples](evidence/track-b-scorer-examples.json)
and [diagnostic candidates](evidence/track-b-scorer-diagnostics.json).

## Tracing Pi: three different failure mechanisms

These findings come from completed tool events, stored files, and actual answer writes,
not speculation about hidden attention or reasoning. Pi is the harness; Qwen selects tools
and content. [Trace evidence](evidence/pi-traces.json) records relevant events and checks
without reproducing private reasoning blocks. Full logs remain in the raw bundles.

### 1. Lanmoor: source read, no durable writes

September 22 ingestion lists `em-0099`, then reads it in an email batch. The tool result
includes the full Guadalupe-to-Vitoria handoff. It makes 27 calls reading existing memory,
emails, chat, and extracting a DOCX into `/tmp`. **It never writes durable memory.**

The final response contains only a reasoning block, 19,948 output/reasoning tokens, followed
by a normal stop. Exit 0, status `ok`, 58.477 s: neither timeout nor length truncation.
SHA-256 comparisons show all 32 non-Git snapshot files identical before/after ingestion.

The September 23 query reads the stale project and commitments files. They still name
Guadalupe from September 10 `em-0030`; it answers Guadalupe with 95% confidence and cites
that old assignment. The source inbox has disappeared. **Failure: persistence at ingestion**,
not missing source access during ingestion or merely poor query-time selection.

Decisive raw log lines, `gen-s3-w1/r1/sessions/2027-09-22.ingest/stdout.log`: 161/173
(source read), 179/186 (DOCX extraction), 190 (final stop). Query project/commitment results
are at cp2 transcript lines 62/112. Paths are relative to the measured Track B bundle.

### 2. Mistral: correct memory read, original owner answered

Memory accurately says Thibault received the memo from Dina and delivered it to Yael.
`unknowns.md` explicitly says Dina did not send it herself. The old task nevertheless
remains in **Dina's open commitments**, annotated “moot” and explaining Thibault's delivery.
The project history and timeline also preserve the update.

The query successfully reads `people.md` and `commitments.md`, `decisions.md` and
`unknowns.md`, the project record, and the timeline. The corrective statements are in the
returned tool output, without truncation notices. It then writes Dina as q-027's owner,
citing the original assignment **and** handoff/receipt. Validation checks answer structure,
not current ownership. **Failure: answer construction after correct retrieval.** The
misleading denormalized heading is a plausible contributor, not a proven internal cause.

Decisive `gen-s2-w1/r1/sessions/cp2.query/stdout.log` results: lines 48, 58, 69, 110;
answer write at 136.

### 3. Fulmar: responsibility transfer recast as recipient change

September 30 ingestion reads the transfer and persists it in the log, decisions, projects,
people, and worker summaries. However, its saved interpretation says **“Amira no longer
the recipient”** and Batbayar is passing it to Adwoa **instead of sending it to Amira**.
The project heading remains **“Retention schedule v2 (Batbayar's)”**. Under the benchmark's
transfer semantics, responsibility moves to Adwoa; Amira remains the intended recipient.

The query reads the project, decisions, and daily log with the handoff present; it writes
Batbayar and cites both original and superseding messages. **Failure: semantic role
interpretation already visible in memory, followed by wrong answer selection.** More
retrieval alone is not sufficient.

Decisive `gen-s8-w4/r1/sessions/2027-09-30.ingest/stdout.log` events: source at line 130;
memory writes/edits at 266, 274, 298, 306, 314. cp8 query results at 59, 83, 93; answer
write at 205. These three traces do not demonstrate a Pi tool-execution bug, a context
overflow, or an output-cap failure; nor do they establish population frequencies.

## Benchmark and scorer findings

### Point grading rejects supported explanatory detail

`wcb/grade/answers.py` deliberately permits at most 0.5 extra content tokens/entities per
gold token for text matching. Short phase/role answers have almost no tolerance for
supported qualifiers. Entity resolution can also treat incidental people in an explanation
as competing answers. Dates can be mis-extracted when correct current values coexist with
historical/assignment/completion dates. This is not simply exact-string equality.

The right change is **unambiguous, temporally correct fact resolution**, not substring
acceptance or blindly increasing a token threshold. Resolve phase/relationship synonyms
and the queried subject/attribute; distinguish context dates; reject negation, hedging,
wrong institutions, and obsolete facts presented as current. Use evidence-aware semantic
fallback for genuinely free-text roles, blockers, and next actions. A short `value` plus
separate explanation could help future contracts, but explanations must not contradict it.

**Existing `--judge llm` does not fix point grading**: that path does not consult the judge.
For list/change/status/brief matching it can help, but must be pinned, calibrated against
human-labeled contrast cases, cached, and reported as a different scorer configuration.
The 0.5 rubric-focus gate is documented anti-stuffing behavior, not a newly discovered
implementation bug; changing it requires adversarial controls, not blanket credit.

### Citation metric both accepts wrong support and rejects valid support

`collect_cites` flattens claim/item citations and deduplicates them. `citation_precision`
checks membership in the **question-wide** support set, not evidence for the attached claim.
This conflicts with the documented claim-support meaning. Item support helps matching
but is not mandatory for a candidate to match.

- Pilot cp1 q-013 has a weekly update supported by `em-0019` and a Council one-pager
  supported by `mt-0008`. Replacing the first item's citation with the second item's
  source keeps base/citation/final all **1.0**. A nonexistent-source control gives citation
  0.5 and final 0.875. Correct answer content is still graded separately.
- Conversely, A retest gen-s8 cp3 q-038 correctly mentions sending Kian the AI-use plan
  and cites `ch-0030`, which directly supports it. The question whitelist contains only
  `nt-0001`, so that evidence is rejected. Replacing only that citation with already-cited
  `nt-0001` raises final **0.8888888889 → 0.90625** without changing any words.

Impact is up to 25% of base score per question. Fix claim/item association and evidence
coverage; do not merely broaden the whitelist. Aggregate impact was not measured and is
not part of the manual corrections.

### Runner integrity and Git snapshot reliability

- **Cached comparison weakness:** `workspace.py` uses `filecmp.cmp(..., shallow=False)`.
  Deterministic probe: compare equal files, change bytes while preserving size and mtime,
  compare again; `tree_diff` can return no changes. This weakens between-session integrity
  enforcement. Initial full pytest: 1 failed, 1,216 passed; the affected test passed alone.
  The weakness is confirmed; its attribution as the cause of that intermittent test is
  inferred, not proven. Replace cached comparison with uncached byte/hash checks.
- **Live `.git` copy race:** gen-s4's query workspace copy saw vanished pack/rev/lock files.
  Tracing runner Git commits confirms host Git 2.55 starts detached automatic maintenance.
  This strongly supports a maintenance/copy race; a 12-attempt controlled probe did not
  reproduce the exception. Disable automatic maintenance for runner-owned Git operations
  and make copies consistent rather than copying a mutating `.git` directory.

### Gold/oracle consistency

Generated `perfect_answers` score 1 on all 693 dev questions and 51/52 pilot questions.
Pilot cp3 q-036 scores 0.7333 due to the known enrollment-totals rubric contradiction;
the resulting overall perfect-answer aggregate is about **99.9495**, not 100. This is an
existing documented heuristic limitation, not a Qwen error.

In gen-s7, July 8 `mt-0014` expands the Garnet pilot from three to four courses. The July 17
oracle contains the accepted decision/history but its current summary still says three;
gold entity summary is equally stale. The simulator regenerates summary prose from static
archetype description. This violates current-state consistency, but no particular question's
grade was proven wrong because of it. “Oracle” does not mean globally consistent prose.

The mini-world smoke also showed change-matching sensitivity: cp2 q-008 correctly described
date/phase changes but missed heuristic matches, and combined a reversal/replacement that
gold treats as two events. Score 0.5455; no manual correction was made.

## What to fix before spending on another run

Recommendations, **not implemented in this results commit**:

1. **Scoring validity first:** reproduce the verified point false negatives as public-interface
   regressions; implement subject/attribute-aware canonicalization and evidence-aware fallback
   where needed. Calibrate rubric/list/change judgments on a human-labeled sample. Preserve
   anti-hedging and contradiction tests. Freeze/version the scorer and regrade saved answers
   before interpreting a new model's delta. Do not treat `--judge llm` as a point-grading fix.
2. **Integrity/reliability before a full run:** uncached content comparison and consistent Git
   query copies. These concern validity and completion, not merely score interpretation.
3. **Citation semantics before comparative claims:** validate support per claim/item, allow
   genuine alternative evidence, and keep correctness separate from extra unsupported claims.
4. **Oracle calibration before Track A comparisons:** repair the stale current-state scope
   and known perfect-answer discrepancy, with versioned gold/scorer expectations. Do not
   quietly rebuild history under the old label.
5. **Adapter/runtime hygiene:** pin working YAML/PDF/document tooling; classify JSON-mode
   truncation as incomplete rather than successful; bound shell tools and clean descendants.
   Report no-op ingestion/write activity diagnostically. Do not automatically retry an
   otherwise normal but unproductive model session or demand a write on every noise-only day.

The first two are the highest-priority blockers for a defensible next full evaluation.
The citation/oracle findings should also be settled before leaderboard-style comparison.
Changes to agent memory organization are a **new agent variant**, not scorer fixes: one
current-owner record per commitment, historical events separate from current fields, and
explicit persistence/completion checks are promising, but were not tested here.

## Recommended next model and harness

**Claude Opus 5.5 (`claude-opus-5-5`) + Pi**, using the same pinned Pi/tool interface and
session isolation, is the recommended next diagnostic pairing. Hold the harness constant
to test whether these persistence/transfer/answer-construction errors depend on the model.
This is an experimental-design recommendation, not a measured WCB superiority claim.

Official [Anthropic model documentation](https://platform.claude.com/docs/en/models/opus-5-5/overview),
checked 11 November 2026, documents **1M context**, **128K synchronous output**, adaptive
thinking, default medium effort, and base **$4/M input, $20/M output** ($0.20/M cache reads).
Record the resolved model/version and a chosen effort rather than leaving it implicit.
Respect the actual provider output ceiling; do not impose another unexplained 32k ceiling
or reuse the Nebius-only overflow-validation workaround. Cost will differ substantially;
there is no reliable invoice projection from Qwen token counts alone.

First smoke the revised adapter/runtime and freeze configuration, then run the same public
worlds/tracks with multiple repeats if comparing models. Regrade the saved Qwen outputs
with the same revised scorer, and retain the original scores alongside them. Runtime fixes
mean this is not a perfectly model-only comparison with the historical run unless Qwen is
also rerun under the new runtime; disclose that rather than claiming a causal model delta.

A subsequent **Opus 5.5 + Claude Code** run can isolate a harness change while holding the
model constant; the repo already has a Claude Code adapter. Do not change both model and
harness at once and attribute the result to either. Sonnet 5.5 + Pi is a cheaper official
model alternative ($2/M input, $10/M output), not a model tested in this experiment.
No next-model run, paid judging, or new credential setup was performed for this record.

## Evidence, verification, and limitations

Tracked files:

- [Original Track A score report](scores-track-a.json), copied unchanged.
- [Original Track B score report](scores-track-b.json), copied unchanged.
- [Original follow-up accounting](followup-results.json), an immutable historical export
  produced before the three-case B correction; its no-source-changes fields describe that
  run stage, not this later results-documentation commit.
- [Adjustment calculations](adjustments.json), including conservative B correction.
- [Nine A corrections](evidence/track-a-nine-false-negatives.json),
  [B examples](evidence/track-b-scorer-examples.json),
  [B diagnostic candidates](evidence/track-b-scorer-diagnostics.json),
  [citation counterexample](evidence/citation-whitelist-counterexample.json),
  [configuration-probe accounting](evidence/configuration-probes.json), and
  [tool/snapshot trace evidence](evidence/pi-traces.json).

Full archives are deliberately **not checked into Git** (about 100 MB combined). Their
download links are in the [thread's detailed report](https://ampcode.com/artifacts/qwen3-8-27b-pi-benchmark-run-15ecdff9-20ec-4db3-b516-a18b349e1ff5);
access may require permission to that Amp thread. The tracked record is readable without
them, but does not contain all raw transcripts/snapshots. Archive provenance:

| Bundle | Bytes | SHA-256 |
| --- | ---: | --- |
| `qwen38-pi-evidence.tar.gz` | 48,559,671 | `b4285e00538a017c14b4ee63332d31f065cd422b41321a10f18f7f57d612328d` |
| `qwen38-pi-followup-evidence.tar.gz` | 51,527,816 | `191e079ac087b8499b565f3d4a0dfb0c48d5a09645aa5b7536e4fdf4a615f30c` |

The original archive validated 24,189 standard files and 44 supplement files against
manifests. Follow-up archive reopened successfully: 4,148 files; **3,660/3,660 manifest
hashes match**. Independently compared 24,188 original measured files against the original
archive: zero differences. Credential-byte scans found zero actual-key occurrences.

Raw archive layout: original A includes `measured/` and `reproduction/config/`; final B is
under `runs/pi-qwen38-provider-remainder/track-b/measured/`, with final configuration in
its sibling `config/`. The valid retest is `runs/pi-qwen38-context-budget/retest/`.
Excluded probes are separately retained. Original score JSON contains absolute orb paths
as provenance; those are not portable filesystem links. Restore the bundles/configuration
and remap paths before trying to reproduce their command lines.

All run services were stopped after completion. Source and score artifacts were unchanged
during measurement/audits. This commit records results; it does not implement recommendations
or rewrite measured outputs. Full-suite validation at run time was **not clean** (the
1,216-pass/one-failure result above); the isolated retry passing does not erase that fact.
Ruff and all-world build checks passed. Documentation/data checks for this results record
are separate from those historical execution checks.

Results-record checks passed: ten JSON files parse, all sixteen relative Markdown links
resolve, the three historical score/accounting exports are byte-identical to their sources,
score adjustments and breakdown tables reconcile, trace and archive hashes match, and an
exact-byte scan finds no available credential values in the twelve committed files.
