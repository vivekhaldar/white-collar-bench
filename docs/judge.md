# Judges

Status: v0.1. How free-text answers are matched and checked. See [scoring](scoring.md) for the full grading rules and [formats](formats.md) §3.2 for the gold shapes.

Most of the grading is deterministic: point facts resolve through the world's alias table, dates and numbers are normalized, and list, change and priority scores are arithmetic over matched items. Two decisions need a **judge**:

| Decision | Used by | Question |
|---|---|---|
| `same_item(pred, gold, kind)` | list, priority (`kind: loop`), change (`kind: change`) | Does this predicted item describe the same commitment or change as this gold item? |
| `rubric(answer_text, item, facts)` | status, brief | Does the answer cover this checklist item? `covered`, `missing` or `contradicted` |

The code lives in `wcb/grade/judge.py` (judges), `wcb/grade/matching.py` (candidates and assignment), `wcb/grade/answers.py` (per-question scores) and `wcb/llm/client.py` (model access).

## Choosing a judge

```bash
wcb score runs/my-agent                                   # heuristic judge (default)
wcb score runs/my-agent --judge llm                       # LLM judge, default pinned model
wcb score runs/my-agent --judge llm --judge-model anthropic:claude-opus-5-5
wcb score runs/my-agent --judge llm --judge-model openai:gpt-judge-model
wcb score runs/my-agent --judge llm --judge-model "cmd:claude -p"
```

| | Heuristic | LLM |
|---|---|---|
| Cost | free | one model call per candidate pair and rubric item, times samples; cached |
| Reproducibility | exact | pinned model and prompts, majority vote, decision cache |
| Paraphrases | under-credits loose paraphrases | handles paraphrase and implication |
| Use it for | development loops, CI, quick comparisons | reported results |

Report which judge you used: it is recorded as the judge `name` (`heuristic`, or `llm:<spec>` such as `llm:anthropic:claude-opus-5-5`). Scores from different judges are not comparable.

## Matching list and change items

Matching (`wcb/grade/matching.py`) has two steps.

1. **Candidates.** A predicted item and a gold item are candidates when any of these holds:
   - a predicted `cites` entry is in the gold item's `support`;
   - the predicted `counterparty` resolves through the alias table to the gold counterparty (an ambiguous name such as a shared first name resolves to nothing);
   - the Dice similarity of their content tokens (prediction `text` + `counterparty` + `why`; gold `what` or `summary` + `keywords`) is at least **0.2**.
2. **Confirmation and assignment.** The judge answers `same_item` for every candidate pair; each distinct pair is asked once per question. Confirmed pairs are assigned one-to-one: greedily in order of decreasing similarity, then improved with augmenting paths so the number of matched pairs is the maximum possible. Ties keep input order, so results are deterministic.

Duplicate predictions therefore earn credit once; the extra copy counts against precision.

For priority questions, `must_include`, `worker_active` and `distractors` are combined into one gold list (a loop listed in both `must_include` and `worker_active` appears once, as must-include), and the top `k` predicted items are matched against it.

## Heuristic judge

`HeuristicJudge` uses content tokens: lowercase ASCII words without stopwords and single letters (the `s` of "Patel's"), with single digits kept and a plural `s` stripped from words longer than three letters.

### `same_item`

A prediction matches a gold item when any route holds:

| Route | Rule | Threshold |
|---|---|---|
| Keyword | a gold `keywords` phrase occurs in the prediction (whole words, case- and accent-insensitive) **and** this share of the gold description's tokens occur in the prediction | 0.3 |
| Overlap | token Jaccard between the prediction's text and the gold description | 0.5 |
| Terse | every prediction token occurs in the gold description, except capitalized words after the first (names, which may be aliases), **and** this many tokens are shared | 3 |

The gold description is a loop's `what` or a change's `summary`. Capitalized words are not treated as names when most words are capitalized (Title Case, ALL CAPS).

The thresholds were tuned on `tests/fixtures/mini-world`. These match their loops: "Volume pricing from Cora", "Ingestion design doc review", "Review Samir's ingestion doc", "Reconciliation report". These do not: "Send Ada the February forecast report" against "Send Ada the January reconciliation report", or "Approve Ben's holiday request" against "Approve Ben's GL sandbox access request". The heuristic cannot tell near-identical descriptions apart, such as a reversed decision and its replacement; the one-to-one assignment resolves those by similarity when both are in gold.

### `rubric`

| Verdict | Rule |
|---|---|
| covered | every group in `keywords` has at least one alternative in the answer. An ISO date alternative also matches its prose forms (`5 Feb`, `February 5th`, `2/5`, ...). |
| contradicted | not covered, and every group in `stale` (when there are any) matches. This is how a superseded value presented as current is caught. |
| missing | otherwise |

An item with no keyword groups is covered when 60% of the tokens of its `text` appear in the answer.

The answer text is the `summary` followed by each claim's `text`.

## LLM judge

`LLMJudge` asks a model the same two narrow questions. Every request uses this system prompt:

```text
You are a careful, strict grader for a benchmark about tracking a knowledge worker's commitments, projects and decisions. Follow the output format exactly.
```

### `same_item` prompt

`{noun}` is `commitment` for list and priority items and `change` for change items. `{gold}` is a JSON object with the gold item's key fields: `what`, `counterparty_name`, `counterparty`, `direction`, `status`, `due` for loops; `summary`, `date`, `type` for changes. `{pred}` is the predicted item as JSON without `cites`. Empty fields are omitted and keys are sorted.

```text
Do these two descriptions refer to the same {noun}? Answer YES or NO.

Reference {noun}:
{gold}

Predicted item:
{pred}

Wording, level of detail and field values (status, dates, names) may differ. Answer YES only if both describe the same underlying {noun}; otherwise answer NO. Reply with the single word YES or NO.
```

### `rubric` prompt

`{item}` is the checklist item's `text`, `{facts}` the question's gold `facts` as JSON with sorted keys, and `{answer}` the answer text.

```text
Grade the answer against one checklist item.

Checklist item:
{item}

Ground-truth facts (JSON):
{facts}

Answer:
<<<
{answer}
>>>

Reply with exactly one word:
COVERED - the answer states the checklist item (paraphrase is fine).
MISSING - the answer does not state it.
CONTRADICTED - the answer presents a superseded or conflicting value as current.
```

### Parsing and voting

- The first `YES`/`NO` word in a completion decides `same_item`. The first `COVERED`/`MISSING`/`CONTRADICTED` word decides `rubric`; `NOT COVERED` counts as missing. Markdown and punctuation are ignored.
- Each decision is the majority over `samples` completions. With one sample the request uses temperature 0; with more it uses temperature 1.0.
- Unparseable completions do not vote. Ties, and decisions where no completion parses, resolve conservatively: `NO` for `same_item`, and missing, then covered, then contradicted for `rubric`.
- Each completion may use up to 2,048 output tokens, because some models think before answering.

### Model pinning

The judge model is part of a benchmark release. `wcb score --judge llm` without `--judge-model` uses `anthropic:claude-opus-5-5` (`DEFAULT_LLM_JUDGE` in `wcb/grade/judge.py`). Use a fixed model ID, never an alias that can move. When you publish results, report the judge spec, the number of samples and the benchmark version. The plan recommends a judge from a different model family than the leading entrants, and checking agreement with human grades (κ ≥ 0.8) before a release.

Some current models reject sampling parameters such as `temperature`. When a request fails with HTTP 400 mentioning `temperature`, the client stops sending it and retries. Decisions are then made at the model's default sampling, and the cache keeps re-grading stable.

### Caching

Every decision is cached under the sha256 of the model spec, the sample count, the system prompt and the user prompt. Each line of the JSONL cache records the key, model, decision kind, sample count, decision and raw completions, so it can be audited. Re-grading the same answers reads the cache and makes no model calls. A different model, prompt or sample count misses the cache.

`wcb score` passes a cache path to `make_judge`. Without one, set `WCB_JUDGE_CACHE`; otherwise the cache lives only in memory for that run. Delete the file to force fresh judgments.

## Model back ends

`wcb.llm.client.make_client(spec)` builds the client from `--judge-model`:

| Spec | Back end |
|---|---|
| `anthropic:<model>` | Anthropic Messages API. Uses the official `anthropic` SDK if installed (`pip install white-collar-bench[llm]`). Otherwise it POSTs to `$ANTHROPIC_BASE_URL/v1/messages` (default `https://api.anthropic.com`) with `x-api-key: $ANTHROPIC_API_KEY` and `anthropic-version: 2023-06-01`. A spec without a provider prefix is treated as an Anthropic model. |
| `openai:<model>` | Any OpenAI-compatible endpoint: POST `$OPENAI_BASE_URL/chat/completions` (default `https://api.openai.com/v1`) with `Authorization: Bearer $OPENAI_API_KEY`. Works with OpenRouter, vLLM and similar servers. The header is omitted when no key is set, for local servers. If the server rejects `max_tokens`, the client sends `max_completion_tokens` instead. |
| `cmd:<shell command>` | Runs the command with `/bin/sh -c`, with the prompt on stdin (system prompt first, then a blank line), and reads the completion from stdout. Example: `cmd:claude -p`. |

HTTP back ends use only `urllib`. They retry HTTP 408, 409, 429 and 5xx responses, and connection errors, with exponential backoff and jitter, honouring `Retry-After`. Other errors fail at once.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | | API key for `anthropic:` specs (raw HTTP path; the SDK also finds its own credentials) |
| `ANTHROPIC_BASE_URL` | `https://api.anthropic.com` | Endpoint for `anthropic:` specs, for example a metering proxy |
| `OPENAI_API_KEY` | | Bearer token for `openai:` specs |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | Endpoint for `openai:` specs, for example `https://openrouter.ai/api/v1` or a local vLLM server |
| `WCB_JUDGE_SAMPLES` | `3` | Completions per decision, majority-voted. Set `1` for cheaper local runs. |
| `WCB_JUDGE_CACHE` | | Decision cache file, used when `wcb score` does not pass one |
| `WCB_LLM_MAX_RETRIES` | `4` (`2` for `cmd:`) | Retries per request |
| `WCB_LLM_TIMEOUT` | `120` (`300` for `cmd:`) | Seconds per request |
| `WCB_LLM_EFFORT` | | Optional `output_config.effort` for Anthropic models that support it, for example `low` |
| `WCB_LLM_TEMPERATURE`, `WCB_LLM_MAX_TOKENS` | | Set *for* `cmd:` judges, so the command can pass them to its model |

## Using the judges from Python

```python
from pathlib import Path

from wcb.grade.answers import ScoreContext, score_answers
from wcb.grade.judge import make_judge
from wcb.util.io import read_json
from wcb.world.model import World
from wcb.world.state import state_at

world = World.load("tests/fixtures/mini-world")
ctx = ScoreContext.from_state(world, state_at(world, "2027-01-12"), store_root=Path("my-store"))
judge = make_judge("llm", "anthropic:claude-opus-5-5", cache_path=Path("judge-cache.jsonl"))
scores = score_answers(read_json(".../gold/questions/cp2.json"), read_json("answers.json"), judge, ctx)
```

Each `QuestionScore` carries `base` (before citations), `citation` and `score`, plus `details`: matches with per-attribute credit, rubric verdicts, invalid citations and validation problems.
