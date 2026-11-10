# Status

Where the benchmark stands against the [construction plan](plan.md#5-milestones), with measured numbers. Updated 2026-11-10 for wcb 0.1.0, `GOLD_VERSION` 3.

## Milestones

| Milestone | State | Notes |
|---|---|---|
| M0 Specs | done | Track A [contract](../contract/CONTRACT.md) v1.0, world, question and answer [formats](formats.md), [adapter protocol](adapters.md), store validator (`wcb validate`). |
| M1 Pilot world | done, awaiting practitioner review | Hand-authored one-week world (below). Gold is computed by `wcb world build` from the hand-written event log, not written by hand. Artifacts were checked against the gold batch by batch and reconciled across threads; a realism read by someone who does this work is still to do. |
| M2 Runner and grader v0 | done | `wcb run`, `wcb score`, store integrity (SIS), `wcb doctor`, metered runs. Null and store-reader baselines behave as expected (below). LLM baselines not yet run (see Open items). |
| M3 Generator v1 | done | Planner, simulator, renderers, verifier, oracle store, question generator ([generator](generator.md)). Generated worlds check clean, are byte-deterministic across hash seeds, and pass a faithfulness audit (asks answered by their debtor, no restatement after a loop closes, no message before its event). Answers built from gold score at least 0.95 on every question of every generated world. Deviations from [calibration targets](calibration.md) are listed in the generator docs. |
| M4 Judge and calibration | tooling done, human labels pending | `wcb judge sample / label / run / agreement` ([judges](judge.md#measuring-judge-agreement)). Heuristic-vs-LLM agreement is measured (below); the milestone's criterion is judge-vs-human agreement, which needs people to label a sample. |
| M5 Dev release | done except LLM baselines | Ten dev worlds (1-, 2- and 4-week; small, standard, large; five settings), public gold, reference adapters, deterministic scoring with the heuristic judge. |
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

745 questions in all. Every world passes `wcb world check` with no issues and has no findings from the privacy scan against the private source repository at any severity (`wcb privacy scan`, [privacy](privacy.md)). Dev worlds regenerate identically from `scripts/make_dev_worlds.py`.

## Baselines

All 11 worlds, one repeat, heuristic judge. Reproduce with:

```bash
wcb run --adapter adapters/examples/null.yaml --world pilot --split dev --out runs/null
wcb run --adapter adapters/examples/store-reader.yaml --world pilot --split dev --skip-ingest --out runs/store-reader
wcb score runs/null && wcb score runs/store-reader
```

| Baseline | WCB | Synthesis (oracle store) | SIS | Pilot | Dev worlds |
|---|---|---|---|---|---|
| Null (abstains everywhere, never edits the store) | 12.7 | 12.7 | 91.5 | 12.5 | 12.5–13.9 |
| Store reader, oracle stores only (`--skip-ingest`) | n/a | 81.6 | n/a | 48.6 | 81.9–92.5 |

By question type, the store reader scores: point 84, list 96, status 63, brief 95, change 90, temporal 27, priority 100, unanswerable 100. It is a pipeline check, not a competitor: it reads the oracle store with fixed rules and string patterns.

What the numbers show:

- **The floor is low.** Abstaining everywhere earns only the unanswerable bucket, about 1/8 of the macro average.
- **Oracle stores carry what the questions need**, so Synthesis on an oracle store measures answering, not missing gold.
- **The pilot resists pattern-matching.** Its hand-written questions ("Who at Pen Mark owes us the three-campus pricing?") defeat the store reader's regexes (48.6), while generated questions, written from templates, let it reach 82–93 on a correct store. Reading the right record is not the hard part of the benchmark; keeping the store correct is, and only an ingesting agent is measured on that.
- **SIS is lenient by design.** An untouched Track A seed store stays valid and grounded, so it scores 91.5. Read SIS against the null baseline, not against 0.

## Judge agreement

`wcb judge` samples of decisions from the store-reader runs, labelled by the heuristic judge and by an LLM judge (Claude through `claude -p`, one sample per decision). The first samples were used to find and fix heuristic and gold errors (items matched on a shared project name; loop checklist items covered by naming the project). The final sample excludes every decision seen before:

| Decision | n | Agreement | Cohen's κ |
|---|---|---|---|
| `same_item` | 60 | 97% | 0.93 |
| `rubric` | 60 | 98% | 0.97 |

Caveats: these decisions come from rule-based answers on oracle stores, which are cleaner than an agent's; the LLM judge used one sample, not the pinned three; and M4's criterion is agreement with people. To finish M4, two people label the same sample with `wcb judge label`, and the pinned judge for the release is compared with both.

## Open items

- **LLM baselines.** Raw retrieval, the simple harness and the reference CLI agents need model API keys; none have been run yet. These are the first real leaderboard rows.
- **Human labels for judge agreement** (M4), and pinning the LLM judge model for the first release.
- **Practitioner realism review** of the pilot and of a sample of generated artifacts ([privacy](privacy.md#release-gate) also asks for a manual skim before a release).
- **Generated prose is template-based.** `wcb generate --llm` rewrites prose with a model and verifies it, but has not been run at scale.
- **Generated questions are formulaic** (see Baselines). Rewriting question text with an LLM, or more hand-written phrasings, would make test worlds harder to pattern-match.
- **Pilot instruction-resistance line.** Generated worlds each plant one instruction-like line in an input; the pilot has none.
- **Scoring design questions raised in review and left as specified:** the unanswerable bucket weighs as much as each answer type; SIS gives credit to untouched or nearly empty stores; the bootstrap interval is over worlds only.
- **Known heuristic limits** are listed in [judges](judge.md); one pilot status item ("the 78/74 ... were v1 totals") is marked contradicted even in a perfect answer.
- **First release:** generate the private test split, publish its commitments, and score a first external submission (M6).
