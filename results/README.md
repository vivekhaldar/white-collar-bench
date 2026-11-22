# Benchmark results

Records of completed experiments, including configuration, unmodified-grader results,
diagnostic corrections, costs, failures, and evidence. These are self-reported public-world
evaluations, not verified private-test leaderboard submissions.

| Run | Model / harness | Track A | Track B | Record |
| --- | --- | ---: | ---: | --- |
| 2026-11-10–11 | Qwen3.8-27B / Pi 1.5.2 | 72.3422 | 54.9968 | [Detailed report](2026-11-11-qwen3.8-27b-pi/README.md) |
| 2026-11-11–12 | DeepSeek V4.1 Flash 1017 / Pi 1.5.2 | 84.6439 | 67.4833 | [Detailed report](2026-11-11-deepseek-v4.1-flash-1017-pi/README.md) |

Reduced-suite runs (WCB-lite and WCB-micro; [reduced suites](../docs/lite.md)), comparable only with each other:

| Run | Model / harness | Lite A | Lite B | Micro A | Micro B | Record |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 2026-11-21 | Claude Sonnet 5.5 / Pi 1.5.2 | 83.8 | 71.1 | 85.5 | 67.0 | [Report](2026-11-21-claude-5.5-pi-lite/README.md) |
| 2026-11-21 | Claude Haiku 5.5 / Pi 1.5.2 | 81.4 | 64.7 | 83.9 | 64.8 | [Report](2026-11-21-claude-5.5-pi-lite/README.md) |
| 2026-11-21 | GPT-6.1 Sol / Pi 1.5.2 | 69.3 | 58.5 | 70.8 | 57.2 | [Report](2026-11-21-gpt-6.1-sol-pi-lite/README.md) |
| 2026-11-21 | Claude Opus 5.5 / Pi 1.5.2 | 82.5 | 67.3 | 82.7 | 67.0 | [Report](2026-11-21-claude-opus-5.5-pi-lite/README.md) |

These are original-scorer scores. Regraded on the same answers with gold v6 and the cross-family panel judge ([judges](../docs/judge.md#panel-judge)), lite A / B is Opus 91.9 / 87.4, Sonnet 89.1 / 80.7, Haiku 88.8 / 78.3 and Sol 87.0 / 79.9 (heuristic judge only: 88.0 / 76.1, 85.5 / 74.2, 84.6 / 67.3, 78.0 / 64.9). The [four-model comparison](2026-11-21-lite-model-comparison/README.md) has every grader's scores, judging cost, run costs and a slide deck.

A cross-run [error analysis](2026-11-21-error-analysis-deepseek-qwen/README.md) breaks down where both runs lost points, by component, question type, challenge, world and episode position, and separates model errors from documented grader limitations.

The table uses **original scores from each run's unchanged scorer**. The Qwen report separately records the
Track A missing-checkpoint retest and conservative semantic-credit adjustments. Do not
substitute these hybrid/manual figures for a complete uniformly configured evaluation.

The DeepSeek run uses the updated benchmark at `c623e77`, gold v4. Historical Qwen results
use gold v3 and the older scorer/prompts/runtime; their difference is not a controlled
model-quality comparison. DeepSeek's report includes four turn-budget failures, sampled
semantic grading limitations, a meter-finalization discrepancy and a credential exposure
with sanitized shareable transcripts; unredacted evidence is
quarantined and excluded from downloadable archives.

Every full run can also be rescored as a [reduced suite](../docs/lite.md) (`wcb score <run> --suite lite`); the lite and micro scores of these two runs are recorded there.

For future entries, record the benchmark revision, worlds, track, repeats, model/provider,
harness/runtime, prompts and budgets, scorer/judge version, original scores and uncertainty,
cost, failures, and evidence provenance. Preserve original results when regrading. Mark
manual adjudications, configuration probes, and partial reruns separately. Keep credentials,
private data, dependency installations, and large raw run directories out of Git.

All world content and example people/organizations in these reports are synthetic.
