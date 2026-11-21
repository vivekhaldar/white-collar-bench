# GPT-6.1 Sol + Pi: WCB-lite and WCB-micro

**GPT-6.1 Sol scores WCB-lite 69.3 on Track A and 58.5 on Track B, well below Claude Haiku 5.5 (81.4 / 64.7) and Sonnet 5.5 (83.8 / 71.1) on the same harness and suite.** It loses most of its points on three question types: prioritization, change questions and status answers. The first two trace to one consistent model behaviour, and the third is largely a scorer limitation.

Run on 21 November 2026, 21:54–22:23 UTC. [Reduced suite](../../docs/lite.md): the 11 public worlds, first two episode days, one repeat, the unchanged heuristic scorer at benchmark `eb0e9cd` (gold v5). The user asked for GPT-6.2 Sol, which the LiteLLM proxy does not serve; 6.1 was run instead. All worlds, people and organizations are synthetic.

## Results

| Model | Track | WCB-lite | 95% CI (worlds) | WCB-micro | Synthesis (oracle store) | Ingestion cost | SIS |
|---|---|---:|---|---:|---:|---:|---:|
| **GPT-6.1 Sol** | A | **69.3** | 63.9–74.6 | 70.8 | 86.2 | 16.9 | 99.5 |
| **GPT-6.1 Sol** | B | **58.5** | 52.8–63.8 | 57.2 | – | – | – |
| Claude Sonnet 5.5 | A / B | 83.8 / 71.1 | | 85.5 / 67.0 | 92.0 | 8.1 | 99.5 |
| Claude Haiku 5.5 | A / B | 81.4 / 64.7 | | 83.9 / 64.8 | 90.1 | 8.7 | 99.4 |

The Claude rows are from [the Claude 5.5 run](../2026-11-21-claude-5.5-pi-lite/README.md), made with the same harness and wrapper (`pi_litellm.py`, generalized here to OpenAI's Responses API), revision and gold, at medium reasoning effort. This is the closest to a controlled comparison in `results/`. Differences: the provider API, a 272k-token context window for Sol vs 1M for Claude, and Sol served on OpenAI's flex tier.

- **Sol trails Haiku by 12.1 points on A and 6.2 on B.** That is well beyond the lite noise guidance (treat differences under about 3 as ties). The confidence intervals barely overlap with Haiku's on A and not at all with Sonnet's.
- **Sol has the largest ingestion cost of the three models: 16.9 points** on A, against 8–9 for Claude. With the perfect oracle store its Synthesis is 86.2, about 4–6 below Claude. So both answering and record-keeping are weaker, and record-keeping more so.
- **The run itself was clean.** All 88 sessions exited with `stop`. There were no failures, timeouts, turn-limit hits or invalid answers.

### By question type (mean score; Track A oracle store in brackets)

| Bucket | Sol A | Sol B | Haiku A | Sonnet A |
|---|---:|---:|---:|---:|
| point | 0.94 (0.96) | 0.69 | 0.93 | 0.93 |
| list | 0.67 (0.82) | 0.36 | 0.78 | 0.87 |
| status | **0.68** (0.84) | 0.44 | 0.89 | 0.88 |
| brief | **0.57** (0.78) | 0.47 | 0.82 | 0.82 |
| change | **0.17** (0.53) | 0.14 | 0.37 | 0.35 |
| temporal | 1.00 (1.00) | 0.95 | 1.00 | 1.00 |
| priority | **0.52** (0.94) | 0.68 | 0.72 | 0.88 |
| unanswerable | 1.00 (1.00) | 1.00 | 1.00 | 1.00 |

Points lost on Track A: 30.7 in total, of which 15.5 are zero-scored answers (19 questions), 13.4 are partial credit (40) and 1.9 are citation penalties. On B: 41.6 in total, with 19.9 from zero scores (34 questions).

## Error analysis

### 1. Requests are treated as unaccepted, which wrecks prioritization (model behaviour)

The single largest difference. In 5 of 11 worlds Sol's "What should I focus on tomorrow?" scores **0** on A (gen-s2, s3, s5, s6, s7). Its answers do mention the must-include item, but always as something to *decide on*:

- gen-s2-w1. Gold: "Update the Mistral access request after Bilal's comments". Sol: "Address Bilal's Mistral access-request revision request; **confirm whether you can take it on** and revise it if agreed."
- gen-s6-w1. Gold: "Send Andres the Fennel rollout checklist". Sol: "Respond to Andres's request … **agree whether you can deliver it tomorrow**, then send it if accepted."

10 of the 12 must-include items at cp1 are commitments created by an incoming ask, such as an email asking for something by tomorrow. The world's gold treats them as accepted commitments (`basis: received`, `accepted: true`).

Sol records such asks as `accepted: false` far more often. New loop records in its Track A stores are 24.3% unaccepted, against 20.9% for Haiku and 14.1% for Sonnet. It then turns them into "decide whether to accept" items, which the scorer doesn't match to the commitment.

Sonnet has the same unaccepted record for the gen-s2 ask, but still ranks it as "update the access request". Sol's phrasing is the decisive difference. With the perfect oracle store Sol's priority score is 0.94, so this is an ingestion problem: Sol builds a store in which the most urgent items look optional.

This exposes a genuine ambiguity in the benchmark. [Store contract](../../contract/CONTRACT.md) rule 7 says a loop "that someone else suggests for the worker … gets `accepted: false` until the worker commits", and these asks have no reply from the worker. The generator, on the other hand, treats a direct request as accepted. Sol follows the contract's wording more literally than the gold does. This is worth resolving in the contract or the generator; see [Benchmark issues](#benchmark-issues-found).

### 2. Status answers with full date histories are zeroed (largely scorer limitation)

Sol's status answers are the most detailed of the three models. In gen-s1-w1 and gen-s8-w4 they score 0 on both tracks, even though the current target date is right. The rubric marks the date items **contradicted** because the answers also list the superseded dates:

> "Ottavio moved the target from 1 November to 12 November on 13 September, then to 24 November on 14 September."

The heuristic judge treats a value after "from" as history, but not one between "to … then". So 12 November counts as a superseded date presented as current, and the two critical date items are wiped out.

A regrade of all status and brief answers (`scripts/rubric_verdicts.py`) shows how specific this is:

| Model | Contradicted rubric verdicts (A) | Low-scoring answers caused by them |
|---|---:|---|
| Sol | 4 of 154 | gen-s1-w1 q-002, gen-s8-w4 q-002, on both tracks |
| Sonnet | 1 of 154 | none |
| Haiku | 0 of 154 | none |

These two answers alone cost Sol 2.3 points on each track. The framing rule should accept "X to Y, then to Z" chains.

### 3. Change questions: verbose and qualified events don't match (mixed)

Sol scores 0.17 on change questions (A), against 0.35–0.37 for Claude, and only 0.53 even with the oracle store. Its event descriptions are long and full of qualifications ("a tentative suggestion … was recorded", "No login or password change is evidenced"). The heuristic matcher under-credits this style; the same limitation is [documented for DeepSeek](../2026-11-21-error-analysis-deepseek-qwen/README.md#4-failure-modes-ranked).

It also lists things that are not changes: meetings held, confirmations, restatements. This dilutes precision.

### 4. Briefs and lists lose precision

Person briefs score 0.57, against 0.82 for both Claude models. Sol leads with meeting logistics and caveats instead of the shared projects and open loops the rubric looks for. In pilot q-008 it answers "I'm meeting Delphine on Thursday …" with the check-in agenda.

Lists score 0.67, against 0.78 and 0.87. Answers mix accepted and suggested items with long annotations, such as "Send Tendai the workshop room plan: recorded as suggested, not accepted; no delivery evidenced".

### 5. Shared with Claude

Several zero scores are shared with Claude and may be world or scorer issues:

- pilot q-007 (Sol owes the references, under her nickname)
- pilot q-004 (Hugo = Hyun-woo; the right package described as an unsent draft)
- gen-s10-w2-small q-003 (changes on Translation Help)
- gen-s9-large q-015 (blocker phrasing)

Sol's point answers are as accurate as Claude's on Track A (0.94).

## Tokens, cost and time

| Track | Sessions | Model calls | Uncached input | Cache read | Output | Agent $ (list) | Agent $ (flex, billed) | Oracle $ (flex) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A | 33 | 515 | 1.50M | 14.0M | 0.40M | 9.13 | **4.57** | 0.97 |
| B | 44 | 680 | 1.93M | 17.3M | 0.38M | 10.38 | **5.19** | – |

- **Lite total: $10.73 billed** (agent $9.76 + oracle $0.97), or $21.44 at list prices.
- **Micro:** $5.10 billed, including oracle sessions.

**Pricing.** The LiteLLM route `gpt-6.1-sol` returns `service_tier: flex` on every response, and Pi prices flex at half the list rate. Pi's self-reported cost is therefore exactly half of list on every component. LiteLLM lists only standard prices for this route, so the billed figure assumes the flex tier is passed through. The metered token counts are exact either way.

**Caching.** Prompt-cache writes are not reported separately by this route: Pi records them, while the metering proxy counts them as uncached input. The "list" column above prices Pi's split (cache write at $2.50/M); `analysis-output.md` prices them all as input at $2/M ($8.38 and $9.41), so its agent cost is slightly lower.

**Comparison.** At the billed flex rate Sol costs about 2.9× Haiku and 0.57× Sonnet for this suite. Sol per session: median 17 turns and 12k output tokens per ingest day, 168 s wall time; it sits between Sonnet (7 turns) and Haiku (22 turns). The run took 29 minutes elapsed (8 workers), 3.4 hours of summed session time.

## Benchmark issues found

1. **Is an incoming ask accepted?** Contract rule 7 and the generator disagree on whether a direct request the worker hasn't answered is an accepted commitment. A model that reads the contract literally (Sol) is punished on prioritization, lists and changes. Either the contract should say that a direct request to the worker is accepted by default, or the generator should mark such loops `accepted: false` until the worker replies.
2. **Date-history framing.** The heuristic judge treats "moved from X to Y, then to Z" as stating Y as current. Correct, well-framed answers are zeroed (gen-s1-w1 q-002 and gen-s8-w4 q-002 for Sol). The history-framing rules in `wcb/util/text.py` and the rubric judge should recognize chained moves.
3. **Change matching** still under-credits long, qualified event descriptions, as already documented.

These change grading, so fixes need a new scorer and gold version. Rescoring the saved answers will show how much of Sol's gap they explain.

## Configuration

- **Harness:** Pi `@earendil-works/pi-coding-agent@1.5.2` (same lockfile as the earlier runs), tools read/bash/edit/write, fresh process per session. Bash calls are capped at 120 s and sessions at a 120-turn budget (none reached it).
- **Model access:** LiteLLM proxy route `gpt-6.1-sol` (which LiteLLM maps to `github_copilot/gpt-6.1-sol`) over the OpenAI Responses API. Reasoning effort is medium (Pi's default), with encrypted reasoning carried between turns (`store: false`), a 272k context window and up to 128k output tokens.
- **Isolation:** bubblewrap namespaces as before. The key stays outside the sandbox: a loopback forwarder adds `Authorization: Bearer`. A scan of every log, transcript and committed file found no copy of the key.
- **Orchestration:** one `wcb run --world W --max-days 2 --meter` shard per world and track, 8 workers. Shards were assembled into one run per track and scored with `wcb score --suite lite` and `--suite micro`. Heuristic judge.

Files: [`config/`](config/) holds the adapter, wrapper, runtime extension, orchestrator and locks. `scores-sol-track-<a|b>-<lite|micro>.json` are the unmodified score reports. [`analyze.py`](analyze.py) regenerates [`analysis-output.md`](analysis-output.md), and [`scripts/rubric_verdicts.py`](../../scripts/rubric_verdicts.py) regenerates the rubric verdict counts. [`evidence/`](evidence/) holds the start and completion records. Raw runs are under the ignored `runs/gpt-6.1-sol-pi-lite/`.

## Caveats

- **One repeat, two days, heuristic judge.** Repeat noise is unmeasured.
- **Not GPT-6.2 Sol.** The proxy does not serve 6.2.
- **Grader-sensitive.** Sol's verbose, heavily qualified style interacts badly with the heuristic scorer, which accounts for part of the gap (issue 2 alone costs 2.3 points per track). An LLM judge, or the scorer fixes above, would narrow the gap. Issue 1 is a real difference in how the model reads commitments, whichever reading the benchmark settles on.
- **Effort.** Medium for all three models. Sol at high effort might do better.
