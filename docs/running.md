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
wcb world list                   # every world under worlds/, with days and checkpoints
wcb world build pilot            # derive manifests, gold state, oracle stores and questions
wcb world questions pilot        # the questions, with unanswerable ones marked (dev worlds only)
```

A world must be **built** before it can be run: the runner needs `inbox/<date>/manifest.json`, `gold/oracle-store/<date>/` and `gold/questions/<checkpoint>.json`. If something is missing, `wcb run` stops before any session starts and tells you which command to run.

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

The directory of the Python interpreter running `wcb` is put first on `PATH`. When you run `wcb` from a virtual environment (`.venv/bin/wcb`), `python` in a command therefore resolves to that environment's interpreter, which has `wcb` installed. `adapters/examples/null.yaml` relies on this with `cmd: ["python", "-m", "wcb.baselines.null"]`. If your Python installation provides only `python3`, use that name instead. Setting `PATH` in `env` replaces the whole value.

stdin is empty (`/dev/null`). An agent that waits for interactive input or approval will time out, so run your agent in its non-interactive mode with the permissions it needs to read and write files in the workspace.

### What the agent sees

**Ingestion session, Track A.** The workspace holds the store (`CONTRACT.md`, `people/`, `projects/`, `loops/`, `logs/` and so on) and the day's inputs in `inbox/<date>/` with a `manifest.json`. The prompt is:

> Today is 2027-03-01. New inputs are in `inbox/2027-03-01/` (see `manifest.json`). Incorporate them into the store following `CONTRACT.md`. Inputs will not be available after this session.

**Query session.** The workspace is a throwaway copy of the store, with its git history, plus `.wcb/questions.json` and `.wcb/answer-schema.json`. Store files are read-only. The agent writes `.wcb/answers.json`. Check the format with `wcb validate answers answers.json --questions questions.json`.

**Usage.** In any session the agent may write `.wcb/usage.json` with `input_tokens`, `output_tokens`, `cost_usd`, `tool_calls` and `model`. The runner copies it into the session's log directory and `session.json`. The runner removes `.wcb/` and `inbox/` after every session.

Prompts are fixed benchmark text, listed in [scoring](scoring.md#standard-prompts) and `wcb/runner/prompts.py`. Your adapter may wrap them in its own system prompt, but must not add knowledge about any world.

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
| `--workspace-root DIR` | Where temporary workspaces are created (default: the system temp directory). |
| `--resume` | Continue an interrupted run (see §6). |
| `--skip-ingest` | Run only oracle query sessions (see §7). |

An episode runs like this:

1. **Start.** Track A: the workspace becomes a copy of the world's seed store (`gold/oracle-store/<seed end>/`) plus `CONTRACT.md`, and is committed to git.
2. **Each day.** The runner copies `inbox/<date>/` into the workspace, writes the prompt and runs the ingest command in a fresh process. Afterwards it removes `inbox/` and `.wcb/`, snapshots the store to `snapshots/<date>/` and commits (`wcb: after <date> ingest`).
3. **Checkpoint days.** After that day's ingestion, the runner runs a query session on a read-only copy of the store, saves the answers and discards the copy.
4. **Oracle sessions.** Track A only: after the episode, each checkpoint's questions are asked again against `gold/oracle-store/<checkpoint date>/` plus `CONTRACT.md`, in a separate session with the same adapter. The scores measure synthesis alone.

**Failed sessions.** A non-zero exit or a timeout fails the session. A failed ingest session leaves the store as it was before the session: the runner restores it from the previous snapshot, and the day's snapshot equals the previous day's. A failed query session counts as empty answers. On timeout the runner sends SIGTERM to the session's whole process group, then SIGKILL after 10 seconds. Any process the agent leaves running after it exits is killed too. The run carries on either way, and `wcb run` exits 0 when the run completes, whatever the sessions' outcomes.

## 6. Resume

If a run stops (Ctrl-C, SIGTERM, a crash or a machine restart), run the same command again with `--resume`:

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-pilot --resume
```

- Ingest sessions that exited 0 within their timeout are skipped, and query sessions that finished are skipped.
- From the first session that has to run, every later session of that episode runs again, because it depends on the store.
- The workspace is found through `<run>/<world>/r<k>/state.json`. If the temporary directory is gone, the runner rebuilds it from the latest snapshot. Snapshots are the source of truth, and git history from before the rebuild is lost.
- Ingest sessions that failed or timed out are run again. `--resume` is for recovering from infrastructure problems. Do not use it to retry an agent's own failures in a reported run.
- `--resume` with a larger `--max-days`, more `--repeats` or extra `--world`s extends an existing run. `run.json` records each resume in `resumed_at`.

## 7. Oracle-only runs

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --out runs/my-agent-synthesis --skip-ingest
```

`--skip-ingest` runs no ingestion. For every checkpoint it runs only the query session against the oracle store. This measures synthesis alone, at a fraction of the cost of a full run, and is useful while working on the query side of an agent. It is Track A only.

## 8. Track B

```bash
wcb run --adapter adapters/my-agent.yaml --world pilot --track B --out runs/my-agent-b
```

In Track B there is no contract and no seed store. The workspace starts empty except for `GOALS.md`, a one-paragraph goal statement. Then one **seed session** delivers every seed date's inbox at once: `inbox/<date>/` for each date in the seed window, each with a `manifest.json`. That session's date is the last seed date, and its prompt lists every seed directory. After that, episode days and checkpoints run as in Track A, with prompts that refer to `GOALS.md` and "your files". Track B is graded only through answers and has no oracle sessions.

## 9. Where outputs go

```text
runs/<name>/
  run.json                       adapter (name, version, model, path, sha256), track, oracle,
                                 worlds, timestamps, status, command line
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

- `status` is `ok`, `failed` (non-zero exit), `timeout`, or `error` (the command could not start; `stderr.log` says why).
- `notes` explains anything the runner did on your agent's behalf, such as restoring the store, recording empty answers, or ignoring an invalid `usage.json`.
- Query sessions add `answers: {status, answered, questions}`. `status` is `ok`, `missing`, `invalid_json` or `not_object`.

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

### Container isolation

[`adapters/examples/docker.yaml`](../adapters/examples/docker.yaml) runs every session of any agent in a fresh container that mounts only the workspace and the prompt file. Without it, an agent with shell access could read `worlds/*/gold/` from your checkout. Verified leaderboard runs use this setup ([leaderboard](leaderboard.md)).

```bash
docker build -f docker/Dockerfile.simple -t wcb-simple .        # an image with the wcb harness, no worlds
WCB_AGENT_IMAGE=wcb-simple WCB_AGENT_CMD="python -m wcb.baselines.null" \
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
| `world ... is not built; missing: ...` | Run `wcb world build <world>`. |
| `output directory ... is not empty` | Pass `--resume` to continue that run, or choose a new `--out`. |
| `status: error`, `command ... not found` in `stderr.log` | The command is not on the session's `PATH`, which is your `PATH` with the `wcb` interpreter's directory first. Use an absolute path or `{adapter_dir}/script`, or set `PATH` in `env`. |
| `python` not found (null baseline) | Run `wcb` from a virtual environment, or change the command to `python3`. |
| Every session times out | The agent may be waiting for input or approval: stdin is empty. Use its non-interactive mode and check `stdout.log` and `stderr.log`. Otherwise raise `timeout_s`. |
| An API key does not reach the agent | Add it to `env_passthrough`. `wcb run` warns when a listed variable is not set. |
| `answers 0/12 (missing)` | The agent did not write `.wcb/answers.json` in the workspace it was given (`{workspace}`, which is also its working directory by default). |
| `answers ... (invalid_json)` | See `answers.raw.json` in the session directory. |
| `Permission denied` in a query session | Expected: query sessions are read-only. Write scratch files in `.wcb/` or `$TMPDIR`. |
| A path with spaces breaks a string command | Remove quotes around placeholders; the runner quotes substituted values. Or use a list command. |
| `git: ...` warning | Git history is optional; snapshots are unaffected. Install git or check the workspace's `.git`. |
| Leftover `/tmp/wcb-ws-*` directories | Workspaces kept after an interruption. Resume the run, or delete them. |
| The adapter changed between a run and its resume | `wcb run --resume` warns. Sessions from then on use the new adapter. Start a new `--out` for a clean result. |
