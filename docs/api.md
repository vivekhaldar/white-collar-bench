# Python API

Everything the `wcb` command does is available from Python. Use it when you want to drive the benchmark from your own evaluation harness, inspect worlds and gold in a notebook, or build tooling around stores. The command line is a thin layer over these functions (`wcb/cli.py`).

Install from a checkout (`uv pip install -e '.[dev]'`). The package needs Python 3.10 or later, PyYAML and jsonschema. Worlds are read from the checkout's `worlds/` directory or from any path.

Names not listed here, including functions starting with `_` and module internals, may change between releases.

## Running and scoring

```python
from pathlib import Path
from wcb.runner.episode import RunConfig, run
from wcb.grade.score import score_run

cfg = RunConfig(
    adapter=Path("adapters/examples/null.yaml"),
    worlds=["pilot"],          # names under worlds/ or paths
    split=None,                # or "dev", or a directory path
    track="A",                 # "A" or "B"
    repeats=1,
    out=Path("runs/null"),
    oracle=True,               # Track A: also answer from oracle stores
)
run(cfg)                       # returns 0; raises ValueError/FileNotFoundError on bad config

report = score_run(Path("runs/null"))            # heuristic judge; writes runs/null/scores/
print(report.summary_text())
print(report.data["headline"]["wcb"], report.data["headline"]["sis"])
```

`RunConfig` also takes `max_days`, `workspace_root`, `resume`, `skip_ingest`, `meter` and `build`, with the same meanings as the [command-line options](running.md). `score_run(run_dir, judge="llm", judge_model="anthropic:<model>")` uses the LLM judge ([judges](judge.md)). `report.data` is exactly `report.json`; its fields are described in [scoring](scoring.md).

| Function | Purpose |
|---|---|
| `wcb.runner.doctor.doctor(adapter_path, *, world=None, track="A", out=None)` | Smoke-test an adapter on the mini world; returns `DoctorResult` with `.ok`, `.checks` and `.summary` (`format_result(res)` renders it) |
| `wcb.runner.adapter.load_adapter(path)` | Parse and validate an adapter file; raises `AdapterError` with a message saying what to fix |
| `wcb.bundle.bundle_run(run_dir, out, *, logs=False, snapshots=False)` | Write a `.tar.gz` of a scored run; returns the manifest |
| `wcb.grade.answers.score_answers(gold_doc, answers, judge, ctx)` | Score one answers dict against one gold questions file (example in [judges](judge.md)) |
| `wcb.grade.agreement.collect_decisions(run_dirs)`, `sample_decisions(decisions, n, seed)`, `label_with_judge(records, judge, name)`, `agreement(records)`, `cohen_kappa(a, b)` | Judge-agreement study: the functions behind `wcb judge` ([judges](judge.md#measuring-judge-agreement)) |

## Stores

```python
from pathlib import Path
from wcb.store.parse import load_store
from wcb.contract.validate import validate_store, validate_answers

store = load_store(Path("runs/null/pilot/r1/snapshots/2027-03-06"))
for rec in store.of_type("project"):
    print(rec.id, rec.meta.get("status"), (rec.section("Current state") or "")[:80])
loop = store.get("loops/send-the-revised-scorecard")    # by ID or path; None if absent

for issue in validate_store(store.root):
    print(issue.format())        # issue.severity is "error" or "warning"
```

- `Store` has `root`, `records` (ID to `Record`), `other_files`, `of_type(type)`, `get(id_or_path)`, `iter_text()` and `all_text()`.
- `Record` has `id`, `expected_id`, `path`, `type`, `meta` (front matter, with dates as ISO strings), `body`, `sections` and `section(title)`. If the front matter could not be read, `error` says why.
- `validate_store(root, *, secrets=None, delivered=None)` checks the [contract](contract.md). With a world's `secrets` and the set of `delivered` artifact IDs, it also reports planted secrets and citations of inputs that were not yet delivered.
- `validate_answers(answers_path, questions_path=None)` checks an answers file against the schema and, if given the questions, their IDs and types.

## Worlds and gold

```python
from wcb.paths import resolve_world, resolve_split
from wcb.world.model import World
from wcb.world.state import state_at

w = World.load(resolve_world("pilot"))
print(w.id, w.worker, w.episode_days(), [c["id"] for c in w.checkpoints()])
st = state_at(w, "2027-03-04")          # gold state knowable at the end of that day
for cid, loop in st["loops"].items():
    print(cid, loop["status"], loop["debtor"], "owes", loop["creditor"], loop["what"])
```

| Name | Purpose |
|---|---|
| `World.load(dir)` | Parse `world.yaml` and `world.jsonl`. Attributes: `meta`, `events`, `artifacts` (ID to `Artifact`), `by_id`, `id`, `worker`. Methods: `seed_dates()`, `episode_days()`, `checkpoints()`, `all_dates()`, `artifacts_on(date)`, `artifacts_through(date)`, `known_on()` (event ID to the date it became knowable), `revealing_artifacts()` and `alias_table()`. |
| `state_at(world, date)` | Gold state at the end of `date`: `entities`, `loops`, `decisions`, `events`, `unknowable`, `delivered` and `secrets` ([formats](formats.md) §3). |
| `wcb.world.check.check_world(dir)` | Consistency checks; returns issues. |
| `wcb.world.build.build_world(dir)` | Check, then write manifests and `gold/`. Returns `BuildResult` with `ok`, `issues` and `written`. |
| `wcb.world.build.gold_status(dir)`, `ensure_built(dir, echo=None)` | `None` if the world's gold is current, else the reason; build only if needed (raises `ValueError` if the build fails). `run` calls `ensure_built` unless `RunConfig(build=False)`. |
| `wcb.world.stats.world_stats(dir)` | Calibration statistics as a dict. |
| `wcb.world.generate.generate_world(*, seed, weeks=1, out_dir, world_id=None, size="standard", llm=False, llm_model=None, build=True)` | Generate a world ([generator](generator.md)). Raises `GenerationError` if the result fails its checks. |
| `wcb.store.oracle.render_oracle_store(world, state, out_dir)` | Write the oracle store for a state. |
| `wcb.paths.resolve_world(spec)`, `resolve_split(spec)` | Turn names or paths into world directories. |

Built gold lives in each world's `gold/` directory: `gold/state/<date>.json`, `gold/oracle-store/<date>/` and `gold/questions/<checkpoint>.json` ([worlds](worlds.md)). Never let an agent under test read it.

## Metering model calls

```python
from pathlib import Path
from wcb.meter import MeterProxy, summarize

with MeterProxy(Path("runs/meter.jsonl")) as proxy:      # 127.0.0.1, free port
    env = proxy.session_env("my-session")                # ANTHROPIC_BASE_URL, OPENAI_BASE_URL, WCB_LLM_BASE_URL
    ...                                                  # start your agent with env
print(summarize(Path("runs/meter.jsonl"), "my-session"))  # calls, tokens by kind, models
```

The proxy forwards requests unchanged to the provider (or to the gateway in `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` when those are set) and records token usage from JSON and streamed responses. `wcb meter serve` runs it from the command line.

## Privacy scan

```python
from pathlib import Path
from wcb.privacy.scan import scan

for f in scan(Path("/path/to/private/repo"), [Path("worlds/pilot")]):
    print(f.format())     # f.severity is "low", "medium" or "high"
```

See [privacy](privacy.md) for what is matched and how to allowlist reviewed terms.
