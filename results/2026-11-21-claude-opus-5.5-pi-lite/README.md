# Claude Opus 5.5 + Pi: WCB-lite and WCB-micro

**Claude Opus 5.5 scores WCB-lite 87.5 on Track A and 72.4 on Track B, the best Track A of the four models run on this harness, but within noise of Sonnet 5.5 (85.4 / 71.3) at 3.3× Sonnet's cost.** Its store-building is the best measured (ingestion cost 5.6 points). Its losses come mostly from change questions and, on Track B, from prioritization lists that bury or reword the must-do item.

Run on 21 November 2026, 22:42–23:05 UTC. [Reduced suite](../../docs/lite.md): the 11 public worlds, first two episode days, one repeat, benchmark `f9bee2b` (gold v5). All worlds, people and organizations are synthetic.

**Scores in this report are rescored** with the judge fixes in `ec9ff3d` (date-history chains and acceptance hedges, [docs/judge.md](../../docs/judge.md)). The same fixes were applied to the Haiku, Sonnet and Sol runs; see the [four-model comparison](../2026-11-21-lite-model-comparison/README.md). The run's original scores, from the scorer it was made with, are in `scores-opus-track-*.json` and the first column below.

## Results

| Track | Original | **Rescored** | 95% CI (worlds) | WCB-micro (orig → rescored) | Synthesis (oracle store) | Ingestion cost | SIS |
|---|---:|---:|---|---:|---:|---:|---:|
| A | 82.5 | **87.5** | 83.2–91.2 | 82.7 → 86.6 | 93.1 | 5.6 | 99.6 |
| B | 67.3 | **72.4** | 65.6–78.2 | 67.0 → 71.5 | – | – | – |

- **The scorer fixes moved Opus the most of any model on Track B (+5.1).** Before them, three of its Track B status answers scored 0 for telling the date history ("moved to 31 Dec (it was 15 Dec, then 22 Dec)"; "1 Nov → 12 Nov (13 Sep) → 24 Nov (14 Sep)"), and four priority or list answers missed matches because they hedged on whether a request had been accepted.
- **Against Sonnet the differences are inside the noise** (+2.1 on A, +1.1 on B; [lite guidance](../../docs/lite.md) treats under about 3 as a tie). Opus is clearly ahead of Haiku on A (+4.7) and of Sol on both tracks (+12.2 / +10.1).
- **Clean run.** All 77 agent sessions and 11 oracle sessions exited with `stop`: no failures, timeouts or turn-limit hits, and no invalid answers.

### By question type (mean score; Track A oracle store in brackets)

| Bucket | Opus A | Opus B | Sonnet A | Sonnet B |
|---|---:|---:|---:|---:|
| point | 0.98 (0.97) | 0.77 | 0.93 | 0.78 |
| list | 0.85 (0.93) | 0.68 | 0.87 | 0.57 |
| status | 0.93 (0.98) | 0.72 | 0.88 | 0.65 |
| brief | 0.81 (0.90) | 0.66 | 0.82 | 0.50 |
| change | **0.52** (0.76) | **0.43** | 0.38 | 0.36 |
| temporal | 1.00 (1.00) | 1.00 | 1.00 | 1.00 |
| priority | 0.92 (0.91) | **0.57** | 0.97 | 0.86 |
| unanswerable | 1.00 (1.00) | 1.00 | 1.00 | 1.00 |

Points lost on Track A: 12.5 in total (3.1 from 4 zero-scored answers, 7.8 partial credit, 1.5 citation penalties). On B: 27.6 (8.7 from 13 zero-scored answers). Details in `analysis-output.md`.

## Error analysis

**A full audit of every lost point is in [ERROR-AUDIT.md](ERROR-AUDIT.md).** Opus's own errors cost about 2.3 points on Track A and 2.8 on Track B. The rest is the heuristic grader (5.6 / 16.0), arguable gold (3.0 / 5.6) and citation penalties (1.5 / 3.2). The LLM judge scores the same answers 89.9 / 85.0; its decisions are cached in `llm-judge/`.


### 1. Change questions are still the weakest type, but Opus is best at them

Change questions score 0.52 on A and 0.43 on B, against 0.38 / 0.36 for Sonnet and 0.19 / 0.17 for Sol. Even with the perfect oracle store Opus gets only 0.76. Two patterns:

- **Real omissions.** gen-s7-w2 q-003, "What changed on Project Corrie since Saturday 3 July?": Opus reports the in-house build decision and the handover, but phrases the decision as "Anastasia confirmed Corrie will be built in-house rather than bought (decision made)" and folds the commitment and its completion into one item. It scores 0 on A.
- **Matcher limits.** pilot q-014 lists the hosting decision, the ARB rejection and the moved API date correctly, but phrased differently from gold ("Hosting decided: option 2, the Kettleyard shared tenant"), and scores 0.06–0.12. The heuristic matcher under-credits paraphrased change items; [docs/judge.md](../../docs/judge.md) documents this as a known limit.

### 2. Track B prioritization: the must-do item is present but reworded or buried

Priority falls from 0.92 on A to 0.57 on B, while Sonnet holds 0.86. Three of Opus's B focus answers score 0 where Sonnet scores 0.93–0.95:

- gen-s8-w4. Gold: "Complete the Fulmar privacy impact assessment". Opus, first item: "Finish and send the Fulmar privacy impact assessment to Goran Liu. **It was due 14 Sep and no completion has been seen, so it is probably overdue**". It is the right item, ranked first, but the explanation sits in `text`, so fewer than 40% of the item's words belong to the loop and the keyword route rejects it. Sonnet puts it as "Send Fulmar privacy impact assessment to Goran Liu (was due 14 Sep, no completion evidenced)" and matches.
- gen-s6-w1. Gold: "Send Andres the Fennel rollout checklist". Opus: "Reply to Andres about the Fennel rollout checklist he wants by Wed 24 Feb (**decide yes or no**)", ranked second behind an unsent draft. Even with the acceptance-hedge fix, "reply … decide yes or no" is a different action, and the answer still treats the ask as optional.
- pilot. Gold: "Send Ramona the workshop deck v2". Opus: "Get workshop deck v2 to Ramona Szabo before the 07:30 offsite bus (no laptop all day)". The paraphrase ("get … to") and the logistics push it below the match threshold.

So part of this is the same behaviour as Sol's: Opus treats an incoming request as something to decide on. It records far fewer asks as unaccepted, though: 15.2% of its new Track A loop records, close to Sonnet (14.1%) and below Haiku (20.9%) and Sol (24.3%). The rest is answer style: long, explanatory item text that the strict matcher reads as a different item.

### 3. Pilot is the hardest world, as for every model

Pilot scores 71.1 on A and 49.9 on B. On A, Opus loses two list questions to wording:

- q-004 "What do I owe Hugo?" Opus answers "Pull together the Tinderbox security review package (draft exists; needs the sub-processor list …)" for gold "Send Hyun-woo the Tinderbox security review package". This is a matcher miss: Sonnet's "Assemble the Tinderbox security review package for Hyun-woo" matches.
- q-007 "What does Sol owe me?" Opus lists a completed loop ("Schedule the panel interview … done") instead of the open "Collect two references for Mateus". This is a real error.

### 4. Where Opus beats Sonnet

On A, Opus gets four questions that Sonnet scores 0, all point or change answers in gen-s9-large, gen-s7-w2 and gen-s5-small (a blocker, a loop owner, a working relationship and a change list). On B, Opus scores 0.5–1.0 on nine questions where Sonnet scores 0 (mostly `i_owe` and `owed_to_me` lists, where Sonnet's Track B memory missed the loop). This matches the ingestion numbers: Opus's store is more complete (ingestion cost 5.6 vs 7.8).

## Tokens, cost and time

| Track | Sessions | Model calls | Cache read | Cache write | Output | Agent $ | Oracle $ |
|---|---:|---:|---:|---:|---:|---:|---:|
| A | 33 | 365 | 13.8M | 2.07M | 0.43M | 21.72 | 6.43 |
| B | 44 | 449 | 18.3M | 2.54M | 0.62M | 28.78 | – |

- **Lite total: $56.93** at LiteLLM list prices ($4 / $20 per million input / output tokens, $0.20 cache read, $5 cache write). Micro: $28.69. All prompt input after the first turn was cached; uncached input is negligible.
- **About 3.3× Sonnet** ($17.24) and **16× Haiku** ($3.53) for this suite. Opus writes more output per session than Sonnet (median 12.2k vs 7.6k tokens per ingest day) and takes more turns (median 10 vs 6).
- **Time:** median ingest session 105 s; the suite took 23 minutes elapsed with 8 workers and 2.7 hours of summed session time.

## Configuration and reproduction

- **Harness:** Pi `@earendil-works/pi-coding-agent@1.5.2` (same lockfile as the earlier runs, `config/pi-package-lock.json`), tools read/bash/edit/write, fresh process per session, bash calls capped at 120 s, 120-turn budget (none reached).
- **Model access:** LiteLLM route `claude-opus-5.5` over the Anthropic Messages API, medium adaptive thinking, 1M context. `config/pi_litellm.py` is the Claude 5.5 run's wrapper with Opus's price added; the provider key stays outside the sandbox.
- **Run:** `python results/2026-11-21-claude-opus-5.5-pi-lite/config/run_all.py` (shards per world, 8 workers, then `wcb score --suite lite|micro`). Raw runs are in `runs/claude-opus-5.5-pi-lite/` (git-ignored).
- **Analysis:** `python results/2026-11-21-claude-opus-5.5-pi-lite/analyze.py > analysis-output.md` (reads `scores-fixed-*`; set `WCB_SCORES=scores` for the original scorer).
