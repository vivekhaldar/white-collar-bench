# DeepSeek V4.1 Flash 1017 + Pi: Tracks A and B

**Completed: Track A 84.6439; Track B 67.4833, using the unchanged gold-v4 heuristic scorer.** Execution: 11–12 November 2026 UTC, 7 h 15 min elapsed. All benchmark workdays, people, organizations and source artifacts are synthetic.

**Security action required:** rotate the Token Factory key before reuse. Four sessions exposed it through environment-inspection tool output. Originals are quarantined; shareable transcripts are redacted and scanned. No credential is included in this report. See [operational/security details](OPERATIONS.md#critical-experiment-security-issue-credential-visible-to-tools).

## Executive results

| Evaluation | Score / 100 | World-bootstrap 95% CI |
| --- | ---: | --- |
| **Track A** | **84.6438837251** | **80.4463–87.6696** |
| A Synthesis, oracle store | 90.7947712619 | 88.3733–92.9162 |
| A SIS, mean over days | 98.9940020661 | Not reported |
| A SIS, final day | 98.5572727273 | Not reported |
| **Track B** | **67.4832563997** | **61.8145–71.8994** |

A's Synthesis minus WCB is **6.1508875368 points**; A minus B is **17.1606273253 points**. These are experiment-condition differences, not isolated causal effects of memory serialization or model capability. A starts from a correct structured seed store; B must build memory from raw seed inputs and has different memory constraints.

Scope: pilot + all ten public dev worlds, one repeat per track; **364 sessions**, **2,235/2,235 schema-valid answers** (745 in each of A agent, A oracle and B). Four ingestions hit the 120-turn budget and rolled back; those failures remain in the scores. No timeouts, final output-length truncations, missing answers or manual session replays.

Measured published-rate cost estimate: **$118.813576128** ($54.323347212 A including oracle, $64.490228916 B), excluding smoke/setup probes and analysis agents. Elapsed time is **7:15:11.408390**, while overlapping sessions sum to 48.9741 hours. These are rate-based estimates, not a provider invoice.

Both complete score commands were rerun; headline, worlds, questions, breakdowns and notes match the original generated reports **exactly**. No manual semantic-credit adjustments were applied. The audit identifies real scorer limitations, but there is **no exhaustively adjudicated substance-corrected score** for this run.

## Per-world results

| World | A WCB | A Synthesis | A SIS | B WCB |
| --- | ---: | ---: | ---: | ---: |
| pilot | 67.1231 | 81.9908 | 95.9950 | 46.2086 |
| gen-s1-w1 | 87.7054 | 88.9187 | 99.5733 | 76.9136 |
| gen-s2-w1 | 88.8959 | 92.6579 | 99.3180 | 72.7740 |
| gen-s3-w1 | 91.5239 | 96.0176 | 99.4367 | 72.2774 |
| gen-s4-w2 | 87.8908 | 91.6781 | 99.2750 | 69.7242 |
| gen-s5-small | 83.2498 | 86.7683 | 99.2000 | 62.2291 |
| gen-s6-w1 | 86.7036 | 91.3232 | 99.7033 | 76.0155 |
| gen-s7-w2 | 82.3578 | 94.9533 | 99.2933 | 67.3832 |
| gen-s8-w4 | 83.0158 | 88.4956 | 98.9338 | 64.0521 |
| gen-s9-large | 88.1619 | 93.0956 | 99.2083 | 71.8417 |
| gen-s10-w2-small | 84.4547 | 92.8435 | 98.9973 | 62.8964 |

Pilot is the weakest world on both tracks and contains three of the four failed ingestions. This is an association, not a quantified causal decomposition. Even without a failed session, other worlds exhibit selection, synthesis and grading errors.

## Question types and scoring interpretation

| Bucket | Questions per arm | A | A oracle | B |
| --- | ---: | ---: | ---: | ---: |
| Point | 187 | 87.4577 | 95.9069 | 72.7429 |
| List | 165 | 80.8485 | 89.9971 | 58.0661 |
| Status | 52 | 86.6581 | 82.1424 | 59.8999 |
| Brief | 77 | 82.7461 | 90.7843 | 59.8021 |
| Change | 52 | 54.7614 | 73.2830 | 24.2849 |
| Temporal | 85 | 97.6912 | 98.5343 | 88.3578 |
| Priority | 51 | 85.0280 | 94.7121 | 69.3359 |
| Unanswerable | 76 | 97.3684 | 98.6842 | 97.3684 |

Unanswerable questions of any underlying type occupy their own bucket. The 52 change questions are the clearest weakness on both tracks. Their scores mix real event selection/omission errors with a documented sensitivity to verbose event descriptions; do not interpret all low change scores as either pure model error or pure grader error.

WCB is not percent exactly correct: scores average questions within type buckets, buckets within checkpoints, checkpoints within episodes, repeats within worlds, then worlds equally. The generated type/challenge tables are descriptive breakdowns, not a substitute aggregation. Confidence intervals resample the eleven worlds, not provider randomness; one repeat does not establish a ranking. Unanswerable questions have their own equal-weight bucket. High SIS is not proof of complete useful memory; its null-seed baseline is already high.

From the generated per-question scores (rounded to four decimals), A agent has **327 full / 386 partial / 32 zero**; oracle **468 / 269 / 8**; B **176 / 467 / 102**. All 745 answers in each arm validate. Status answers from the agent store outperform oracle on this sample; an oracle input is not a guaranteed upper bound on a stochastic model's realized answer or lexical score.

## What the traces establish

- **Successful source handling:** A's Translation Help change answer preserves “suggested, no owner agreed” and identifies both source events; B's Akosua obligations answer excludes two suggestions that A incorrectly lists.
- **Query selection after successful retention:** both tracks store and read Nettle's approach-A test-plan decision, yet omit it from status answers. These are not failures to ingest or retrieve the fact.
- **Acceptance and deadline semantics:** both tracks sometimes include unaccepted proposals as formal open obligations; B also turns a calendar booking into a hard due date and invents an owned follow-up from unresolved document questions.
- **Verified semantic matcher limitation:** B's two long, caution-heavy descriptions of real Translation Help events receive zero accepted event matches despite containing those events. This is not a one-to-one assignment issue. The whole answer still contains speculation and an extraneous non-change, so automatic full credit would also be wrong.
- **Closed-support citation limitation:** real supplementary calendar evidence and a true completed-checklist confirmation can lose citation precision because they fall outside supplied gold support. Correctly implementing a closed set is not the same as evaluating semantic support exhaustively.
- **Budget failure rather than input paralysis:** all four failed ingestions perform substantial writes, then keep reconciling/validating until the cap. Rollback turns late finishing failures into durable missing-day knowledge. Pilot later gives stale ownership/go-live answers; B gen-s7 misses a questionnaire introduced on its discarded day.

The [answer audit](ANSWER-AUDIT.md) contains the matched A/B examples, exact question IDs, gold versus predictions, scores, sources and trace lines. The [failure traces](FAILURE-TRACES.md) follow all four failed sessions, including successful controls and the limits of causal interpretation.

## Issues and recommendations before another run

1. **Critical runtime security:** rotate the exposed key and move provider authentication outside the tool namespace. Masking transcript output alone would not prevent the model from reading a secret. This is an experiment-adapter defect, not a synthetic-world error.
2. **Benchmark telemetry:** fix the final meter-record race. One B seed session misses its last call in `session.json` and generated efficiency tokens; final raw meters and Pi usage agree, and WCB scores are unaffected. The exact discrepancy is documented in [operations](OPERATIONS.md#confirmed-meter-finalization-race-no-answer-score-impact).
3. **Scorer calibration and annotation:** add the demonstrated verbose event pairs and closed-support examples to calibration/annotation review. Improve event identity without accepting reversed facts, wrong sibling objects or unsupported speculation. Expand supplementary support narrowly where sources actually corroborate a matched item; do not make all project artifacts interchangeable. Retain official scores and separately version/regrade any change.
4. **Harness finishing behavior:** use a finite completion checklist, expose remaining turns and reduce mirrored state. Test a changed turn budget or partial-state policy as a separate condition, not a silent repair of this run. Preserve failed working trees diagnostically if the runner is extended.
5. **One-shot supervision:** prevent automatic restarts after successful orchestration and use append-only logs. The replay guard prevented duplicate model execution, but restarts overwrote the orchestration log after completion; completion/outcome records remain intact.

No new GitHub issues were opened as part of this request; these findings are recorded here with fix directions and reproduction evidence. No new benchmark/scorer code fixes or additional model runs are included. Existing release caveats, calibration disagreements and human-validation gaps remain documented in [preflight](PREFLIGHT.md).

## Scope and assumptions

- User requested a full run on both tracks using Nebius `deepseek-ai/DeepSeek-V4.1-Flash-1017`, after synchronizing main, with detailed results, findings and issues saved here.
- Main fast-forwarded from `ed8e03370b25b54f500f1e5b002a92636af7c5a0` to `c623e777a59830ab9bd016dac1fd3ba6896e26d2` (merged benchmark fixes). The experiment froze this revision, gold v4 and the current deterministic heuristic scorer (WCB 0.1.0, scorer label 0.1). No benchmark/scorer patches or manual answer repairs are part of the measured run.
- Same scope as the previous experiment: pilot plus all ten public dev worlds, one repeat, Track A with paired oracle queries and SIS, Track B with seed ingestion and no oracle/SIS. These are public development-world results, not a private-test leaderboard submission.
- Pi remains `@earendil-works/pi-coding-agent@1.5.2` with read/bash/edit/write, fresh processes, no persisted conversations, external MCP, skills, context discovery, or personal extensions. This holds the harness version constant, not the entire experiment: benchmark sources, gold, prompts, scorer and document runtime changed.
- Normally eight independent world/track workers, longest worlds first. Within every world, chronology and benchmark session boundaries are unchanged. No measured sessions were replayed. Pi's default within-session transport retry recovered one HTTP 502; it was not disabled, and is separately disclosed.
- Session budgets: 120 assistant turns, ingestion 1,800 s, query 900 s. Bash calls get at most 120 s so the agent can recover from hanging scripts. This is an explicitly changed runtime variant relative to the historical Qwen run.

## Provider configuration and probes

- Authenticated `/v1/models` confirms exact routing key `deepseek-ai/DeepSeek-V4.1-Flash-1017`; the existing `TOKEN_FACTORY_API_KEY` was supplied via environment. The later tool-output exposure and sanitization are documented above; the initial intention not to log its value was not met.
- Official [catalog metadata](https://tokenfactory.nebius.com/api/public/models_info), read on 11 November, lists **1,048,576 context tokens**, FP8, tool calling and reasoning; public endpoint pricing **$0.30/M uncached input, $0.006/M cached input, $1.20/M output**. Direct public-page requests from Python returned 403, but the page-reading tool retrieved the official JSON. Authenticated inference works.
- Reasoning enabled explicitly with `thinking: {type: enabled}`; provider sampling defaults, no seed or effort override. Simple API controls with both default and explicit thinking returned reasoning-token usage and the correct answer. Provider uses `reasoning`, not just `reasoning_content`, for reasoning text; Pi supports both.
- No arbitrary 32k client output cap. Adapter requests the model context ceiling (`max_tokens=1048576`) on every request; a direct short-prompt probe accepted it and stopped normally. This confirms acceptance, **not** that a million output tokens are independently available alongside input. The provider owns remaining-context/output enforcement. No Qwen-specific intentional overflow validation is reused; `/tokenize` and `/v1/tokenize` were unavailable (404).
- Final raw stop reason, process exit, missing/invalid answers and operational incompleteness are recorded separately. Per current runner policy, exit-0 incomplete ingestions retain partial writes and are marked incomplete; actual failed/timed-out ingestions roll back. These outcomes will remain in measured results.

## Runtime and isolation

Fresh bubblewrap user/PID/mount namespaces, disposable home/config/tmp and writable benchmark workspace. The repository, public gold, other world outputs and host credential files were not mounted. Network was shared, not endpoint-allowlisted: not leaderboard-verified isolation. **The provider credential environment variable was nevertheless visible to Bash**, so filesystem isolation did not establish secret isolation. See the exposure incident and remediation above.

Document dependencies followed `docker/requirements-tools.txt`: PyYAML 6.0.3, pypdf 7.0.1, python-docx 1.2.0, openpyxl 3.1.5, python-pptx 1.0.2. A separate tools virtualenv was mounted read-only inside the actual tool namespace; transitive packages and host versions are recorded in `config/tools-lock.txt`, `config/pi-package-lock.json` and `evidence/environment.json`. Preflight tested document parsing in that namespace, including actual public synthetic files. No dependency installation was performed during measured sessions. A missing `awk` was encountered and recovered by using Python; all rich-document readers had passed preflight.

## Evidence and running notes

- [Preflight and comparability](PREFLIGHT.md): benchmark validation, changes since Qwen, remaining known grading limits.
- [Source-grounded answer audit](ANSWER-AUDIT.md): matched completed A/B checkpoint examples, ingestion→memory→query traces, justified deductions and verified semantic matching/support-set limitations. Exact answers and grading details are retained in `evidence/matched-cp1-audit.json`. This is a sampled diagnostic, not a semantic regrade of the full run.
- [Operational/security audit](OPERATIONS.md): final call/token/cost accounting, metering discrepancy, credential remediation and supervisor issue.
- [Turn-budget failure traces](FAILURE-TRACES.md): four source-grounded timelines and downstream answer examples.
- `scores-track-a.json`, `scores-track-b.json`: unmodified generated score data; generated Markdown copies are in `evidence/`. `evidence/operational-audit.json` records authoritative final-meter accounting separately.
- `config/adapter.yaml`, `pi_nebius.py`, `runtime.mjs`, `run_all.py`: exact experiment configuration and orchestration; no secrets. Runtime installation paths can be supplied via `WCB_PI_NODE_MODULES` and `WCB_TOOLS_VENV`.
- `evidence/provider-api-metadata.json`: authenticated model ID lookup.
- `evidence/provider-probes.json`, `provider-budget-probes.json`: excluded configuration controls; not measured benchmark answers.
- Raw runs live under ignored `runs/pi-deepseek-v41-flash-1017/`; summaries and report evidence are saved here. Sanitized transcript/snapshot bundles and a separate metering/configuration archive are outside Git, with hashes/provenance in `evidence/archive-manifest.json`. Unredacted originals are quarantined separately and must not be bundled.

The historical Qwen A 72.3422 / B 54.9968 run used gold v3, earlier scoring/prompts and a different document runtime. These new numbers are numerically higher but **not a controlled DeepSeek-versus-Qwen model-quality delta**. No historical Qwen regrade or new private-test evaluation was requested/performed. Only reports and reproducibility evidence belong in Git; large sanitized archives and restricted originals remain outside Git.

### Evidence bundles and regrading

Outside Git, under this thread's `.amp/in/artifacts/`:

- `deepseek-v41-flash-1017-pi-track-a-sanitized.tar.gz`: 71,153,748 bytes; 25,347 manifest-verified files, including answers, metadata, redacted transcripts and snapshots excluding Git internals.
- `deepseek-v41-flash-1017-pi-track-b-sanitized.tar.gz`: 107,206,680 bytes; 4,516 manifest-verified files with the same scope.
- `deepseek-v41-flash-1017-pi-metering-and-config.tar.gz`: 308,174 bytes; 12 verified files supplementing WCB bundles with final meter logs, frozen adapter/runtime, completion outcomes and redaction provenance.

Every archive member's hash and byte size was checked against its manifest; every member passed the exact credential-byte scan. `evidence/archive-manifest.json` records archive SHA-256 values and local paths. These bundles exclude the restricted unredacted originals and dependency installations. No archive is a private-test leaderboard submission.

At the recorded benchmark revision, after building its public gold, the retained measured directories can be rescored without model calls:

```bash
.venv/bin/wcb score runs/pi-deepseek-v41-flash-1017/track-a/measured --out /tmp/deepseek-regrade-a
.venv/bin/wcb score runs/pi-deepseek-v41-flash-1017/track-b/measured --out /tmp/deepseek-regrade-b
```

Use the **frozen revision**, not a later main, to reproduce these scores. Unpacked WCB bundles place world directories and `run.json` under their archive root; supply that root instead and restore world paths if the repository location differs. To reproduce inference rather than just grading, rebuild the pinned Pi/document tool installations from the saved locks and first fix credential isolation with a rotated key. Do not blindly rerun the frozen insecure adapter.

## Execution log

- 20:05:56 UTC: started supervised service `deepseek-benchmark`; eight workers launched the first four worlds on both tracks. Exact start/revision recorded in `runs/pi-deepseek-v41-flash-1017/started.json`; independent shard logs and append-only outcomes retained there.
- Two excluded mini-world end-to-end smoke jobs were still finishing when measurement began. They briefly added two concurrent provider clients; neither their answers nor their usage belongs to measured scores/costs. Both are complete: A six of six sessions operationally OK, 13/13 answers in each arm, WCB 91.1797, Synthesis 92.5595, SIS 97.77, 854.4 s, $0.301313; B five of five sessions OK, 13/13 answers, WCB 72.4329, 998.3 s, $0.356806. Exact score reports are `evidence/smoke-{a,b}-score.json`. These fixture scores are runtime controls, not estimates of full-world performance. Track B's sole scoring note is the expected omission of Track-A-only SIS.
- 20:23 UTC: first measured ingestions completed normally; early Track A sessions took approximately 466–685 s and first completed B seed ingestions took 707–984 s. This is an hours-long evaluation, not a latency-normalized comparison. No measured sessions were replayed.
- 20:40 UTC: 26 measured sessions complete (15 A, 11 B), all operationally OK with final `stop`; 1,342 metered provider requests, all HTTP 200 with usage present. No full world has completed, so no aggregate score is reported. Final operational/cost auditing is delegated independently while source-grounded answer analysis and report preparation proceed.
- 21:05 UTC: 54 sessions complete; completed-session estimate $16.10. 21:19: 68 sessions; $20.09. These were progress snapshots, not final accounting.
- 12 November 02:04 UTC: 342/364 sessions, 17/22 shards complete; four turn-limit ingestions and one recovered HTTP 502 now recorded. No manual retries or cap changes.
- 03:21:08 UTC: all 22 shards and both assembled score reports complete. The supervisor subsequently restarted the protected one-shot and overwrote its log; append-only outcomes and completion metadata survived.
- After completion: reconciled final meters and Pi usage, independently reproduced both score reports, quarantined/redacted eight credential-bearing transcript copies and scanned the shareable trees. Source-grounded and operational findings were consolidated here. No score, answer or store repair was made.
