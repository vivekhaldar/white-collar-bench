# Reduced suites: WCB-lite and WCB-micro

Status: v0.1. A full run is expensive: on the public worlds it costs about $110 for one repeat of Tracks A and B with DeepSeek V4.1 Flash, and far more with a frontier model. The reduced suites give most of the signal about how one harness or model compares with another for a fraction of that cost. They are for development and comparison. They are not leaderboard results.

```bash
wcb run --adapter adapters/my-agent.yaml --suite lite --track A --out runs/my-agent-lite-a
wcb run --adapter adapters/my-agent.yaml --suite lite --track B --out runs/my-agent-lite-b
wcb score runs/my-agent-lite-a        # headline: "WCB-lite score (Track A)"

wcb score runs/my-full-run --suite lite --out runs/my-full-run/scores-lite   # a full run, as lite
```

| Suite | Worlds | Days | Questions | Cost vs full | Use |
|---|---|---:|---:|---:|---|
| `micro` | pilot, gen-s1-w1, gen-s4-w2, gen-s5-small, gen-s9-large | 2 | 73 | ~10% | Harness iteration and regression checks |
| `lite` | all 11 public worlds | 2 | 159 | ~21% | Harness or model comparisons you report |
| full | all 11 public worlds | all (5–24) | 745 | 100% | Reported results; the leaderboard |

The suites are defined in [`wcb/suites.py`](../wcb/suites.py). Both play the first two episode days of each world. Day 2 is every world's first checkpoint (cp1), so a suite run asks only cp1's questions. Track A still runs its oracle sessions, so Synthesis, Ingestion cost and SIS are reported as usual, over the days played.

## Rules

- **Compare only within a suite.** A suite score is labelled `WCB-lite` or `WCB-micro` in `report.json` (`headline.label`, `headline.suite`), `report.md` and `wcb score`'s output. It is about 1–3 points higher than the full WCB score of the same run, because errors have had only two days to compound (see the measurements below). A WCB-lite score is never a WCB score.
- **Suites are frozen.** Changing a suite's worlds or day count would make old scores incomparable, so a change gets a new suite name.
- **A suite is a prefix-subset of a full run.** `wcb score --suite NAME` rescores any full run (or a longer run) as that suite. It keeps the suite's worlds, the checkpoints within its first days, and the sessions of those days for efficiency. Every full run therefore also yields lite and micro scores at no cost. Do this for every full run you make: it keeps the calibration in [Measured fidelity](#measured-fidelity) growing.
- `wcb run --suite` sets the worlds and `--max-days`; combining it with `--world`, `--split` or `--max-days` is an error. `--repeats`, `--track`, `--meter` and every other option work as usual. A resumed run stays a suite run only if every invocation used the same suite.

### Suggested protocol for a comparison

1. Run `micro` for the baseline and the candidate with the same adapter settings, Tracks A and B.
2. If the difference is well above the noise (see below), stop. Otherwise run `lite`.
3. If `lite` is still inconclusive, or the result will be published, run the full benchmark.

Noise between repeats has not been measured yet: every result so far is one repeat. Until it is, treat lite differences under about 3 points and micro differences under about 5 as ties.

## Why these suites

Where the cost goes, from the DeepSeek V4.1 Flash run (agent and oracle sessions, Tracks A and B together):

| Sessions | Cost | Share |
|---|---:|---:|
| Ingestion | $90.1 | 76% |
| Agent queries | $20.2 | 17% |
| Oracle queries (Track A) | $8.5 | 7% |

- **Input tokens are almost all of the cost.** An ingestion session reads about 4M input tokens in Track A and 8.7M in Track B, against about 50k output tokens. The agent rereads its store and the day's inputs many times per session.
- **Days, not questions, are the unit of cost.** A checkpoint's questions are one query session, so dropping questions saves under 5%. Dropping days saves almost proportionally. The 4-week world (gen-s8-w4) alone is 29% of the run.
- **Breadth beats depth.** Most of the variance in a run is between worlds, so a fixed budget is better spent on more worlds at a short horizon than on fewer worlds at a long one.

Options considered and not taken:

| Option | Why not |
|---|---|
| Fewer questions | Saves under 5%: questions are not what costs money. |
| Synthesis only (`--skip-ingest`) | Already exists and costs about 7%, but measures none of ingestion, which is what the benchmark is about. Use it while working on the query side. |
| Ingestion only, graded by SIS | SIS is saturated: the null agent scores 91.5 and both measured agents 98–99, so it separates nothing. |
| Fewer worlds at full length | For the same cost, much worse fidelity (table below). |
| Smaller generated worlds | Would need its own calibration and would not be comparable with full runs. |

### What the suites cannot see

Two days are not enough for errors to compound over weeks, and the suites miss failures that happen later in an episode. In the DeepSeek run, all 4 ingestion sessions that hit the turn budget (and were rolled back, losing that day) were on day 4 or later (pilot days 4 and 5, gen-s7-w2 day 11); neither suite would have shown them. When a change targets long-horizon behaviour (budgets, store growth, finishing a session cleanly), run the full benchmark. In suite runs, read the efficiency section for incomplete or failed sessions and for the number of turns used against the budget.

## Measured fidelity

Measured on the two committed runs ([results](../results/README.md)) by rescoring each as each suite. The script is [`scripts/suite_fidelity.py`](../scripts/suite_fidelity.py); it needs no model calls:

```bash
python scripts/suite_fidelity.py results/2026-11-11-deepseek-v4.1-flash-1017-pi results/2026-11-11-qwen3.8-27b-pi
```

Costs are the runs' recorded agent-session costs (ingestion and agent queries; Track A oracle sessions excluded) at each provider's rates.

| Run | Track | Full | Lite | Micro | Full $ | Lite $ | Micro $ |
|---|---|---:|---:|---:|---:|---:|---:|
| DeepSeek V4.1 Flash / Pi | A | 84.6 | 87.0 | 86.1 | 45.81 | 9.31 | 4.24 |
| DeepSeek V4.1 Flash / Pi | B | 67.5 | 69.8 | 70.6 | 64.49 | 13.90 | 6.54 |
| Qwen3.8-27B / Pi | A | 72.3 | 75.3 | 74.8 | 57.47 | 12.17 | 6.13 |
| Qwen3.8-27B / Pi | B | 55.0 | 55.7 | 55.3 | 59.45 | 15.58 | 6.86 |

The gaps a comparison relies on:

| Gap | Full | Lite (error) | Micro (error) |
|---|---:|---:|---:|
| DeepSeek − Qwen, Track A | +12.3 | +11.7 (−0.6) | +11.4 (−0.9) |
| DeepSeek − Qwen, Track B | +12.5 | +14.2 (+1.7) | +15.2 (+2.8) |
| Track A − Track B, DeepSeek | +17.2 | +17.1 (−0.1) | +15.6 (−1.6) |
| Track A − Track B, Qwen | +17.3 | +19.6 (+2.3) | +19.4 (+2.1) |

Both suites rank all four model and track combinations in the same order as the full runs, and suite scores are 0.3–3.1 points above full scores. A per-world check agrees: the correlation between a world's full score and its cp1-only score is 0.79–0.88 across the four combinations.

The Qwen run used gold v3 and an older scorer, so the DeepSeek − Qwen gap is not a controlled model comparison. It is used here only as a pair of systems whose full-run gap is known.

### Choosing the worlds and horizon

Recomputed over every subset of k worlds (median cost of A and B together for DeepSeek; errors are the 90th percentile of |suite − full| over subsets and the four model and track combinations, and of the DeepSeek − Qwen gap error over subsets and both tracks):

| Worlds | Checkpoints | Median cost | Share of full | Mean score error | Score error p90 | Gap error p90 |
|---|---|---:|---:|---:|---:|---:|
| 3 | cp1 | $6.3 | 6% | +2.1 | 9.2 | 7.9 |
| 5 | cp1 | $10.5 | 10% | +2.1 | 6.6 | 5.6 |
| 5 | cp1–cp2 | $20.9 | 19% | +1.2 | 6.0 | 5.8 |
| 7 | cp1 | $14.8 | 13% | +2.1 | 5.2 | 4.2 |
| 11 (lite) | cp1 | $23.2 | 21% | +2.1 | 2.4 | 0.6 |
| 11 | cp1–cp2 | $46.2 | 42% | +1.2 | 2.1 | 0.4 |

- At about the same cost, all 11 worlds at cp1 (gap error 0.6) is far better than 5 worlds at cp1–cp2 (5.8).
- A random choice of 5 worlds can be off by 5–6 points. Micro's five worlds are stratified instead: the pilot (hand-authored and the hardest), one small, one large, one standard 1-week and one 2-week world. On the two runs, micro's errors are close to lite's (tables above). That choice was made after looking at these two runs, so it may be fitted to them. Re-check it, and re-pick it if needed by minimizing the gap error over all pairs of runs, once four or more full runs exist; rescoring them with `--suite` and the script above costs nothing.

## Open work

- **Repeat noise.** Run micro and lite with 3 repeats of one configuration to measure the noise between repeats, then replace the "treat as ties" rule above with a minimum detectable difference.
- **Late-horizon probes.** A run that starts Track A from the oracle store at a late checkpoint and plays only the days up to the next one would cover late-episode failures cheaply, but needs a runner option to seed from an arbitrary date.
