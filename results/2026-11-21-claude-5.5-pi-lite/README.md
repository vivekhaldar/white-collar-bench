# Claude Haiku 5.5 and Sonnet 5.5 + Pi: WCB-lite and WCB-micro

**Sonnet 5.5 beats Haiku 5.5 on both tracks: WCB-lite Track A 83.8 vs 81.4, Track B 71.1 vs 64.7. Haiku costs about a quarter as much.** These are [reduced-suite](../../docs/lite.md) scores: the 11 public worlds, first two episode days, one repeat, the unchanged heuristic scorer at benchmark `babaf49` (gold v5). Compare them only with other WCB-lite scores, never with full WCB scores. Run on 21 November 2026, 19:37–20:52 UTC. All worlds, people and organizations are synthetic.

## Results

| Model | Track | WCB-lite | 95% CI (worlds) | WCB-micro | Synthesis (oracle store) | Ingestion cost | SIS |
|---|---|---:|---|---:|---:|---:|---:|
| Haiku 5.5 | A | 81.4 | 76.4–85.7 | 83.9 | 90.1 | 8.7 | 99.4 |
| Haiku 5.5 | B | 64.7 | 58.8–69.6 | 64.8 | – | – | – |
| Sonnet 5.5 | A | **83.8** | 80.5–87.3 | 85.5 | **92.0** | 8.1 | 99.5 |
| Sonnet 5.5 | B | **71.1** | 65.0–76.5 | 67.0 | – | – | – |

For context, the [earlier full runs rescored as lite](../../docs/lite.md#measured-fidelity) (same harness, older benchmark revisions and gold, so not controlled):

| Model | Lite A | Lite B |
|---|---:|---:|
| DeepSeek V4.1 Flash (gold v4) | 87.0 | 69.8 |
| Qwen3.8-27B (gold v3) | 75.3 | 55.7 |

- **The Sonnet − Haiku gap is +2.4 on A and +6.4 on B.** The A gap is inside the [noise guidance](../../docs/lite.md#suggested-protocol-for-a-comparison) for lite (treat differences under about 3 as ties), and the confidence intervals overlap widely. Track B is a real separation, though not a conclusive one. Micro agrees on A (+1.6) but shrinks the B gap to +2.2, because the B difference is concentrated in worlds micro leaves out.
- **Both models lose about 17 points (Haiku) and 13 (Sonnet) from A to B.** Sonnet organizes its own memory better.
- **Both models handle the episode reliably.** All 176 sessions exited cleanly, with `stop`, no turn-limit hits, timeouts, failures or rollbacks. One Haiku Track B answer (pilot q-009) failed validation. The DeepSeek and Qwen full runs failed on days 4 and later, which lite does not cover.

### By question type (mean score; Track A oracle store in brackets)

| Bucket | Haiku A | Haiku B | Sonnet A | Sonnet B |
|---|---:|---:|---:|---:|
| point | 0.93 (0.96) | 0.65 | 0.93 (0.97) | 0.78 |
| list | 0.78 (0.90) | 0.48 | **0.87** (0.93) | 0.56 |
| status | 0.89 (0.79) | 0.55 | 0.88 (0.78) | 0.65 |
| brief | 0.82 (0.92) | 0.53 | 0.82 (0.91) | 0.50 |
| change | **0.37** (0.72) | 0.26 | **0.35** (0.84) | 0.36 |
| temporal | 1.00 (1.00) | 0.95 | 1.00 (1.00) | 1.00 |
| priority | 0.72 (0.94) | 0.76 | **0.88** (0.93) | 0.86 |
| unanswerable | 1.00 (1.00) | 1.00 | 1.00 (1.00) | 1.00 |

### Points lost (WCB-lite points; questions affected)

| Model | Track | Lost | Invalid | Wrong abstention | Base zero | Base partial | Citation penalty |
|---|---|---:|---:|---:|---:|---:|---:|
| Haiku | A | 18.6 | 0 | 0.38 (1) | 6.20 (9) | 10.52 (39) | 1.54 (52) |
| Haiku | A oracle | 9.9 | 0 | 0.38 (1) | 1.14 (1) | 7.10 (32) | 1.27 (44) |
| Haiku | B | 35.3 | 0.23 (1) | 0.54 (2) | 12.12 (23) | 17.75 (49) | 4.64 (90) |
| Sonnet | A | 16.2 | 0 | 0 | 4.84 (7) | 10.09 (39) | 1.25 (40) |
| Sonnet | A oracle | 8.0 | 0 | 0.38 (1) | 2.65 (3) | 4.32 (24) | 0.69 (20) |
| Sonnet | B | 28.9 | 0 | 1.52 (4) | 8.56 (16) | 16.24 (51) | 2.59 (65) |

Neither model answered an unanswerable question.

## Error analysis

### Shared weaknesses

1. **Change questions are the worst bucket for both models** (A: Haiku 0.37, Sonnet 0.35). That is far below their oracle-store scores (0.72 and 0.84), so most of the loss is ingestion: the event is missing from the agent's store, or recorded in a form that doesn't match.
   - Both models score 0 on gen-s10-w2-small q-003 and gen-s7-w2 q-003. In gen-s7-w2 q-003 the Corrie build-in-house decision and the handover are both present, but the answers pad with meeting check-ins, which costs precision.
   - Both lose most of pilot q-014 (Tinderbox changes, ≤ 0.13): they list the hosting decision and the ARB rejection, while gold expects the SSO group-claims issue and the load-test plan.
   - Some of this is the [documented matcher limit](../2026-11-21-error-analysis-deepseek-qwen/README.md#4-failure-modes-ranked) on long, caveated event descriptions.
2. **Suggested vs agreed commitments.**
   - On A, both models carefully label unaccepted asks ("not accepted, so confirm or decline") and then rank them in focus lists. gen-s6-w1 focus scores 0 for Sonnet: it ranks the Fennel checklist with a "decide whether to accept" framing instead of as the top commitment.
   - On B, Sonnet returns `[]` for gen-s3-w1 q-010 (Rosix loops) and q-004 (owe Eleni), discarding real commitments as unaccepted. Haiku makes the same `[]` miss on gen-s3-w1 q-004 on A.
3. **Alias resolution for obligations.**
   - Pilot q-007 "What does Sol owe me?" scores 0 for both models on A. Both resolve Sol to Marisol and then find no matching loop. Gold is "Collect two references for Mateus", which their stores hold as the reference checks but don't connect to her.
   - Pilot q-004 (Hugo = Hyun-woo) also scores 0 for Haiku A and both models on B. The item is right ("Prepare the Tinderbox security review package"), but it is phrased as preparing an unsent draft and gets no judge match.
4. **Wrong entity with a shared first name.** gen-s7-w2 q-006 "Who is responsible for returning the Merol questionnaire?": both answer **Bolat Farah**, but gold is **Bolat Oyelami** (a name_collision planting). The same mistake from both models suggests the seed store or inputs make it easy to get wrong; worth checking.
5. **Verbose point values against short gold** (largely grader strictness, as in earlier runs):
   - gen-s9-large q-015 "What is blocking Cirrus?" gets "Security review" (Haiku A) or a list of three blockers (Sonnet A) where gold is "real patient data paused pending the security review".
   - On B, `person_attr` relationship questions fail on wording: "Executive stakeholder (CMIO…)" for gold "executive", "Colleague … day-to-day collaborator" for "peer".

### Haiku-specific

- **Prioritization is weak** (A 0.72 vs Sonnet 0.88). gen-s2-w1 and gen-s7-w2 focus questions score 0: Haiku leads with "decide on…" items or with a suggested ask, ahead of the must-include commitment.
- **Lists lose precision** (A 0.78 vs 0.87): more extra or misframed items.
- **Track B: point answers collapse** (0.65 vs Sonnet's 0.78). Examples: gen-s7-w2 target date 2027-07-26 where gold is 2027-08-03 (a superseded date kept as current), and gen-s4-w2 Fjord phase "Scoping/design" where gold is "build". Haiku's self-built memory keeps less current state.
- **Citations on B are weaker** (4.6 points of penalty vs 2.6).

### Sonnet-specific

- **Over-abstains on B** (4 wrong abstentions: gen-s5-small blocker and relationship, gen-s10 relationship, gen-s6 Rike). Its own memory sometimes lacks a fact it needed.
- **On B, briefs are no better than Haiku's** (0.50 vs 0.53). In pilot q-008 (Delphine) it answers with the meeting agenda instead of the shared projects. In gen-s2-w1 q-011 it conflates Imani Quaye with Imani Navarro (name collision).
- **gen-s5-small B is its worst world** (50.2). Its memory has the Falbury pilot "with no blockers", although the security-review pause was in the inputs.

## Tokens, cost and time

Metered at the proxy (`wcb run --meter`); cost uses LiteLLM's listed prices per million tokens: Haiku $0.10 input / $0.50 output / $0.01 cache read / $0.125 cache write; Sonnet $2 / $10 / $0.10 / $2.50. Uncached input is negligible (Pi's prompt caching covers almost everything). The agent's self-reported costs match the metered ones to the cent.

| Model | Track | Sessions | Model calls | Cache read | Cache write | Output | Agent $ | Oracle $ (A) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Haiku | A | 33 | 607 | 32.7M | 3.18M | 1.26M | 1.35 | 0.25 |
| Haiku | B | 44 | 911 | 59.3M | 4.16M | 1.63M | 1.93 | – |
| Sonnet | A | 33 | 267 | 6.8M | 1.50M | 0.33M | 7.72 | 2.04 |
| Sonnet | B | 44 | 266 | 5.2M | 1.58M | 0.30M | 7.48 | – |
| **Total** | | 154 | 2,051 | 104.0M | 10.4M | 3.52M | **18.48** | **2.29** |

**All-in: $20.77** for both models, both tracks, lite including oracle sessions: Haiku $3.53, Sonnet $17.24. Micro is the subset of the same sessions on its five worlds: agent sessions on A+B cost Haiku $1.57 and Sonnet $7.50, plus $0.11 and $0.90 for oracle sessions.

Wall time: 75 minutes elapsed with 8 parallel workers. Summed session time was Haiku 3.9 h and Sonnet 1.3 h.

**Haiku works very differently from Sonnet.** Per ingest session (medians), Haiku takes 22 turns and writes 44k output tokens; Sonnet takes 7 turns and 9.4k. Both spend about 8.6 s per model call, and 96% of session wall time is model calls. Sonnet batches: one command reads all inputs, one script updates all memory files. Haiku reads and edits piecemeal and re-checks. Haiku's tokens are 20× cheaper, so it still costs about a quarter of Sonnet's price, but its sessions take about 3× longer.

## Configuration

- **Harness:** Pi `@earendil-works/pi-coding-agent@1.5.2` (same lockfile as the DeepSeek run), tools read/bash/edit/write. Fresh process per session, no session persistence, extensions, MCP, skills or context files. Bash calls are capped at 120 s, and sessions at a 120-turn budget (none reached it).
- **Model access:** a LiteLLM proxy over the Anthropic Messages API, models `claude-haiku-5.5` and `claude-sonnet-5.5`, adaptive thinking at effort **medium** (Pi's default), up to 128k output tokens.
- **Isolation:** bubblewrap namespaces as in the DeepSeek run (only the workspace is writable; repo, gold and other results are not mounted; network shared).
- **Credential fix.** The DeepSeek report recommended keeping provider credentials out of the tool namespace. Here the wrapper runs a loopback forwarder outside the sandbox that adds the key to each request; Pi gets only a placeholder. A scan of every run log and transcript found no copy of the key.
- **Budgets:** ingest 1,800 s, query 900 s. Track A ran with oracle sessions.
- **Orchestration:** one `wcb run --world W --max-days 2 --meter` shard per model, track and world, run with 8 workers. Shards were assembled into one run per model and track, recorded as a lite-suite run, and scored with `wcb score --suite lite` and `--suite micro`. Heuristic judge.

Files: [`config/`](config/) holds the adapters, wrapper, runtime extension, orchestrator and locks. `scores-<model>-track-<a|b>-<lite|micro>.json` are the unmodified score reports. [`analyze.py`](analyze.py) regenerates [`analysis-output.md`](analysis-output.md) (tables and the 25 lowest-scoring answers per arm, with gold and predicted). [`evidence/`](evidence/) holds the start and completion records. Raw runs (transcripts, snapshots, answers, meter logs) are under the ignored `runs/claude-5.5-pi-lite/`.

## Caveats

- **One repeat, two days, heuristic judge.** Lite is about 2 points optimistic against full runs. Repeat noise is unmeasured, so the A gap between the models is not established.
- **Not controlled against the DeepSeek and Qwen numbers.** Benchmark revision, gold version (v5 vs v4/v3), adapter wrapper and reasoning settings differ.
- **Effort setting.** Both models ran at medium effort. Higher effort might change the ranking and the cost, especially for Haiku.
- **Shared zeros may be world or scorer issues.** Several zero scores occur for both models on the same questions (gen-s7-w2 q-006 Bolat, pilot q-007 Sol, gen-s10 q-003 changes); they deserve a gold or scorer review before being read as model errors.
