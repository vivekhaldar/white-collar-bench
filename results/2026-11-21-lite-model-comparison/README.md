# Four models on WCB-lite: Haiku, Sonnet and Opus 5.5, GPT-6.1 Sol (Pi harness)

## Panel provenance and publication status

The latest verified comparison with the configured cross-family panel is the gold v6 study below. The gold v14 table at commit `070f12e` and the existing deck used a different panel for changed prompts. Those numbers are historical diagnostics and are withdrawn as release headlines.

For gold v14, original cached decisions came from Claude Sonnet 5.5 and GPT-6.1 Sol. GPT-6 Luna and GPT-6.1 Sol decided new prompts in a ChatGPT session, and GPT-6 Sol resolved persistent citation splits. The historical votes and per-question baseline are retained for comparison. The current regression command uses only Claude Sonnet 5.5 and GPT-6.1 Sol. A citation must receive cross-family agreement, including on the second reading. The release uses no referee.

The corrected comparison awaits the configured panel's raw responses. Fill the shared cache with `python scripts/lite_regression.py --allow-calls`, then run offline to compare every changed question against the historical baseline. A replacement baseline requires zero missing votes on every arm.

## Original gold v6 study


**Graded for substance (gold v6 and a cross-family judge panel), Opus 5.5 leads on both tracks (A 91.9, B 87.4). Sonnet 5.5, Haiku 5.5 and GPT-6.1 Sol are within 2 points of each other on Track A (87.0–89.1), with overlapping confidence intervals.** Haiku costs $3.53 per lite run, a fifth of Sonnet's cost. Track B, where the model designs its own memory, separates the models most: Opus loses 4.5 points there, the others 7–10.

All four runs used the same harness (Pi 1.5.2 with the `pi_litellm.py` wrapper), the same [WCB-lite suite](../../docs/lite.md) (11 public worlds, two episode days, one repeat), medium reasoning effort and a LiteLLM proxy. They are the closest thing to a controlled model comparison in `results/`. All worlds, people and organizations are synthetic.

Per-run reports: [Haiku and Sonnet](../2026-11-21-claude-5.5-pi-lite/README.md), [Opus](../2026-11-21-claude-opus-5.5-pi-lite/README.md), [Sol](../2026-11-21-gpt-6.1-sol-pi-lite/README.md). The deck for presenting these results is [`slides/index.html`](slides/index.html) (PDF: [`slides/wcb-lite-results.pdf`](slides/wcb-lite-results.pdf)). It also shows DeepSeek V4.1 Flash and Qwen3.8-27B, whose earlier full runs are rescored as lite from their saved reports with the older grader; their raw answers are not available, so they could not be regraded.

## Scores

Gold v6 with the panel judge (headline), on the same saved answers:

| Model | Lite A | Lite B | 95% CI A | 95% CI B | Micro A | Micro B | Synthesis | Ingestion cost | Heuristic only, A / B | Lite $ |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|
| Opus 5.5 | **91.9** | **87.4** | 88.1–94.9 | 83.3–90.6 | 92.3 | 85.9 | 96.6 | **4.7** | 88.0 / 76.1 | 56.93 |
| Sonnet 5.5 | 89.1 | 80.7 | 84.7–92.8 | 76.1–84.9 | 89.9 | 78.1 | 96.2 | 7.1 | 85.5 / 74.2 | 17.24 |
| Haiku 5.5 | 88.8 | 78.3 | 86.5–91.2 | 75.4–81.6 | 89.9 | 81.7 | 94.8 | 6.0 | 84.6 / 67.3 | **3.53** |
| GPT-6.1 Sol | 87.0 | 79.9 | 83.2–90.7 | 73.3–84.7 | 89.3 | 78.2 | 94.8 | 7.8 | 78.0 / 64.9 | 10.72 (flex) |

*Synthesis* is the Track A score answering from the perfect oracle store; *ingestion cost* is Synthesis minus Track A. *Lite $* is the cost of the model under test, including Track A oracle sessions, before grading. Sol is billed at OpenAI's flex tier, half of its $21.44 list price.

- **Opus is clearly first on Track B** (87.4; next is Sonnet at 80.7, intervals barely touching) and first on A. The other three are statistically tied on A.
- **Answering from a perfect memory is nearly solved:** every model scores 94.8–96.6 from the oracle store. What separates them is the memory they build.
- **Sol gained the most from grading for substance** (A 78.0 → 87.0 heuristic → panel; B 64.9 → 79.9). Its answers are the longest and hedge most (contract rule 7), which word matching punished.

## Grading changes and rescoring

The same saved answers were scored with four graders. The [deck](slides/index.html) charts all four.

| Model | Original A / B | Judge fixes `ec9ff3d` | Gold v6, heuristic | Gold v6 + panel |
|---|---|---|---|---|
| Haiku 5.5 | 81.4 / 64.7 | 82.8 / 65.3 | 84.6 / 67.3 | 88.8 / 78.3 |
| Sonnet 5.5 | 83.8 / 71.1 | 85.4 / 71.3 | 85.5 / 74.2 | 89.1 / 80.7 |
| Opus 5.5 | 82.5 / 67.3 | 87.5 / 72.4 | 88.0 / 76.1 | 91.9 / 87.4 |
| GPT-6.1 Sol | 69.3 / 58.5 | 75.3 / 62.3 | 78.0 / 64.9 | 87.0 / 79.9 |

1. **Judge fixes (`ec9ff3d`).** Date-history chains (\"moved from 15 Dec to 22 Dec on 8 Nov, then to 31 Dec\") no longer read as stale dates, and the item matcher ignores acceptance hedges (\"confirm whether you can…\"). 65 answers rose, none fell.
2. **Gold v6** ([scoring](../../docs/scoring.md#query-scoring)). It needs no new runs; it only changes how gold marks items:
   - *Optional loops.* A suggestion nobody accepted, or an ask the worker owes only because someone requested it with no reply from the worker, is defensible either way under contract rule 7. Such items are now `optional`: neither required nor wrong. 43 of 144 lite list items and 9 of 104 change items are optional.
   - *Project status.* An \"X is active\" rubric item is covered by an answer that gives no other status (\"in build\", \"in security review\").
   - *Citations.* For status, brief and point answers, a delivered artifact about the question's subject counts even when it is outside the minimal gold support.
3. **Panel judge** ([judges](../../docs/judge.md#panel-judge)). The heuristic decides first; every negative decision goes to Claude Sonnet 5.5 and GPT-6.1 Sol, and is overturned only when both agree. So no family grades its own models alone. Free-text point answers the deterministic rules reject (a relationship described as \"a colleague in my own org\" for `peer`) go to the panel too.

**Spot check of the panel.** On Opus Track B the panel overturned 89 heuristic decisions. Reading about 40, most are clearly right: correct items with explanation attached, \"in security review\" for an active project, \"colleague in my own org\" for `peer`. A few are lenient, for example an item naming the right deliverable with the wrong owner (\"Bisi to send the term sheet\" for \"Send Alasdair the Rosix term sheet\"). Report the heuristic score next to the panel score.

### Judging cost

| Run graded | Panel calls (Sonnet + Sol) | Cost, A + B |
|---|---:|---:|
| Haiku 5.5 | 4,692 | $3.88 |
| Sonnet 5.5 | 3,906 | $3.24 |
| Opus 5.5 | 4,818 | $3.81 |
| GPT-6.1 Sol | 5,088 | $4.33 |
| **Total** | **18,504** | **$15.26** ($18.18 at list) |

That is 6.6M tokens (6.0M input, 0.6M output): Sonnet 3.6M in / 0.5M out at $12.34, Sol 2.4M in / 0.1M out at $2.92 (flex). Grading adds 7% to Opus's run cost and 110% to Haiku's. Token counts are estimated, not metered: the judge client does not record usage, so prompt characters were converted with tokens-per-character and mean output tokens measured on 30 real calls per model ([`judge-cost.json`](judge-cost.json)). The first panel pass also judged the store-integrity check (SIS), which does not enter the WCB headline, before it was switched back to the heuristic: about 46,000 wasted Sonnet calls, an estimated $61 and 20M tokens. Total spent on judging: about $76.

Rescored reports are in [`rescored/`](rescored/): the `ec9ff3d` reports at the top level, `v6-heuristic/` and `v6-panel/` (with the gzipped decision caches, so the panel scores can be reproduced without model calls).

## How the models differ

| | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 | GPT-6.1 Sol |
|---|---:|---:|---:|---:|
| Median turns per ingest day | 20 | **6** | 10 | 16 |
| Median output tokens per ingest day | 37.5k | **7.6k** | 12.2k | 12.0k |
| Median wall time per ingest day | 171 s | **51 s** | 105 s | 158 s |
| Total tokens, lite (incl. cache reads) | 109M | **18M** | 41M | 38M |
| Summed session time, lite | 3.9 h | **1.3 h** | 2.7 h | 3.4 h |
| New loops recorded as unaccepted (Track A) | 20.9% | 14.1% | 15.2% | **24.3%** |
| Median words in a status answer (A / B) | 127 / 203 | **97 / 101** | 166 / 183 | 160 / 250 |
| Median content words per list item (A / B) | 7 / 9 | **6 / 7** | 7 / 8 | 10 / 13 |

- **Sonnet is the most economical agent:** few turns, short output, short answers. It plans a day's ingestion in about six tool calls.
- **Haiku is cheap per token but not per task.** It takes 3× Sonnet's turns and 5× its output, reading files piece by piece. Low prices still make it the cheapest run by far, and it was slower than Sonnet in wall time.
- **Opus writes more than Sonnet and keeps the best memory.** Its answers are long and explanatory, which helps on change questions (best of the four) and hurts where the strict matcher reads explanation as a different item (Track B priority).
- **Sol is the most literal and the most verbose.** It follows contract rule 7 most strictly, writes the longest answers and list items, and has the weakest store (ingestion cost 12.1).

## Why the best model is not near 100

An [audit of every point Opus lost under the old grader](../2026-11-21-claude-opus-5.5-pi-lite/ERROR-AUDIT.md) found its own errors cost only about 2.3 points on A and 2.8 on B; the rest was the heuristic grader, arguable gold and citation penalties. Gold v6 and the panel address the grader and the two clearest gold ambiguities, and Opus now scores 91.9 / 87.4. What remains is its real errors, citation penalties and change questions.

## What all four get wrong

- **Change questions are still the weakest type for every model:** 0.62–0.74 on A, 0.57–0.75 on B. Answers fold several events into one item, and one-to-one matching credits it once.
- **The pilot world is the hardest for every model.** It is hand-authored, with dense hand-offs, corrections and an offsite day that moves everything.
- **Track B lists lose loops:** list scores fall from 0.84–0.90 on A to 0.69–0.82 on B. Without the contract's loop records, models forget commitments made in passing.
- **None of them invents answers.** Unanswerable questions score 1.00 for every model on both tracks, and temporal questions 0.95–1.00.

## Reproduction

- `python results/2026-11-21-lite-model-comparison/compare.py > results/2026-11-21-lite-model-comparison/data.json` collects every number above from the raw runs (`runs/`, git-ignored) and their original and rescored reports.
- Rescoring a run: `wcb score <run>/track-<t>/measured --suite lite --judge panel --out <run>/track-<t>/scores-v6-panel-lite` (with `OPENAI_BASE_URL` and `OPENAI_API_KEY` pointing at a proxy that serves both panel models). Copy the matching `rescored/v6-panel/judge-cache-*.jsonl.gz`, unzipped, to `<out>/judge-cache.jsonl` first to reuse the decisions.
- `slides/build.py` renders the deck's charts from `data.json`.

## Regression harness for grader and gold fixes

`regression/lite-runs.tar.gz` (4 MB) packs what scoring reads from the eight lite runs: answers, `run.json`, and each episode's checkpoint snapshot. With the panel caches in `rescored/v6-panel/`, `python scripts/lite_regression.py` rescores all eight with the current grader and gold, **without model calls**, and lists every question whose score changed against `regression/baseline.json`. It re-derives each judge decision from the cached raw outputs, so parser changes take effect too. GitHub issues #16–#30 state the expected changes for each fix.

`failure-classes.json` holds the per-run split of remaining loss into model causes (ingest, select, attribution) and benchmark causes (gold, grader, granularity, citation) from the failure analysis of the 60 costliest questions (91% of loss).
