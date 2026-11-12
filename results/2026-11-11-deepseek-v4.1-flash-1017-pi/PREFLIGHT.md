# Preflight and comparability

The updated benchmark has no test/lint blocker for this development-world evaluation. Provider and isolated-runtime checks are separate from benchmark validation; passing the suite does not validate a full model run.

## Benchmark verification

An independent verification subagent ran these commands at `c623e777a59830ab9bd016dac1fd3ba6896e26d2` without modifying source, rebuilding public worlds, or calling a model:

```text
.venv/bin/python -m pytest
1675 passed in 129.29s (0:02:09)

.venv/bin/ruff check .
All checks passed!

.venv/bin/python -m pytest -v tests/grade/test_perfect_answers.py
12 passed in 5.16s
```

Python 3.11.6, pytest 9.2.0, Ruff 0.17.4. Full output is retained in `evidence/preflight-*.log`.

`tests/grade/test_perfect_answers.py` discovers pilot and every public dev directory with `world.yaml`, builds gold in memory and traverses all checkpoint questions. Its eleven world cases and discovery guard passed. Important qualification: it asserts **base == 1**, not final citation-adjusted score, and supplies no store root. This is a base-correctness positive control, not proof that every store-path citation or full episode works.

## Changes from the Qwen experiment

- Gold v3 → v4; dev-world project summaries regenerated; **33 questions changed**, while inbox inputs did not. Track A seed/oracle conditions therefore changed even with the same external inputs.
- Query prompts now request bare point `value` and optional ungraded `note`. Point grading accepts supported subject-record context and leading dates. Entity narration remains limited.
- List/change citations now use matched-item evidence and event-thread support expansion. Other answer types retain question-wide citation checking. The previous issue is narrowed, not evidence that arbitrary supplemental claims receive semantic citation validation.
- Rubric coverage uses item-local focused passages instead of the answer-wide focus cliff, with a separate padding penalty of up to 0.25. The penalty applies regardless of heuristic versus LLM judge.
- Status rubrics now select the latest project-level change and only dated loops when there are more than six active loops. Store-reader status score rose from 63 to 93 under these changed gold conditions.
- Runner comparisons use current bytes, Git maintenance is disabled for runner-owned commands, and termination/write activity is recorded.
- This run also changes document runtime and bash timeout policy. Holding Pi 1.5.2 fixed does not make its delta versus historical Qwen causal evidence about model quality.

The old Qwen original scores (A 72.3422, Synthesis 84.2704, SIS 98.4145, B 54.9968) remain historical gold-v3/scorer-v0.1 values. Its saved raw archives exist in this orb, but regrading that experiment is not part of the requested new run. Do not compare a subset point-evidence regrade to a full fresh evaluation as if both used identical questions, prompts and runtime.

## Known remaining grader/release limits

These are documented limitations, not newly established failures in the DeepSeek run:

- `same_item` paraphrase matching remains the weaker judge: calibration κ 0.60 versus hand labels, 63/79 decisions; relaxing it created more false positives. One predicted item merging two gold events can match only once by design.
- Rubric lexical errors remain: reversed/denied handoffs with unordered names; shared keyword loop confusion; alternate entity names; true detail absent from gold reducing focus; contradictions without stale groups sometimes marked missing instead of contradicted.
- Calibration tests deliberately preserve **29 known disagreements**, while asserting improvement elsewhere and rubric κ ≥ 0.8. Green tests do not mean these disagreements disappeared.
- Current rubric κ 0.87 is against calibration hand labels, not completed independent human review. A 100-item sample awaits two human labellers; release judge pinning and practitioner realism review remain open.
- Unanswerable questions retain an equal-weight type bucket; SIS is intentionally lenient (untouched seed null baseline 91.5); confidence intervals resample worlds, not repeats or provider randomness.

Source references: `docs/status.md`, `docs/judge.md`, `docs/scoring.md`, `docs/questions.md`, `wcb/grade/answers.py`, `tests/grade/test_perfect_answers.py`, `tests/grade/test_rubric_calibration.py`. The report will assess concrete new errors against actual sources instead of attributing all low scores to this list.

## Isolated document runtime

`docker/smoke_tools.py` was run in a bubblewrap namespace with the separate tools virtualenv mounted at `/opt/tools`, all eleven public **inbox directories only** mounted at `/inputs`, and no benchmark repository/gold mount. It imported and round-tripped the pinned YAML/DOCX/XLSX/PPTX readers, imported pypdf, and extracted all discovered public PDF/DOCX/XLSX/PPTX/Markdown inputs. Exit 0, **all readers work**. Full file-by-file output: `evidence/runtime-smoke.log`. Optional `pdftotext` is unavailable; pypdf covers PDFs.

Dependency pins and transitive package versions are in `config/tools-lock.txt`. This tooling prevents known missing-dependency confounds; it does not prevent the model from writing incorrect parsers or ignoring accessible evidence.
