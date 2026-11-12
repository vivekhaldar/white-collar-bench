# Operational audit and experiment issues

The measured evaluation completed successfully as an experiment, with **four failed ingestion sessions retained in the scores**, and a credential-exposure incident requiring rotation before another run. This file distinguishes model failures, benchmark bookkeeping and experiment-wrapper defects. No benchmark implementation was patched during measurement.

## Completion and immutable outcomes

- Start: 2026-11-11 20:05:56.759623 UTC. Finish: 2026-11-12 03:21:08.168013 UTC. Elapsed: **7 h 15 min 11.408390 s**.
- All 22 world/track shards exited 0 and recorded run status `completed`. A completed run does not imply every contained model session succeeded.
- A: 202 sessions, 201 normal stops, one failed ingestion. B: 162 sessions, 159 normal stops, three failed ingestions.
- All four failures reached 120 assistant turns, exited 143 and reported `turn_limit`, `incomplete: true`, last assistant stop `toolUse`.
- No timeouts, final output-length terminations, exit-0 incomplete sessions, successful no-op ingestions or empty post-ingestion stores.
- **All 2,235 expected answers are present and schema-valid:** A 745, A oracle 745, B 745. No null or empty answer objects.
- The failed-day snapshots are byte-identical to the preceding/restored snapshots, excluding Git internals: these are **rollbacks**, not successful no-op ingestions. Subsequent daily inputs remained ephemeral; missed-day knowledge could persist.
- Four failed ingestions consumed **$2.970641988** and **4,508.297 summed session-seconds**, included in the experiment totals. They were not replayed or replaced.

Exact failed sessions, relative to `runs/pi-deepseek-v41-flash-1017/`:

```text
track-a/shards/pilot/pilot/r1/sessions/2027-03-05.ingest
track-b/shards/pilot/pilot/r1/sessions/2027-03-04.ingest
track-b/shards/pilot/pilot/r1/sessions/2027-03-05.ingest
track-b/shards/gen-s7-w2/gen-s7-w2/r1/sessions/2027-07-16.ingest
```

See [failure traces](FAILURE-TRACES.md) for why these sessions kept working instead of stopping. The trace audit found no half-written final tool call: productive edits and late consistency work were discarded together after the session failed to conclude normally.

## Token and cost reconciliation

Authoritative accounting uses final **shard `meter.jsonl`** records, reconciled with completed assistant `message_end` usage. Do not double-count `agent_end` or `turn_end` events. Combined and shard meter row multisets agree: 6,403 A rows and 8,336 B rows.

| Track / phase | Sessions | Fresh input | Cache-read input | Output, including reasoning | Calculated USD |
| --- | ---: | ---: | ---: | ---: | ---: |
| A ingestion | 100 | 91,275,946 | 308,865,280 | 4,977,480 | 35.208951480 |
| A agent query | 51 | 29,942,042 | 40,653,312 | 1,147,632 | 10.603690872 |
| A oracle query | 51 | 23,594,309 | 29,042,560 | 1,048,464 | 8.510704860 |
| **A total** | **202** | **144,812,297** | **378,561,152** | **7,173,576** | **54.323347212** |
| B seed ingestion | 11 | 12,645,270 | 67,512,832 | 920,671 | 5.303463192 |
| B daily ingestion | 100 | 128,892,515 | 757,810,304 | 5,298,605 | 49.572942324 |
| B query | 51 | 27,975,374 | 29,363,200 | 870,860 | 9.613823400 |
| **B total** | **162** | **169,513,159** | **854,686,336** | **7,090,136** | **64.490228916** |
| **Measured total** | **364** | **314,325,456** | **1,233,247,488** | **14,263,712** | **118.813576128** |

For every session, calculated USD = (fresh input × 0.30 + cached input × 0.006 + output × 1.20) / 1,000,000. Pi's dollar estimate agrees within $0.000000001 per session. Cost components: $94.297636800 fresh input, $7.399484928 cache input, $17.116454400 output. Cache creation is zero; cache reads comprise 79.6891% of input tokens.

These are **published-rate estimates, not an invoice**. Every successful assistant usage record has `totalFromProvider: false`; the provider did not supply a billed dollar amount. Pi records 7,185,883 reasoning tokens (A 4,328,796, B 2,857,087), already a **subset of output**, not additional billable tokens. Its installed parser maps completion tokens to output and records reasoning tokens separately.

The adapter's `usage.input_tokens` is fresh **plus** cached input; raw meter `input_tokens` is fresh **only**. Applying the fresh price to the report's combined input would substantially overstate cost. The totals exclude smoke/configuration probes and analysis-agent work.

### Confirmed meter-finalization race, no answer-score impact

`track-b/shards/gen-s6-w1/gen-s6-w1/r1/sessions/seed.ingest/session.json` captured 67 calls rather than 68. Its final call is present in the completed raw meter logs and Pi usage: **14,089 fresh + 140,160 cache input, 981 output (698 reasoning), $0.006244860**.

Consequently the generated B efficiency report understates input by **154,249** and output by **981**, although its self-reported dollar cost is correct. The tables here and `evidence/operational-audit.json` use final raw meter records. Original generated reports are preserved, not silently repaired.

`wcb/meter.py:303–325` streams the response to the client before appending its record; `wcb/runner/episode.py:935–939` immediately summarizes the log after process completion. The missing final record in the session snapshot is consistent with this race. A future fix should await the session's in-flight meter requests/record flush before summarizing, with a delayed-final-record regression test. This affects telemetry, not the evaluated answers or WCB scores.

## Calls, latency and recovered errors

| Track / phase | Assistant turns / calls | Tool calls | Summed session seconds |
| --- | ---: | ---: | ---: |
| A ingestion | 4,242 | 6,816 | 57,035.622 |
| A agent query | 1,148 | 1,708 | 14,377.834 |
| A oracle query | 1,013 | 1,475 | 14,120.520 |
| B seed ingestion | 713 | 851 | 10,985.443 |
| B daily ingestion | 6,695 | 7,746 | 68,148.133 |
| B query | 928 | 1,214 | 11,639.308 |
| **Total** | **14,739** | **19,810** | **176,306.860** |

The summed session time is **48.9741 hours**, not elapsed runtime: eight workers overlapped. Mean A ingestion is 570.356 s; B daily ingestion 681.481 s; B seed ingestion 998.677 s. Mean query is 281.918 s for A agent, 276.873 s for A oracle and 228.222 s for B.

All 14,739 assistant message/model records and metered calls identify the requested `deepseek-ai/DeepSeek-V4.1-Flash-1017`. Provider statuses: **14,738 × 200; 1 × 502**. The 502 at 2026-11-11 23:02:46 UTC is in B gen-s9-large `meter.jsonl:72`, session `2027-11-01.ingest/stdout.log:414`. Lines 417–423 show Pi's built-in automatic retry, attempt 1 after two seconds, succeeding. This is a disclosed within-session harness retry, not a replay of a benchmark session. Initial notes saying “no retries” mean no manual session reruns, not that Pi's default transport retry was disabled.

There are 275 tool-error events (A 154, B 121), separate from provider errors; all 19,810 tool starts have matching ends. Assistant stop records: 14,378 `toolUse`, 360 `stop`, one transient `error`. Tool errors were not automatically counted as failed benchmark sessions.

## Critical experiment security issue: credential visible to tools

Four measured sessions ran environment-inspection commands that exposed the live provider credential in tool output. Filters such as `env | grep -i PI_` also match the `API_` substring in the credential variable name. Because Bash inherited the provider key, the credential became model-readable. This is a failure of the experiment adapter's credential isolation; absence of host secret-file mounts did not prevent it.

Affected original logs:

```text
track-a/shards/gen-s8-w4/gen-s8-w4/r1/sessions/cp6.query/stdout.log
track-a/shards/gen-s8-w4/gen-s8-w4/r1/sessions/cp1.query-oracle/stdout.log
track-a/shards/gen-s7-w2/gen-s7-w2/r1/sessions/cp4.query-oracle/stdout.log
track-b/shards/gen-s10-w2-small/gen-s10-w2-small/r1/sessions/cp3.query/stdout.log
```

Their four assembled copies contained the same value. **Do not publish the unredacted originals.** An exact-byte scan initially found those eight files; the parent then copied them to restricted `runs/.credential-quarantine-deepseek-2026-11-12/` (directory 0700, files 0600) and redacted all eight shareable paths. There were **56 substitutions** across originals and assembled copies. The redaction marker is `[REDACTED_TOKEN_FACTORY_API_KEY]`. Exact original/sanitized hashes and paths are in `evidence/transcript-redaction.json`; no credential value is in that manifest.

The shareable run and results trees passed a new exact-credential-byte scan after redaction. Answers, snapshots, scores and token/cost records were not modified. Sanitization is a transcript transformation, explicitly recorded rather than represented as untouched raw evidence. The restricted originals remain local and must not enter Git or downloadable archives.

**Rotate/revoke this Token Factory key before reuse. Rotation was not performed or implied.** No evidence of deliberate external exfiltration was established; the verified exposure is to model input/output and local transcripts. That distinction does not make the key safe to retain. Before another run, put upstream authentication in a host-side broker/proxy and remove provider credentials from the model's tool namespace. Output redaction is defense in depth, not a substitute for making secrets inaccessible to tools.

## One-shot service restarted after successful completion

After the one-shot orchestrator completed, the supervisor restarted it. Its replay guard rejected existing `started.json`; **no measured sessions replayed**. After eleven restart attempts the service was marked failed at 03:21:32 UTC. Because the startup command used `>` redirection, these restarts overwrote `orchestrator.log` with the refusal traceback.

This is an **experiment-wrapper/supervisor issue**, not a failed evaluation. `completed.json`, 22 append-only `outcomes.jsonl` entries, all shard run states and scores establish completion. Preserve those records; do not treat the final service status as authoritative benchmark status. Future one-shot runs should use an appropriate no-restart lifecycle and append-only orchestration logs. The exact measured orchestration script remains frozen in `config/` rather than being patched after the fact.

## Provenance and validation

Both score commands were rerun independently into scratch output directories. Headline, worlds, questions, breakdowns and notes agree **exactly** with the original generated reports. All configuration hashes remain equal to the pre-run manifest. A separate audit verified session metadata, usage, answers and transcript copies against shards before sanitization; corresponding redacted shard/assembled logs also share the same sanitized hash.

`evidence/operational-audit.json` contains machine-readable session/phase totals and completion outcomes. `scores-track-{a,b}.json` and `evidence/generated-track-{a,b}.md` preserve generated scores, including the small efficiency undercount above. [Preflight](PREFLIGHT.md) records the full test suite, lint, document readers and perfect-answer controls.
