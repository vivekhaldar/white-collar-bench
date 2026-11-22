# Four models on WCB-lite: Haiku, Sonnet and Opus 5.5, GPT-6.1 Sol (Pi harness)

**Rescored with the fixed judge, Opus 5.5 and Sonnet 5.5 tie at the top (Track A 87.5 vs 85.4, Track B 72.4 vs 71.3), Haiku 5.5 is a few points behind at a fifth of Sonnet's cost, and GPT-6.1 Sol trails by 10–12 points on A.** Opus costs 3.3× Sonnet for a gain inside the noise.

All four runs used the same harness (Pi 1.5.2 with the `pi_litellm.py` wrapper), the same [WCB-lite suite](../../docs/lite.md) (11 public worlds, two episode days, one repeat), gold v5, medium reasoning effort and a LiteLLM proxy. They are the closest thing to a controlled model comparison in `results/`. All worlds, people and organizations are synthetic.

Per-run reports: [Haiku and Sonnet](../2026-11-21-claude-5.5-pi-lite/README.md), [Opus](../2026-11-21-claude-opus-5.5-pi-lite/README.md), [Sol](../2026-11-21-gpt-6.1-sol-pi-lite/README.md). The deck for presenting these results is [`slides/index.html`](slides/index.html) (PDF: [`slides/wcb-lite-results.pdf`](slides/wcb-lite-results.pdf)). It also shows DeepSeek V4.1 Flash and Qwen3.8-27B, whose earlier full runs are rescored as lite from their saved reports (older scorer and gold).

## Scores

| Model | Lite A | Lite B | 95% CI A | 95% CI B | Micro A | Micro B | Synthesis | Ingestion cost | Lite $ |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|
| Opus 5.5 | **87.5** | **72.4** | 83.2–91.2 | 65.6–78.2 | 86.6 | 71.5 | 93.1 | **5.6** | 56.93 |
| Sonnet 5.5 | 85.4 | 71.3 | 81.8–88.8 | 65.3–76.6 | 86.5 | 67.2 | **93.2** | 7.8 | 17.24 |
| Haiku 5.5 | 82.8 | 65.3 | 78.7–86.4 | 59.5–70.3 | 84.4 | 65.2 | 90.2 | 7.4 | **3.53** |
| GPT-6.1 Sol | 75.3 | 62.3 | 69.0–80.8 | 55.4–68.2 | 77.0 | 60.0 | 87.4 | 12.1 | 10.72 (flex) |

*Synthesis* is the Track A score answering from the perfect oracle store; *ingestion cost* is how much the model's own store costs it (Synthesis minus Track A, before citation effects). Costs include Track A oracle sessions. Sol is billed at OpenAI's flex tier, half of its $21.44 list price.

- **The ranking is the same on both tracks and in both suites:** Opus ≈ Sonnet > Haiku > Sol. Micro agrees with lite to within 1.6 points on A and 4.1 on B (Sonnet B is the outlier), so micro at half the price gives the same ordering.
- **Track B costs every model 13–17 points.** Without the contract's store layout, every model keeps a worse memory. The gap is smallest for Sol (13.0), whose Track A is already low.
- **Answering is not the bottleneck for the Claude models.** All three score 90–93 from the oracle store. What separates them is ingestion: Opus's store costs it 5.6 points, Sonnet's 7.8, Haiku's 7.4 and Sol's 12.1.

## Judge fixes and rescoring

Two scorer bugs were found in the Sol error analysis and fixed in `ec9ff3d` ([docs/judge.md](../../docs/judge.md)). Every run was rescored; 65 answers went up and none went down.

| Model | Lite A (orig → new) | Lite B (orig → new) | From date-history chains | From acceptance hedges |
|---|---|---|---|---|
| Haiku 5.5 | 81.4 → 82.8 | 64.7 → 65.3 | 0 / 0 | +1.5 / +0.6 |
| Sonnet 5.5 | 83.8 → 85.4 | 71.1 → 71.3 | 0 / 0 | +1.5 / +0.2 |
| Opus 5.5 | 82.5 → 87.5 | 67.3 → 72.4 | 0 / +2.5 | +5.1 / +2.5 |
| GPT-6.1 Sol | 69.3 → 75.3 | 58.5 → 62.3 | +2.1 / +1.6 | +3.9 / +2.3 |

1. **Date-history chains.** A status answer that tells the full history of a moved date ("moved from 15 Dec to 22 Dec on 8 Nov, then to 31 Dec", "it was 15 Dec, then 22 Dec", "1 Nov → 12 Nov (13 Sep) → 24 Nov") had its date items marked *contradicted*, zeroing a correct answer. The rubric now reads these as history; negative controls ("Target 29 Jan, then 5 Feb if the vendor slips", "Kickoff was last week, then 29 Jan is the target") still contradict. Only the two most detailed writers, Opus and Sol, were hit.
2. **Acceptance hedges.** [Contract](../../contract/CONTRACT.md) rule 7 says a loop suggested to the worker is unaccepted until they agree, while the world generator treats an unanswered direct request as accepted. Models that follow the contract write items such as "Respond to Andres's request for the Fennel rollout checklist; agree whether you can deliver it tomorrow", and the matcher rejected them because the hedge words diluted the item. The matcher now ignores words about acceptance (accept, confirm, whether, not yet, request, …) unless the gold item uses them. It still requires the right object: "Confirm whether you can send Andres the Fennel stakeholder map" does not match the checklist.

The contract and generator still disagree on rule 7. Fixing the generator (rendering unanswered asks as tentative) would regenerate every dev world's inbox and void all existing runs, so that is left for the next gold version. The original-scorer reports stay in each run's directory; the rescored reports are in [`rescored/`](rescored/).

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

An [audit of every point Opus lost](../2026-11-21-claude-opus-5.5-pi-lite/ERROR-AUDIT.md) finds its own errors cost only about 2.3 points on A and 2.8 on B. The heuristic grader costs 5.6 / 16.0, arguable gold items 3.0 / 5.6 and citation penalties 1.5 / 3.2. An LLM judge (Opus 5.5, so an upper estimate) scores the same answers 89.9 / 85.0. Scores near the top of lite therefore measure the grader as much as the model; use the LLM judge when comparing frontier models.

## What all four get wrong

- **Change questions are the weakest type for every model:** 0.19–0.52 on A, 0.17–0.43 on B. Even from the perfect store the best is 0.85 (Sonnet). Answers fold several events into one item or describe them differently from gold, and the heuristic matcher under-credits paraphrases.
- **The pilot world is the hardest for every model** (A 57–76, B 43–62). It is hand-authored, with dense hand-offs, corrections and an offsite day that moves everything.
- **Track B lists lose loops:** list scores fall from 0.69–0.87 on A to 0.42–0.68 on B. Without the contract's loop records, models forget commitments made in passing.
- **None of them invents answers.** Unanswerable questions score 1.00 for every model on both tracks, and temporal questions 0.95–1.00.

## Reproduction

- `python results/2026-11-21-lite-model-comparison/compare.py > results/2026-11-21-lite-model-comparison/data.json` collects every number above from the raw runs (`runs/`, git-ignored) and their original and rescored reports.
- Rescoring a run: `wcb score <run>/track-<t>/measured --suite lite --out <run>/track-<t>/scores-fixed-lite` at `ec9ff3d` or later.
- `slides/build.py` renders the deck's charts from `data.json`.
