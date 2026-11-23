# Historical residual loss on gold v14

All eight arms use the original saved answers. Headline points use the regression harness’s world, checkpoint and question-bucket weights. All quantities below sum over the eight arms unless noted.

## Failure classification

The 60 costliest world/checkpoint/questions account for 96.3% of the remaining 82.69 headline points. GPT-6.1 Sol assigned the base-score loss for each imperfect answer in this group using the source dossier and archived workspace. For mixed cases it apportioned the loss. The remaining difference between base and final score is assigned to citations. Questions outside the top 60 are unclassified. The 73.4% benchmark-side share is indicative. GPT-6.1 Sol was both the sole classifier and one of the four graded models. No independent family reviewed its classifications or measured agreement. The estimate describes the historical mixed-panel replay. These are model judgments, with uncertainty particularly around ingestion versus answer selection.

| Cause | Headline points |
|---|---:|
| GOLD | 32.75 |
| GRADER | 22.20 |
| SELECT | 12.86 |
| GRANULARITY | 4.81 |
| INGEST | 3.97 |
| UNLABELLED | 3.08 |
| JUDGE_ENTITY | 2.12 |
| CITATION | 0.90 |

[Per-answer classifications](loss-classification.csv) · [Original gold v6 totals](../failure-classes.json)

## Review of scoring assumptions

The v14 relationship shortcuts included language copied verbatim from saved answers, such as “cross-portfolio colleague and collaborator.” On the corrected grader, unambiguous short forms still receive deterministic credit. Descriptions that require interpreting the relationship go to the point panel with definitions of all contract labels. The v14 audit predates this change.

Commit `0bd01bf` was motivated by the pilot hosting example. The rule uses an explicit causal phrase in a dropped loop’s summary (“superseded by” or “after choosing”), a unique decision on the same project at the same timestamp, and matching decision keywords. When neither fact initially matches, one answer must cite shared evidence and explicitly state both the decision and its outcome. It contains no project, date, event ID or option specific to the pilot. Its dependence on those causal phrases can still miss other ways of reporting a cancellation.

## Bundled changes

Disabling linked-event matching while holding the rest of the scorer fixed reduces 47 of the 88 change-answer base scores and increases none. All eight Corrie answers benefit. Sol separately inspected 71 archived imperfect change answers from the pre-pilot-fix replay. The audit lists additional matches which split a single fact or reported it alongside another. We checked those matches against the final assignments and recalculated F1, holding citation precision fixed. The estimated remaining loss from linked events is 0.74 headline points. Including unrelated events bundled into one prediction gives 3.53. The control in #23 deliberately prevents one prediction from covering unrelated threads. This calculation measures change-question matching directly. The top-60 loss classification above also considers other question types.

[Bundled-event audit](granularity-audit.csv)

## Disputed citations

The seeded sample contains 50 residual citation occurrences across all eight arms, including otherwise incorrect answers. A separate Codex evidence review considered the full source and the specific claim. The evidence review found 1 ambiguous, 34 genuinely wrong, 15 reasonable. The sheet gives each claim, reference and rationale. Reproduce the selection with `python scripts/lite_regression.py --citation-sample sample.json`.

[Citation audit](citation-audit.csv)

| Priority question | Mean citation precision, gold v6 | Mean citation precision, gold v14 |
|---|---:|---:|
| gen-s9-large/cp1/q-001 | 68.1% | 99.2% |
| gen-s10-w2-small/cp1/q-001 | 82.4% | 100.0% |

## Score decreases from gold v6

Making an item optional removes it from the scoring denominator. This can lower the score of an answer that covered the optional item and missed a required one, or that lists an additional closed or transferred task. Correcting a suggestion to its original wording also changes what the judges accept. Removing the disputed blocker from a status rubric changes the relative weight of the remaining facts. The table shows each decline and separates the base score from citation precision. A dash means citation precision did not apply.

| Run | World and question | Base score | Citation precision | Final score |
|---|---|---:|---:|---:|
| haiku-a | gen-s9-large/q-003 | 0.444 → 0.333 | 0.727 → 1.000 | 0.414 → 0.333 |
| haiku-b | gen-s2-w1/q-004 | 0.667 → 0.000 | 0.375 → 1.000 | 0.562 → 0.000 |
| haiku-b | gen-s9-large/q-003 | 0.667 → 0.400 | 0.500 → 1.000 | 0.583 → 0.400 |
| opus-a | gen-s5-small/q-002 | 0.769 → 0.727 | 0.867 → 1.000 | 0.744 → 0.727 |
| opus-a | gen-s9-large/q-003 | 0.889 → 0.800 | 0.900 → 1.000 | 0.867 → 0.800 |
| opus-b | gen-s2-w1/q-003 | 0.900 → 0.824 | 0.867 → 1.000 | 0.870 → 0.824 |
| opus-b | gen-s9-large/q-002 | 0.778 → 0.714 | 0.947 → 1.000 | 0.767 → 0.714 |
| opus-b | gen-s9-large/q-003 | 0.800 → 0.667 | 0.667 → 1.000 | 0.733 → 0.667 |
| sol-a | gen-s9-large/q-003 | 0.800 → 0.667 | 0.769 → 1.000 | 0.754 → 0.667 |
| sol-b | gen-s2-w1/q-004 | 0.667 → 0.000 | 0.500 → 1.000 | 0.583 → 0.000 |
| sol-b | gen-s5-small/q-002 | 0.572 → 0.502 | 0.895 → 1.000 | 0.556 → 0.502 |
| sol-b | gen-s9-large/q-003 | 0.444 → 0.333 | 0.375 → 1.000 | 0.375 → 0.333 |
| sonnet-a | gen-s5-small/q-002 | 0.692 → 0.636 | 1.000 → 1.000 | 0.692 → 0.636 |
| sonnet-b | gen-s2-w1/q-003 | 0.444 → 0.400 | 0.643 → 1.000 | 0.405 → 0.400 |
