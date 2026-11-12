# Status

Where the benchmark stands against the [construction plan](plan.md#5-milestones), with measured numbers. Updated 2026-11-12 for wcb 0.1.0, `GOLD_VERSION` 5.

## Milestones

| Milestone | State | Notes |
|---|---|---|
| M0 Specs | done | Track A [contract](../contract/CONTRACT.md) v1.0, world, question and answer [formats](formats.md), [adapter protocol](adapters.md), store validator (`wcb validate`). |
| M1 Pilot world | done, awaiting practitioner review | Hand-authored one-week world (below). Gold is computed by `wcb world build` from the hand-written event log, not written by hand. Artifacts were checked against the gold batch by batch and reconciled across threads; a realism read by someone who does this work is still to do. |
| M2 Runner and grader v0 | done | `wcb run`, `wcb score`, store integrity (SIS), `wcb doctor`, metered runs. Null and store-reader baselines behave as expected (below). LLM baselines not yet run (see Open items). |
| M3 Generator v1 | done | Planner, simulator, renderers, verifier, oracle store, question generator ([generator](generator.md)). Generated worlds check clean, are byte-deterministic across hash seeds, and pass a faithfulness audit (asks answered by their debtor, no restatement after a loop closes, no message before its event). Answers built from gold score at least 0.95 on every question of every generated world. Deviations from [calibration targets](calibration.md) are listed in the generator docs. |
| M4 Judge and calibration | calibrated, human labels pending | `wcb judge sample / label / run / agreement` ([judges](judge.md#measuring-judge-agreement)) and a committed calibration set of real and adversarial answers ([judges](judge.md#calibration)). The milestone's criterion is judge-vs-human agreement, which needs people to label the prepared sample. |
| M5 Dev release | done; first agent run recorded | Ten dev worlds (1-, 2- and 4-week; small, standard, large; five settings), public gold, reference adapters, deterministic scoring with the heuristic judge. |
| M6 Test set and leaderboard | tooling done | `scripts/make_test_split.py` (secret seeds, published commitments, `--verify`), `wcb bundle`, metered runs, container adapter, [submission docs](leaderboard.md). No test split released and no external submission yet. |

## Worlds

| World | Setting | Weeks | Size | Episode days | Checkpoints | Artifacts | Questions |
|---|---|---|---|---|---|---|---|
| `pilot` | university system (hand-authored) | 1 | — | 6 | 3 | 127 | 52 |
| `dev/gen-s1-w1` | city government | 1 | standard | 6 | 3 | 295 | 45 |
| `dev/gen-s2-w1` | city government | 1 | standard | 5 | 3 | 291 | 45 |
| `dev/gen-s3-w1` | health network | 1 | standard | 6 | 3 | 294 | 45 |
| `dev/gen-s4-w2` | university system | 2 | standard | 12 | 6 | 406 | 90 |
| `dev/gen-s5-small` | health network | 1 | small | 6 | 3 | 209 | 33 |
| `dev/gen-s6-w1` | university system | 1 | standard | 6 | 3 | 287 | 45 |
| `dev/gen-s7-w2` | university system | 2 | standard | 12 | 6 | 392 | 90 |
| `dev/gen-s8-w4` | manufacturer | 4 | standard | 24 | 12 | 589 | 180 |
| `dev/gen-s9-large` | health network | 1 | large | 6 | 3 | 349 | 54 |
| `dev/gen-s10-w2-small` | nonprofit federation | 2 | small | 11 | 6 | 269 | 66 |

745 questions in all. Every world passes `wcb world check` with no issues and has no findings from the privacy scan against the private source repository (`wcb privacy scan`, [privacy](privacy.md)). Dev worlds regenerate identically from `scripts/make_dev_worlds.py`; they were regenerated on 2026-11-11 so that project summaries track decisions that change scope ([issue #8](https://github.com/vivekhaldar/white-collar-bench/issues/8)). Inputs did not change; 33 questions did.

On 2026-11-12, the dev worlds were regenerated again to refresh 40 stale `challenges` annotations after the rubric changes ([issue #13](https://github.com/vivekhaldar/white-collar-bench/issues/13)). `GOLD_VERSION` 5 records this annotation-only refresh: inboxes, question IDs/parameters/text, expected answers and supporting evidence are unchanged from version 4. Only challenge-specific score groupings can change; no agent rerun is needed. The original Qwen and DeepSeek result records remain unchanged and have not been regraded as part of this refresh.

## Baselines

Measured on all 11 worlds, one repeat, heuristic judge, `GOLD_VERSION` 4. Version 5 changes only challenge annotations, so headline scores are unaffected. Reproduce with:

```bash
wcb run --adapter adapters/examples/null.yaml --world pilot --split dev --out runs/null
wcb run --adapter adapters/examples/store-reader.yaml --world pilot --split dev --skip-ingest --out runs/store-reader
wcb score runs/null && wcb score runs/store-reader
```

| Baseline | WCB | Synthesis (oracle store) | SIS | Pilot | Dev worlds |
|---|---|---|---|---|---|
| Null (abstains everywhere, never edits the store) | 12.7 | 12.7 | 91.5 | 12.5 | 12.5–13.9 |
| Store reader, oracle stores only (`--skip-ingest`) | n/a | 85.2 | n/a | 49.1 | 86.2–95.8 |

By question type, the store reader scores: point 84, list 96, status 93, brief 95, change 88, temporal 27, priority 100, unanswerable 100. Status rose from 63 under `GOLD_VERSION` 3 because status rubrics no longer grade an arbitrary pick of loops or a minor loop event as the latest change (see below). It is a pipeline check, not a competitor: it reads the oracle store with fixed rules and string patterns.

What the numbers show:

- **The floor is low.** Abstaining everywhere earns only the unanswerable bucket, about 1/8 of the macro average.
- **Oracle stores carry what the questions need**, so Synthesis on an oracle store measures answering, not missing gold.
- **The pilot resists pattern-matching.** Its hand-written questions ("Who at Pen Mark owes us the three-campus pricing?") defeat the store reader's regexes (48.6), while generated questions, written from templates, let it reach 86–96 on a correct store. Reading the right record is not the hard part of the benchmark; keeping the store correct is, and only an ingesting agent is measured on that.
- **SIS is lenient by design.** An untouched Track A seed store stays valid and grounded, so it scores 91.5. Read SIS against the null baseline, not against 0.

## First agent run

Qwen3.8-27B in the Pi harness ran all 11 worlds on both tracks on 10–11 November 2026 under `GOLD_VERSION` 3 and scorer v0.1: Track A 72.3 (Synthesis 84.3, SIS 98.4), Track B 55.0 ([report](../results/2026-11-11-qwen3.8-27b-pi/README.md)). Its audit filed issues #3–#11 against the runner, gold and scorer. All have been addressed since:

| Issue | Fix |
|---|---|
| #3, #4 point answers with context; dates | Context from the subject's own record is not counted as extra words; a date at the start of `value` is the answer. Point answers may carry an ungraded `note`, and the query prompt now says `value` holds only the answer. |
| #5, #6 runner integrity | `tree_diff` compares current bytes; runner git commits never start background maintenance. |
| #7 citations | List and change citations are checked against the matched gold item; support is widened along each item's event thread. |
| #8 stale summaries | Project summaries track decisions that change scope; dev worlds regenerated. |
| #9 pilot perfect answer | History labels after a stale value are read; every gold-derived perfect answer now scores exactly 1. |
| #10 rubric calibration | Item-local coverage replaces the answer-wide focus cliff, plus a bounded padding penalty; status rubrics grade the latest project-level change and only dated loops when there are many. Human labels still pending. |
| #11 runtime | Sessions record why the agent stopped (`termination`, `incomplete`) and how many store files changed; the reference Docker image ships pinned document readers. |

Its scores have not been regraded: that needs the run's raw answers and stores, which are in archives outside the repository. `scripts/regrade_points.py` regrades the 75 zero-scored point answers saved in its evidence files. Before the dev worlds were regenerated, 22 were credited, each checked by hand; on the regenerated worlds 6 of those questions changed, and 20 of the remaining 69 are credited.

## Judge agreement

**Calibration set** (`tests/fixtures/judge-calibration/`, [judges](judge.md#calibration)): 258 decisions (179 rubric, 79 `same_item`), 71 of them real agent prose from the Qwen run and the rest honest paraphrases and adversarial controls, each labelled against the sources and gold state. 100 also carry an LLM label (Claude through `claude -p`, one sample each).

| Agreement (Cohen's κ) | n | Before the 2026-11-11 changes | After |
|---|---:|---:|---:|
| rubric: heuristic vs hand labels | 179 | 0.61 | 0.87 |
| rubric: heuristic vs LLM | 55 | 0.53 | 0.78 |
| rubric: LLM vs hand labels | 55 | | 0.94 |
| `same_item`: heuristic vs hand labels / vs LLM | 79 / 45 | 0.60 / 0.73 | unchanged |

**Earlier measurement.** On decisions from the store reader's rule-based answers, the heuristic agreed with the LLM judge at κ 0.93 (`same_item`) and 0.97 (`rubric`), n = 60 each. Those answers are much cleaner than an agent's, and the calibration set shows that number overstated agreement on real agent prose.

`same_item` matching is the weaker judge: its errors are mostly false negatives on paraphrases, and the fixes tried so far created more false positives than they removed. To finish M4, two people label `tests/fixtures/judge-calibration/human-sample.jsonl` with `wcb judge label`, and the pinned judge for the release is compared with both.

## Open items

- **More agent runs.** One agent run is recorded (Qwen3.8-27B in Pi). Raw retrieval, the simple harness and the reference CLI agents (Claude Code, Codex) still need runs, with several repeats.
- **Regrade the Qwen run** under `GOLD_VERSION` 4 once its raw archives are available.
- **Human labels for judge agreement** (M4), and pinning the LLM judge model for the first release.
- **Practitioner realism review** (`scripts/realism_packet.py` draws a blind sample with a score sheet) of the pilot and of a sample of generated artifacts ([privacy](privacy.md#release-gate) also asks for a manual skim before a release).
- **Generated prose is template-based.** `wcb generate --llm` rewrites prose with a model and verifies it, but has not been run at scale.
- **Generated questions are formulaic** (see Baselines). Rewriting question text with an LLM, or more hand-written phrasings, would make test worlds harder to pattern-match.
- **Pilot instruction-resistance line.** Generated worlds each plant one instruction-like line in an input; the pilot has none.
- **Scoring design questions raised in review and left as specified:** the unanswerable bucket weighs as much as each answer type; SIS gives credit to untouched or nearly empty stores; the bootstrap interval is over worlds only.
- **Known heuristic limits** are listed in [judges](judge.md), including the calibration set's 29 documented disagreements. `same_item` paraphrase false negatives and entity point answers with narration are the largest remaining sources of grading error.
- **First release:** generate the private test split, publish its commitments, and score a first external submission (M6).
