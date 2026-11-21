# Running the benchmark

Status: v0.1. This is the step-by-step guide for running an agent on white-collar-bench. See [scoring](scoring.md) for the run protocol and how answers are graded, and [formats](formats.md) for every file format referred to here.

The runner owns the episode: the workspace, the simulated clock, the inbox, snapshots and timeouts. You supply an **adapter**: a small YAML file that says how to start your agent for one session. Your agent only ever sees its workspace.

## 1. Install

Python 3.10 or later is required. `git` is recommended: the runner keeps a git history in each workspace for your agent to use.

With [uv](https://docs.astral.sh/uv/):

```bash
git clone <this repository> white-collar-bench && cd white-collar-bench
uv venv && uv pip install -e '.[dev]'
source .venv/bin/activate
wcb --version
```

With pip:

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
source .venv/bin/activate
```

Worlds (`worlds/`) and the contract (`contract/`) come with the source checkout.

## 2. Find and build worlds

```bash
wcb world list                   # every world under worlds/, with days, checkpoints and gold status
wcb world build pilot            # derive manifests, gold state, oracle stores and questions
wcb world build --all --if-stale # build every world whose gold is missing or out of date
wcb world questions pilot        # the questions, with unanswerable ones marked (dev worlds only)
```

A world must be **built** before it can be run: the runner needs `inbox/<date>/manifest.json`, `gold/oracle-store/<date>/` and `gold/questions/<checkpoint>.json`. Built gold is not committed to the repository, so after cloning or pulling, `wcb run` builds each world whose gold is missing or stale before any session starts (a few seconds per world). It knows a world is stale from `gold/BUILD.json`, which records the gold version and a digest of the world's sources ([worlds](worlds.md#what-wcb-world-build-writes)). Pass `--no-build` to skip this; then a world with missing files stops the run, with the command that fixes it.

Worlds are named by their path under `worlds/` (`pilot`, `dev/w01`) or given as a directory path.

## 3. Try the null baseline

The null baseline does nothing during ingestion and abstains on every question. It is the score floor and the smallest working adapter:

```bash
wcb run --adapter adapters/examples/null.yaml --world pilot --out runs/null
wcb score runs/null
```

Each line of progress output shows the world, repeat, session, outcome, exit code and wall time:

```text
[pilot r1] seed store 2027-02-26: 41 files in workspace /tmp/wcb-ws-k2v9x1
[pilot r1] 2027-03-01 ingest              ok      exit=0     0.1s
[pilot r1] cp1 query (2027-03-02)         ok      exit=0     0.1s  answers 12/12
```

## 4. Write an adapter

```yaml
# adapters/my-agent.yaml
name: my-agent                      # required
version: 0.3.1                      # recorded in run.json and reports
model: provider/model-name          # reported on the leaderboard
cmd: ["my-agent", "run", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]
ingest:
  timeout_s: 1800
query:
  cmd: ["my-agent", "run", "--cwd", "{workspace}", "--prompt-file", "{prompt}", "--read-only"]
  timeout_s: 900
cwd: "{workspace}"
env: {MY_AGENT_MODE: benchmark}
env_passthrough: [MY_PROVIDER_API_KEY]
```

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Short identifier for your agent. |
| `version`, `model` | `unspecified` | Recorded in `run.json`. A missing value is a warning. |
| `cmd` | required (here or per phase) | A list runs the program directly with no shell. A string runs with `/bin/sh -c`. |
| `cwd` | `{workspace}` | Working directory. A relative path is resolved against the adapter file's directory. `null` means the directory you ran `wcb` from. |
| `timeout_s` | 1800 for ingest, 900 for query | Wall-clock limit per session, in seconds. |
| `env` | none | Literal environment variables. Values may use placeholders. |
| `env_passthrough` | none | Names of variables copied from your environment, typically API keys. |
| `ingest:`, `query:` | | Per-phase `cmd`, `cwd` and `timeout_s`, overriding the top-level values. |

Unknown keys are reported as warnings, because they are usually typos. A missing command or a value of the wrong type is an error that lists every problem at once.

### Placeholders

Placeholders are filled in `cmd`, `cwd` and `env` values:

| Placeholder | Value |
|---|---|
| `{workspace}` | Absolute path of the workspace: the store the agent works on. |
| `{prompt}` | Absolute path of the prompt file, `<session_dir>/prompt.md`. |
| `{prompt_text}` | The prompt itself. |
| `{date}` | The simulated date, `YYYY-MM-DD`. Treat it as today. |
| `{phase}` | `ingest` or `query`. |
| `{track}` | `A` or `B`. |
| `{session_dir}` | Absolute path of this session's log directory, outside the workspace. Your harness may write transcripts or traces here. |
| `{adapter_dir}` | Absolute path of the directory holding the adapter file, for wrapper scripts kept next to it. |

In a **list** command each element is substituted as is, so values with spaces stay one argument. In a **string** command each substituted value is shell-quoted. Do not put quotes around placeholders yourself: write `--cwd {workspace}`, not `--cwd "{workspace}"`. Shell syntax such as `${HOME}` is left alone.

```yaml
# A wrapper script next to the adapter, reading the prompt from stdin:
cmd: "{adapter_dir}/run-agent.sh {workspace} < {prompt}"
```

### Environment

Sessions do not inherit your whole environment. Each session gets:

- `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR` and `SHELL` from your environment, when set;
- the variables named in `env_passthrough`, then the `env` mapping;
- `WCB_DATE`, `WCB_PHASE`, `WCB_TRACK`, `WCB_WORKSPACE`, `WCB_PROMPT_FILE` and `WCB_SESSION_DIR`, which cannot be overridden.

The directory of the Python interpreter running `wcb` is put first on `PATH`. When you run `wcb` from a virtual environment (`.venv/bin/wcb`), `python` in a command therefore resolves to that environment's interpreter, which has `wcb` installed. `adapters/examples/null.yaml` relies on this with `cmd: ["python", "-I", "-m", "wcb.baselines.null"]`. If your Python installation provides only `python3`, use that name instead. Setting `PATH` in `env` replaces the whole value.

Keep `-I` (or `-P` on Python 3.11+) when you start a module with `python -m` or code with `python -c`. Without it Python puts its working directory, the workspace, first on `sys.path`, so a file the agent leaves at the store root (`json.py`, a `wcb/` directory) replaces the real module in every later session. `wcb run` warns about adapters that do this ([adapters](adapters.md#environment)).

stdin is empty (`/dev/null`). An agent that waits for interactive input or approval will time out, so run your agent in its non-interactive mode with the permissions it needs to read and write files in the workspace.

### What the agent sees

**Ingestion session, Track A.** The workspace holds the store (`CONTRACT.md`, `people/`, `projects/`, `loops/`, `logs/` and so on) and the day's inputs in `inbox/<date>/` with a `manifest.json`. The prompt is:

> Today is 2027-03-01. New inputs are in `inbox/2027-03-01/` (see `manifest.json`). Incorporate them into the store following `CONTRACT.md`. Inputs will not be available after this session.

**Query session.** The workspace is a throwaway copy of the store, with its git history, plus `.wcb/questions.json` and `.wcb/answer-schema.json`. Store files are read-only. The agent writes `.wcb/answers.json`. A point answer's `value` holds only the answer (a role, a date, a name); any explanation goes in its optional `note`, which is not graded ([formats §4](formats.md#4-answers-wcbanswersjson)). Check the format with `wcb validate answers answers.json --questions questions.json`.

**Usage.** In any session the agent may write `.wcb/usage.json` with `input_tokens`, `output_tokens`, `cost_usd`, `tool_calls` and `model`. The runner copies it into the session's log directory and `session.json`. The runner removes `.wcb/` and `inbox/` after every session.

Prompts are fixed benchmark text, listed in [adapters](adapters.md#standard-prompts) and `wcb/runner/prompts.py`. Your adapter may wrap them in its own system prompt, but must not add knowledge about any world.

## 5. Run

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-pilot
wcb run --adapter adapters/my-agent.yaml --split dev --repeats 3 --out runs/my-agent-dev
```

| Option | Meaning |
|---|---|
| `--world W` | A world name or path. Repeat it to run several worlds. |
| `--split S` | Every world in `worlds/S/`, or in directory `S` if it is a path (for example a private test split). Can be combined with `--world`. |
| `--track A\|B` | Track A (default) uses the store contract; Track B uses an open representation (see §8). |
| `--repeats N` | Independent episodes per world, in `r1/`, `r2/`, ... |
| `--out DIR` | Run directory. It must be new or empty unless you pass `--resume`. |
| `--oracle` / `--no-oracle` | Track A: also ask each checkpoint's questions against the oracle store (default on). |
| `--max-days N` | Play only the first N episode days and their checkpoints. Useful for a quick check. |
| `--suite lite\|micro` | Run a reduced suite: a fixed set of worlds and days, scored as `WCB-lite` or `WCB-micro` for cheap comparisons ([reduced suites](lite.md)). Sets the worlds and `--max-days`. |
| `--workspace-root DIR` | Where temporary workspaces are created (default: the system temp directory). |
| `--resume` | Continue an interrupted run (see §6). |
| `--skip-ingest` | Run only oracle query sessions (see §7). |
| `--build` / `--no-build` | Build worlds whose gold is missing or stale before running (default on; see §2). |
| `--meter` | Route each session's model calls through a local metering proxy, so token counts are measured rather than self-reported (see §7a). `--meter-bind` and `--meter-host` set where it listens and how sessions reach it. |

An episode runs like this:

1. **Start.** Track A: the workspace becomes a copy of the world's seed store (`gold/oracle-store/<seed end>/`) plus `CONTRACT.md`, and is committed to git. Like every oracle store it holds only what the inputs delivered by then show: aliases an input has used, and no hint of people or loops revealed later ([worlds](worlds.md#oracle-stores)).
2. **Each day.** The runner copies `inbox/<date>/` into the workspace, writes the prompt and runs the ingest command in a fresh process. Afterwards it removes `inbox/` and `.wcb/`, snapshots the store to `snapshots/<date>/` and commits (`wcb: after <date> ingest`). The runner's git commands ignore your global and system git config, replace the workspace's `.git/config` with the runner's own, and never start automatic `gc` or `maintenance`, so no background repack is still changing `.git` when the store is copied for a query session.
3. **Checkpoint days.** After that day's ingestion, the runner runs a query session on a read-only copy of the store, saves the answers and discards the copy.
4. **Oracle sessions.** Track A only: after the episode, each checkpoint's questions are asked again against `gold/oracle-store/<checkpoint date>/` plus `CONTRACT.md`, in a separate session with the same adapter. The scores measure synthesis alone.

**Failed sessions.** A non-zero exit or a timeout fails the session. A failed ingest session leaves the store as it was before the session: the runner restores it from the previous snapshot, and the day's snapshot equals the previous day's. A failed query session counts as empty answers. The run carries on either way, and `wcb run` exits 0 when the run completes, whatever the sessions' outcomes.

**Incomplete and no-op sessions.** An agent that stops early, or whose final response is cut off by an output-token limit, still exits 0; that is the agent's outcome and the session is not failed, restored or retried. If the agent reports it in `.wcb/usage.json` (`termination`, which `wcb.agents.wrap` writes for Claude Code and Codex), `session.json` gets `"incomplete": true` and a note, and the run log marks the session `incomplete (<reason>)`. Every ingest session's `session.json` also counts the files it added, modified and removed (`store_changes`), and the run log says when a successful ingest session changed nothing in the store. A day with nothing worth recording can legitimately change nothing, so such sessions are neither retried nor penalized ([formats §6](formats.md#6-run-directory)).

**Session processes.** On timeout the runner sends SIGTERM to every process of the session, then SIGKILL after 10 seconds. When the agent's main process exits, any process it leaves running is killed too, including processes that left its process group: daemons, `setsid cmd &`, Node's `detached: true`. On Linux the runner makes itself a child subreaper (`prctl(PR_SET_CHILD_SUBREAPER)`) during each session, so such orphans are re-parented to it rather than to init, and it kills them. Elsewhere, macOS included, only the session's process group is signalled; run the agent in a container (`docker run --rm --init`, [isolation](#container-isolation)) so that all its processes stop with the container. A process started by another service is not the session's and is not found either (for example `docker run -d`, `systemd-run`, `at`).

**Between sessions.** Before each ingest session and each query of the agent's store, the runner checks that the workspace still matches the last snapshot. A change, whether from a process that escaped its session or an edit by hand, is reverted and listed in that session's `notes`, so it is never credited to the next day.

**What a session leaves behind.** After each session the runner gives the owner read permission on every file and full permission on every directory in the workspace, clears macOS file flags such as `uchg`, and deletes FIFOs, sockets and device files (noted in `notes`). An agent that runs `chmod 000` on part of its store therefore cannot stop the run. If the store still cannot be read, copied or cleaned, for example because the agent wrote files as another user, the session fails (`status: failed`, with the error in `notes`) and the store is restored from the previous snapshot. If even the workspace cannot be cleaned, the episode continues in a new workspace rebuilt from that snapshot, and `wcb run` prints the old directory's path so you can delete it.

## 6. Resume

If a run stops (Ctrl-C, SIGTERM, SIGHUP when the terminal or ssh connection closes, SIGQUIT, a crash or a machine restart), run the same command again with `--resume`. On SIGTERM, SIGHUP and SIGQUIT the runner stops the running session's processes and marks `run.json` and `state.json` `interrupted`, as for Ctrl-C:

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-pilot --resume
```

- Ingest sessions that exited 0 within their timeout are skipped, and query sessions that finished are skipped.
- From the first session that has to run, every later session of that episode runs again, because it depends on the store.
- The workspace is found through `<run>/<world>/r<k>/state.json`. If the temporary directory is gone, the runner rebuilds it from the latest snapshot. Snapshots are the source of truth, and git history from before the rebuild is lost.
- Ingest sessions that failed or timed out are run again. `--resume` is for recovering from infrastructure problems. Do not use it to retry an agent's own failures in a reported run.
- `--resume` with a larger `--max-days`, more `--repeats` or extra `--world`s extends an existing run. So does a resume without `--skip-ingest` of a `--skip-ingest` run: it adds the agent's episodes. `run.json` records each resume's time in `resumed_at` and its command line and options in `resumed_with`. Its `options` describe the whole run, and `wcb score` reads them to decide what to score: `max_days` is the largest given, or none if any invocation played every day, and `skip_ingest` stays true only if every invocation used `--skip-ingest`.

## 7. Oracle-only runs

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-synthesis --skip-ingest
```

`--skip-ingest` runs no ingestion. For every checkpoint it runs only the query session against the oracle store. This measures synthesis alone, at a fraction of the cost of a full run, and is useful while working on the query side of an agent. It is Track A only.

## 7a. Metered runs

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-metered --meter
```

With `--meter` the runner starts a proxy (`wcb/meter.py`) on a free port and points every session at it:

| Variable | Value |
|---|---|
| `ANTHROPIC_BASE_URL` | `http://127.0.0.1:<port>/t/<tag>/anthropic` |
| `OPENAI_BASE_URL` | `http://127.0.0.1:<port>/t/<tag>/openai/v1` |
| `WCB_LLM_BASE_URL` | `http://127.0.0.1:<port>/t/<tag>`; append `/anthropic` or `/openai/v1` |

`<tag>` names the world, repeat, session and attempt. The proxy forwards each request unchanged to the real endpoint, which is the provider or whatever `ANTHROPIC_BASE_URL` / `OPENAI_BASE_URL` held when you started `wcb run`. It streams the response back and logs the call to `<run>/meter.jsonl`. After each session the runner adds its totals to `session.json` as `metered_usage`: calls, input, output, cache-read and cache-write tokens, and models. `wcb score` then uses these measured token counts instead of the agent's self-reported ones. Cost and tool calls are still self-reported.

Most SDKs and CLI agents read these variables, including the Anthropic and OpenAI SDKs, Claude Code, Codex and the simple harness. An agent that ignores them, or calls a provider the proxy does not know, is not metered. Its `metered_usage` then shows `calls: 0`, which is itself a useful check.

**Containers.** Inside a container, `127.0.0.1` is the container itself. Either run the container with `--network host` (Linux), or start the proxy on an address the container can reach and give sessions that address, for example `--meter-bind 0.0.0.0 --meter-host host.docker.internal` with `--add-host=host.docker.internal:host-gateway` in the `docker run` command. The proxy forwards your API credentials, so only bind it to addresses that untrusted machines cannot reach.

`wcb meter serve --log FILE` runs the same proxy on its own, and `wcb meter summary FILE [--tag T]` prints totals.

## 8. Track B

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --track B --out runs/my-agent-b
```

In Track B there is no contract and no seed store. The workspace starts empty except for `GOALS.md`, a one-paragraph goal statement. Then one **seed session** delivers every seed date's inbox at once: `inbox/<date>/` for each date in the seed window, each with a `manifest.json`. That session's date is the last seed date, and its prompt lists every seed directory. After that, episode days and checkpoints run as in Track A, with prompts that refer to `GOALS.md` and "your files". Track B is graded only through answers and has no oracle sessions.

## 9. Where outputs go

```text
runs/<name>/
  run.json                       adapter (name, version, model, path, sha256), track, oracle,
                                 worlds, timestamps, status, command line, options,
                                 resumed_at and resumed_with (see §6)
  <world>/r<k>/
    state.json                   workspace path and progress, used by --resume
    workspace/                   final store (without .git)
    snapshots/<date>/            store after the seed and after each ingestion day
    sessions/seed.ingest/        Track B seed session
    sessions/<date>.ingest/      prompt.md, stdout.log, stderr.log, session.json, usage.json
    sessions/<cp>.query/         also questions.json and answers.json (answers.raw.json if invalid)
    sessions/<cp>.query-oracle/  the same, against the oracle store
    answers/<cp>.json            answers from your agent's store
    answers/<cp>.oracle.json     answers from the oracle store
  scores/                        written by `wcb score`
```

`run.json` has `status: running` during a run, then `completed`, `interrupted` or `error`.

Workspaces are created **outside** the run directory and the repository, in the system temp directory by default (`/tmp/wcb-ws-*`). Query copies are `/tmp/wcb-q-*`. Both are deleted when they are no longer needed. After an interruption the episode's workspace is kept for `--resume`, and the runner prints its path.

## 10. Reading session logs

Every session directory holds the exact prompt (`prompt.md`), your agent's output (`stdout.log`, `stderr.log`) and `session.json`:

```json
{"phase": "ingest", "date": "2027-03-02", "checkpoint": null, "store": "agent",
 "cmd": ["my-agent", "run", "--cwd", "/tmp/wcb-ws-k2v9x1", "--prompt-file", "..."],
 "exit_code": 0, "timed_out": false, "wall_s": 412.7, "timeout_s": 1800.0,
 "started_at": "2027-...", "finished_at": "2027-...",
 "usage": {"input_tokens": 182344, "output_tokens": 9120, "cost_usd": 0.71, "tool_calls": 57, "model": "..."},
 "status": "ok", "world": "pilot", "repeat": 1, "track": "A", "notes": []}
```

- `status` is `ok`, `failed` (non-zero exit, or the runner could not read or copy the store the session left; see §5), `timeout`, or `error` (the command could not start; `stderr.log` says why).
- `notes` explains anything the runner did on your agent's behalf, such as restoring the store, recording empty answers, or ignoring an invalid `usage.json`.
- Query sessions add `answers: {status, answered, questions}`. `status` is `ok`, `missing`, `invalid_json`, `not_object`, `invalid` (a symbolic link), `too_large` or `unreadable`.

Useful commands:

```bash
jq -r '[.date, .status, .wall_s] | @tsv' runs/x/pilot/r1/sessions/*/session.json
diff -ru runs/x/pilot/r1/snapshots/2027-03-01 runs/x/pilot/r1/snapshots/2027-03-02   # one day's changes
wcb validate store runs/x/pilot/r1/snapshots/2027-03-02                                 # contract check
wcb validate answers runs/x/pilot/r1/answers/cp1.json \
  --questions runs/x/pilot/r1/sessions/cp1.query/questions.json
```

## 11. Honest-run rules

A run is only meaningful if the agent works the way it would for a real person, from the inputs it is given.

1. **The agent sees only its workspace.** It must not read the world directory (`world.jsonl`, `questions.yaml`, `gold/`), other worlds, the run directory, or any earlier run. The runner keeps workspaces away from these, but a local agent with shell access can still reach them. Sandbox it so that only `{workspace}` is visible, plus `{session_dir}` if your harness writes logs there. For example, run it in a container that mounts only those directories.
2. **No memory outside the workspace.** Each session is a fresh process. Disable any harness feature that carries memory, caches, conversation history or vector indexes between sessions outside the workspace. Anything the agent wants to remember goes into the workspace.
3. **No world-specific knowledge.** Adapters and system prompts must be generic. Do not tune prompts, tools or heuristics to particular worlds, questions or answers. Develop on `dev`; the `test` split is held out.
4. **No outside data.** Network access should be limited to your model provider's endpoints.
5. **Respect the session boundaries.** Do not edit the store between sessions, do not change the inbox, and do not retry failed sessions in a reported run. `--resume` is for infrastructure failures.
6. **Report what you ran.** Use real `version` and `model` values. `run.json` records the adapter's sha256 so a result can be traced to an exact adapter file.
7. **Answer for a person, not for the grader.** Do not shape answers around grading rules: padding status answers with lists of statuses, dates, roles or loop titles; stringing several items into one; repeating items or adding filler; hedging between values; citing records that do not support the answer; or writing instructions to the judge. The graders are built to give such answers no credit, and `tests/grade/test_gaming.py` checks that they stay that way.

### Container isolation

[`adapters/examples/docker.yaml`](../adapters/examples/docker.yaml) runs every session of any agent in a fresh container that mounts only the workspace and the prompt file. Without it, an agent with shell access could read `worlds/*/gold/` from your checkout. Verified leaderboard runs use this setup ([leaderboard](leaderboard.md)).

```bash
docker build -f docker/Dockerfile.simple -t wcb-simple .        # the wcb harness and pinned document readers, no worlds
WCB_AGENT_IMAGE=wcb-simple WCB_AGENT_CMD="python -I -m wcb.baselines.null" \
  wcb run --adapter adapters/examples/docker.yaml --world pilot --out runs/null-docker
```

Replace `WCB_AGENT_IMAGE` and `WCB_AGENT_CMD` with your own image and entry command. Inside the container the agent sees `/workspace`, `/wcb/prompt.md` and the `WCB_*` variables.

## 12. Fairness notes

- Every agent gets the same prompts and the same inputs on the same days. Time limits come from the adapter and are recorded in each `session.json` (`timeout_s`); compare agents at similar budgets.
- Query sessions run on a copy of the store, including its git history; the history is legitimate evidence. Store files are read-only and all changes are discarded.
- Oracle sessions use the same adapter and prompt on a correct store, so the gap between your end-to-end score and your oracle score isolates ingestion errors.
- Self-reported usage (`.wcb/usage.json`) is shown as reported. Verified leaderboard entries use metered mode (see [scoring](scoring.md#efficiency)).
- Agents vary from run to run. Use `--repeats 3` or more before comparing two agents.

## 13. Troubleshooting

| Symptom | Fix |
|---|---|
| `world ... is not built; missing: ...` | Run `wcb world build <world>`, or drop `--no-build`. |
| `world ... failed to build` | The world's sources have errors; run `wcb world check <world>`. For a world you edited, see [worlds](worlds.md). |
| `output directory ... is not empty` | Pass `--resume` to continue that run, or choose a new `--out`. |
| `status: error`, `command ... not found` in `stderr.log` | The command is not on the session's `PATH`, which is your `PATH` with the `wcb` interpreter's directory first. Use an absolute path or `{adapter_dir}/script`, or set `PATH` in `env`. |
| `python` not found (null baseline) | Run `wcb` from a virtual environment, or change the command to `python3`. |
| Every session times out | The agent may be waiting for input or approval: stdin is empty. Use its non-interactive mode and check `stdout.log` and `stderr.log`. Otherwise raise `timeout_s`. |
| An API key does not reach the agent | Add it to `env_passthrough`. `wcb run` warns when a listed variable is not set. |
| `answers 0/12 (missing)` | The agent did not write `.wcb/answers.json` in the workspace it was given (`{workspace}`, which is also its working directory by default). |
| `answers ... (invalid_json)` | See `answers.raw.json` in the session directory. |
| `... could not be graded (...); it scores 0` in the report's notes | The answer passed validation but the grader could not handle it, so that one question scored 0 and scoring went on. Check the answer in `answers/<cp>.json`; if it looks right, report a bug with the note. |
| `Permission denied` in a query session | Expected: query sessions are read-only. Write scratch files in `.wcb/` or `$TMPDIR`. |
| Adapter warning `... puts its working directory, the workspace, first on sys.path` | Start Python with `-I` (`python -I -m ...`), or `-P` on Python 3.11+ (§4, Environment). |
| A background process the agent started stops when the session ends | Expected: no process outlives its session (§5). Finish all work before the main process exits. |
| `the workspace changed after snapshots/... was taken` in `notes` | Something edited the store between sessions; the runner reverted it (§5). Look for a process outside the session, or edits by hand. |
| A path with spaces breaks a string command | Remove quotes around placeholders; the runner quotes substituted values. Or use a list command. |
| `git: ...` warning | Git history is optional; snapshots are unaffected. Install git or check the workspace's `.git`. |
| Leftover `/tmp/wcb-ws-*` directories | Workspaces kept after an interruption. Resume the run, or delete them. |
| The adapter changed between a run and its resume | `wcb run --resume` warns. Sessions from then on use the new adapter. Start a new `--out` for a clean result. |

## 14. Command reference

| Command | Purpose |
|---|---|
| `wcb run --adapter A --world W --out DIR` | Run an agent over worlds (`--split dev`, `--track B`, `--repeats N`, `--resume`, `--skip-ingest` for oracle-only runs) |
| `wcb doctor --adapter A [--track B]` | Smoke-test an adapter on the two-day mini world, with a checklist and hints |
| `wcb score DIR [--judge llm --judge-model M]` | Grade a run and write `report.json` and `report.md` (`--suite lite` scores only a reduced suite's worlds and days; [reduced suites](lite.md)) |
| `wcb judge sample\|label\|run\|agreement` | Sample judge decisions from scored runs, label them by hand or with a judge, and report Cohen's κ ([judges](judge.md#measuring-judge-agreement)) |
| `wcb validate store DIR` | Check a store against the Track A contract |
| `wcb validate answers FILE --questions Q` | Check an answers file |
| `wcb world list / check / build / stats / questions` | Inspect, validate and build worlds ([worlds](worlds.md)) |
| `wcb generate --seed N --out DIR` | Generate a synthetic world ([generator](generator.md)) |
| `wcb bundle DIR [--logs]` | Pack a scored run into a `.tar.gz` with a manifest, for reporting results |
| `wcb privacy scan --private-repo P PATHS` | Check content for terms from a private repository ([privacy](privacy.md)) |

Reference adapters in `adapters/examples/`:

| Adapter | What it runs |
|---|---|
| `null.yaml` | Abstains on every question: the floor |
| `store-reader.yaml` | Fixed rules over a contract store; with `--skip-ingest` it checks that oracle stores carry what the questions need |
| `raw-retrieval.yaml` | Archives inputs without curation and answers by searching them with an LLM |
| `claude-code.yaml`, `codex.yaml` | CLI coding agents |
| `simple-anthropic.yaml`, `simple-openai.yaml` | A raw model in a minimal tool loop (OpenAI-compatible covers OpenRouter, vLLM, Ollama and others) |
| `docker.yaml` | Any agent in a container that sees only its workspace, as leaderboard runs do |
| `custom-script.yaml` | Template for your own script ([adapters](adapters.md)) |
