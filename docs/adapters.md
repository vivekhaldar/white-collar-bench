# Adapters

Status: v0.1. How to connect an agent or a model to white-collar-bench. [Running](running.md) is the step-by-step guide to `wcb run`; [formats](formats.md#5-adapter-adapteryaml) specifies the adapter file; [scoring](scoring.md) explains the run protocol and grading. This page is the reference for writing adapters, with worked examples for CLI agents, API-based agents and raw models.

An **adapter** is a small YAML file that tells the runner how to start your agent for one session. The runner owns everything else: the workspace, the simulated clock, the inbox, snapshots, timeouts and grading. Your agent only sees its workspace, a fixed prompt and a few environment variables.

There are three ways to plug in:

| You have | Use | Example |
|---|---|---|
| A CLI coding agent (Claude Code, Codex, ...) | Run it non-interactively in the workspace. | [`claude-code.yaml`](../adapters/examples/claude-code.yaml), [`codex.yaml`](../adapters/examples/codex.yaml) |
| A model behind an API, and no agent | The simple harness: a fixed, minimal tool loop around the model. | [`simple-anthropic.yaml`](../adapters/examples/simple-anthropic.yaml), [`simple-openai.yaml`](../adapters/examples/simple-openai.yaml) |
| Your own agent code | A script that reads the session from the environment. | [`custom-script.yaml`](../adapters/examples/custom-script.yaml) + [`custom_agent_template.py`](../adapters/examples/custom_agent_template.py) |

The smallest working adapter is the null baseline, [`null.yaml`](../adapters/examples/null.yaml), which abstains on every question.

## 1. Quick start

```bash
# A raw model in the simple harness (edit <model-id> in the file first)
export ANTHROPIC_API_KEY=...
wcb run --adapter adapters/examples/simple-anthropic.yaml --world pilot --out runs/simple-claude

# Any OpenAI-compatible endpoint (edit <model-id> first)
export OPENAI_API_KEY=...                       # not needed for local servers
export OPENAI_BASE_URL=https://openrouter.ai/api/v1   # omit for api.openai.com
wcb run --adapter adapters/examples/simple-openai.yaml --world pilot --out runs/simple-openai

# CLI agents (installed and authenticated; see section 7)
wcb run --adapter adapters/examples/claude-code.yaml --world pilot --out runs/claude-code
wcb run --adapter adapters/examples/codex.yaml --world pilot --out runs/codex

# Your own script, starting from the template
wcb run --adapter adapters/examples/custom-script.yaml --world pilot --out runs/custom

wcb score runs/simple-claude
```

Add `--max-days 1` for a quick check that sessions start and finish. `wcb run` builds the world's gold first if needed; see [running](running.md#2-find-and-build-worlds).

## 2. Adapter file reference

```yaml
name: my-agent                      # required
version: 0.3.1
model: provider/model-name
description: One line about the agent
cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}"]   # both phases
cwd: "{workspace}"
timeout_s: 1800
env: {MY_AGENT_MODE: benchmark}
env_passthrough: [MY_PROVIDER_API_KEY]
ingest:
  timeout_s: 1800
query:
  cmd: ["my-agent", "--cwd", "{workspace}", "--prompt-file", "{prompt}", "--read-only"]
  timeout_s: 900
```

### Keys

| Key | Default | Meaning |
|---|---|---|
| `name` | required | Short identifier for your agent. |
| `version` | `unspecified` (warning) | Your agent's version. Recorded in `run.json` and reports. |
| `model` | `unspecified` (warning) | The model you ran, as `provider/model-name`. Shown on the leaderboard. Keep it in sync with the model your command actually uses. |
| `description` | none | Free text. |
| `cmd` | required here or in both phases | The command. A **list** runs the program directly (no shell); each element is one argument. A **string** runs with `/bin/sh -c`. |
| `cwd` | `{workspace}` | Working directory. A relative path is resolved against the adapter file's directory; `null` means the directory you ran `wcb` from. |
| `timeout_s` | 1800 (ingest), 900 (query) | Wall-clock limit per session, in seconds. |
| `env` | none | Literal environment variables for the session. Values may use placeholders. |
| `env_passthrough` | none | Names of variables copied from your environment, typically API keys. `wcb run` warns when one is not set. |
| `ingest`, `query` | | Per-phase `cmd`, `cwd` and `timeout_s`, overriding the top-level values. No other keys are allowed here. |

Unknown keys are reported as warnings because they are usually typos. Invalid values are errors, all listed at once.

### Placeholders

Written `{name}` in `cmd`, `cwd` and `env` values:

| Placeholder | Value |
|---|---|
| `{workspace}` | Absolute path of the workspace: the directory the agent works in. |
| `{prompt}` | Absolute path of the prompt file (`<session_dir>/prompt.md`). |
| `{prompt_text}` | The prompt itself. |
| `{date}` | The simulated date, `YYYY-MM-DD`. Treat it as today. |
| `{phase}` | `ingest` or `query`. |
| `{track}` | `A` or `B`. |
| `{session_dir}` | Absolute path of this session's log directory, outside the workspace. Your harness may write transcripts here. |
| `{adapter_dir}` | Absolute path of the directory holding the adapter file, for scripts kept next to it. |

In a list command, substituted values stay one argument even with spaces. In a string command, every substituted value is shell-quoted for you, so write `--cwd {workspace}`, never `--cwd "{workspace}"`. Shell syntax such as `${HOME}` or `${MODEL:+--model "$MODEL"}` is left alone (`codex.yaml` uses this to add a flag only when a variable is set). Any other `{word}` is passed through literally, with a warning.

### Environment

A session does not inherit your whole environment. It gets:

1. `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `TERM`, `TMPDIR` and `SHELL` from your environment, when set. The directory of the Python interpreter running `wcb` is put first on `PATH`, so `python` in a command is the interpreter that has `wcb` installed.
2. The variables named in `env_passthrough`, then `env`.
3. These, which cannot be overridden:

| Variable | Value |
|---|---|
| `WCB_DATE` | The simulated date. |
| `WCB_PHASE` | `ingest` or `query`. |
| `WCB_TRACK` | `A` or `B`. |
| `WCB_WORKSPACE` | The workspace path (`{workspace}`). |
| `WCB_PROMPT_FILE` | The prompt file path (`{prompt}`). |
| `WCB_SESSION_DIR` | The session log directory (`{session_dir}`). |

stdin is empty (`/dev/null`). stdout and stderr are saved to `stdout.log` and `stderr.log` in the session directory.

**Python entry points.** The default working directory is the workspace, which the agent controls. `python -m module` and `python -c` put the working directory first on `sys.path`, so a `json.py`, `typing.py` or `wcb/` the agent leaves at the store root would be imported instead of the real module, in that session and every later one. Start Python with `-I` (`python -I -m wcb.agents.wrap ...`), as the examples do, or with `-P` on Python 3.11+. `-I` also ignores `PYTHON*` variables and user site-packages, which does not matter when `wcb` is installed in a virtual environment. `wcb run` warns about an adapter that runs `python -m` or `-c` in the workspace without either flag. A script path (`python {adapter_dir}/agent.py`) is safe: Python puts the script's own directory on `sys.path`.

### Exit status and timeouts

- Exit 0 when the session's work is done. Any other status fails the session.
- A failed or timed-out **ingest** session leaves the store as it was before the session: all its changes are discarded.
- A failed or timed-out **query** session counts as empty answers if `.wcb/answers.json` is missing or invalid. Write it early and keep it valid.
- On timeout the runner sends SIGTERM to every process of the session, then SIGKILL 10 seconds later. Write usage on SIGTERM if you can (the simple harness and `wcb.agents.wrap` do).
- The runner sets no time limit on individual tool calls: a command or model-written script that hangs is the agent's own failure, bounded by the session timeout, after which a failed ingest session's store is restored from the previous snapshot; bound tool calls in your agent if you want it to recover.
- When the session's main process exits, every process it started is killed, including daemons and processes started with `setsid` or Node's `detached: true`. Nothing may keep running, or keep writing to the workspace, after a session ([running §5](running.md#5-run)).

## 3. What the agent sees

### Ingestion sessions

The workspace holds the store and the day's inputs in `inbox/<date>/`:

```text
<workspace>/
  CONTRACT.md            Track A: the store contract (Track B: GOALS.md, one paragraph)
  people/ orgs/ projects/ loops/ logs/ ...   Track A: the store so far
  inbox/2027-03-01/
    manifest.json        {"date": ..., "artifacts": [{"id", "channel", "received_at", "path", "title", "parent"?}]}
    em-0031.eml  ch-0012.json  mt-0004.vtt  mn-0002.md  nt-0009.md  ca-0005.ics  dc-0007.docx ...
```

Input formats are specified in [formats §1.5-1.6](formats.md#15-inboxdatemanifestjson): `.eml` email, `.json` chat export, `.vtt` transcript, `.md` notes and meeting notes, `.ics` calendar, and `.md`/`.docx`/`.xlsx`/`.pdf` documents. The inbox is removed after the session: anything needed later must be copied into the store. In Track B the first session is a **seed session** that receives every seed date's inbox at once (`inbox/<d1>/`, `inbox/<d2>/`, ...).

A git history of the store is kept in `.git/`. It is legitimate evidence for the agent; do not modify it.

### Query sessions

The workspace is a throwaway copy of the store (with its git history) plus:

```text
.wcb/questions.json      {"date": ..., "questions": [{"id": "q-001", "type": "list", "text": "..."}]}
.wcb/answer-schema.json  the JSON Schema for answers
```

Store files are read-only. The agent writes `.wcb/answers.json`, a JSON object mapping each question ID to an answer whose `type` equals the question's type ([formats §4](formats.md#4-answers-wcbanswersjson), [example](../contract/answers/example.answers.json)). Answers that fail the schema score 0. A point answer's `value` is the bare answer only (`"Privacy Officer"`, `"2027-11-18"`); put any context in its optional `note`, which is not graded. Abstain (`{"type": ..., "abstain": true}`) when the store does not support an answer. Check an answers file with:

```bash
wcb validate answers answers.json --questions questions.json
```

### Standard prompts

The prompt is fixed benchmark text, defined in [`wcb/runner/prompts.py`](../wcb/runner/prompts.py) and [scoring](scoring.md#standard-prompts). With the date filled in:

| Session | Prompt |
|---|---|
| Track A ingestion | Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). Incorporate them into the store following `CONTRACT.md`. Inputs will not be available after this session. |
| Track A query (also oracle-store queries) | Today is {date}. Answer every question in `.wcb/questions.json` using the store. Write `.wcb/answers.json` following `.wcb/answer-schema.json`. For point answers, put only the answer in `value` and any context in `note`. Cite sources. Abstain when the store does not support an answer. Do not modify the store. |
| Track B ingestion | Today is {date}. New inputs are in `inbox/{date}/` (see `manifest.json`). Incorporate them into your files following `GOALS.md`. Inputs will not be available after this session. |
| Track B seed ingestion | Today is {date}. Your inputs so far, up to and including today, are in `inbox/<d1>/`, ... and `inbox/<dn>/`, one directory per date (each has a `manifest.json`). Incorporate them into your files following `GOALS.md`. Inputs will not be available after this session. |
| Track B query | Today is {date}. Answer every question in `.wcb/questions.json` using your files. Write `.wcb/answers.json` following `.wcb/answer-schema.json`. For point answers, put only the answer in `value` and any context in `note`. Cite sources. Abstain when your files do not support an answer. Do not modify your files. |

Pass the prompt to your agent unchanged, via `{prompt_text}`, `{prompt}` or `$WCB_PROMPT_FILE`. You may wrap it in your own **generic** system prompt.

## 4. Rules

These keep results comparable. Verified leaderboard runs enforce them; local runs rely on you. See also [running §11](running.md#11-honest-run-rules).

1. **No world-specific knowledge.** Adapters, system prompts, tools and heuristics must be generic. Do not mention people, projects, organizations, questions or answers from any world, and do not tune on the `test` split. "You maintain a knowledge store; cite artifact IDs" is fine; "Marisol Teague is the PM for Thistledown" is not.
2. **Fresh process per session, no memory outside the workspace.** Each session starts a new process. Disable anything that carries state between sessions outside the workspace: conversation history, session resume, auto-memory, user-level instruction files, caches, vector indexes in your home directory. Anything the agent wants to remember goes into the workspace.
3. **Workspace only.** The agent reads and writes only `{workspace}` (and may write logs to `{session_dir}`). It must not read world files, gold, other runs or other workspaces. Agents with shell access can reach them, so isolate them (section 8).
4. **Query sessions are read-only.** Do not modify the store while answering; write only under `.wcb/`. The runner discards every change anyway.
5. **No outside data.** Network access is for model endpoints only: no web search, no fetching.
6. **Report usage.** Write `.wcb/usage.json` (section 5) so cost can be weighed against quality. Verified runs meter model calls instead.
7. **Report what you ran.** Real `version` and `model` values; the adapter's sha256 is recorded in `run.json`.

## 5. Usage reporting: `.wcb/usage.json`

At the end of any session the agent may write `.wcb/usage.json` in the workspace. The runner copies it into the session directory and `session.json`, then removes `.wcb/`.

```json
{"input_tokens": 182344, "output_tokens": 9120, "cost_usd": 0.71, "tool_calls": 57, "model": "provider/model-name"}
```

| Field | Meaning |
|---|---|
| `input_tokens` | All input tokens of all model calls in the session, including cached tokens. |
| `output_tokens` | All output tokens, including reasoning tokens. |
| `cost_usd` | Total cost, or `null` if unknown. |
| `tool_calls` | Number of tool calls or commands the agent ran. |
| `model` | The model used. |

Extra fields are kept as-is. The examples add `cache_read_input_tokens`, `cache_creation_input_tokens`, `turns`, `provider`, `harness` and, for the simple harness, `stop` and `tool_counts`. Write the file even when the session fails, so failed sessions are costed too.

**Why the agent stopped.** Add `"termination": {"reason": "...", "incomplete": true|false}` when your agent knows. `reason` is the agent's or provider's own stop reason (for example `success`, `max_tokens`, `error_max_turns`); `incomplete` is true when the agent did not finish normally, in particular when its final response was cut off by an output-token limit, even if it exited 0. The runner copies it into `session.json` and flags incomplete sessions there ([formats §6](formats.md#6-run-directory)); it does not change the session's status or restore the store, so truncation stays the agent's outcome, but it is visible. `wcb.agents.wrap` fills it in for Claude Code and Codex.

## 6. Wrapping an API-based agent (your own code)

If your agent is a program that calls a model API, run it as a script. Start from the template:

```bash
cp adapters/examples/custom_agent_template.py my_agent.py
cp adapters/examples/custom-script.yaml my-agent.yaml   # set cmd to {adapter_dir}/my_agent.py
```

The template ([`custom_agent_template.py`](../adapters/examples/custom_agent_template.py)) is a complete, standard-library-only agent that you extend. It shows how to:

1. **Read the session** from `WCB_PHASE`, `WCB_DATE`, `WCB_TRACK`, `WCB_WORKSPACE`, `WCB_PROMPT_FILE` and `WCB_SESSION_DIR`.
2. **List the inbox**: every `inbox/<date>/manifest.json` (several in a Track B seed session), and read each artifact. Office documents and PDFs can be converted with `wcb.agents.docs_text.extract_text` when `wcb` is installed in the agent's environment.
3. **Write records**: Markdown with YAML front matter (`write_record`), and the daily log Track A requires (`logs/<date>.md`, one bullet per input).
4. **Answer questions**: read `.wcb/questions.json`, write `.wcb/answers.json` with one answer per question. The docstring of `answer_question` shows every answer shape.
5. **Report usage** in `.wcb/usage.json`, even on failure.

Points to get right:

- **Dependencies.** `python` in a command is the interpreter running `wcb`. If your agent needs other packages, install them in the same environment, or run your own interpreter by absolute path, e.g. `cmd: ["/opt/my-agent/.venv/bin/python", "{adapter_dir}/my_agent.py"]`.
- **API keys.** List them in `env_passthrough`; nothing else from your environment reaches the session.
- **Prompt.** Use the fixed prompt from `WCB_PROMPT_FILE` as the task. Your system prompt must be generic.
- **Same command for both phases** is simplest: branch on `WCB_PHASE` inside the script. Per-phase `cmd` is available when your agent has separate entry points.
- **Logs.** Print progress to stdout and errors to stderr; both are saved. Detailed traces can go to `$WCB_SESSION_DIR`, which is outside the workspace and never graded.
- **Time.** Stay well inside `timeout_s`; a timed-out ingest session loses all its changes.

If your agent is a service rather than a script (an HTTP API, a hosted agent), write a thin client script that sends the prompt and workspace to it and waits for it to finish. The service must work only on that session's workspace and keep no state between sessions.

## 7. Wrapping a CLI agent

Any agent with a non-interactive mode can be run directly. The recipe:

1. **Run non-interactively**, with the prompt as an argument (`{prompt_text}`) or on stdin (string command `... < {prompt}`).
2. **Work in the workspace**: the default `cwd` is `{workspace}`; pass it explicitly too if the agent has a flag for its root directory.
3. **No approvals**: stdin is empty, so a permission prompt hangs until the timeout. Grant file and command permissions up front, and confine the agent with its own sandbox or a container.
4. **Fresh state**: turn off session persistence, resume, auto-memory and user-level config or instruction files.
5. **Usage**: if the agent prints machine-readable usage, run it under `python -I -m wcb.agents.wrap --format <fmt> -- <command...>`, which copies the output to `stdout.log` and writes `.wcb/usage.json`. Formats: `claude` (Claude Code `--output-format stream-json` or `json`) and `codex` (Codex `exec --json`). It exits with the agent's status, and records why the agent stopped in `termination`: for Claude Code the `result` event's `subtype` and `is_error` and the last assistant message's `stop_reason` (`max_tokens` means the final response was truncated); for Codex any `turn.failed` or `error` events.

### Claude Code: [`claude-code.yaml`](../adapters/examples/claude-code.yaml)

```yaml
cmd: [python, -I, -m, wcb.agents.wrap, --format, claude, --,
      claude, --print, "{prompt_text}", --bare, --dangerously-skip-permissions,
      --no-session-persistence, --output-format, stream-json, --verbose,
      --append-system-prompt, "You are running unattended ..."]
env_passthrough: [ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_BASE_URL]
```

- `--print` runs one non-interactive session. `--dangerously-skip-permissions` removes permission prompts; its tools (including Bash) are then **not** confined to the workspace, so verified or shared-machine runs must use a container (section 8).
- `--bare` skips CLAUDE.md discovery, auto-memory, hooks and plugins, so nothing from your own setup or earlier sessions leaks in. It authenticates **only** with `ANTHROPIC_API_KEY`. To use a subscription login, drop `--bare`, pass `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) and run in a container with a clean `HOME`.
- `--no-session-persistence` stores no conversation history.
- Model: set `ANTHROPIC_MODEL`, or add `--model <model-id>`. Update `model:` to match.
- Optional: `--max-budget-usd <amount>` caps spend per session; `--effort <level>` sets reasoning effort.
- Flags were checked against `claude --help` for Claude Code 2.1. Run `claude --help` if your version differs.

### Codex: [`codex.yaml`](../adapters/examples/codex.yaml)

```yaml
cmd: >-
  python -I -m wcb.agents.wrap --format codex ${CODEX_MODEL:+--model "$CODEX_MODEL"} --
  codex exec --cd {workspace} --sandbox workspace-write --skip-git-repo-check
  --ephemeral --ignore-user-config --json --color never
  ${CODEX_MODEL:+--model "$CODEX_MODEL"}
  {prompt_text}
env_passthrough: [OPENAI_API_KEY, CODEX_API_KEY, CODEX_HOME, CODEX_MODEL]
```

- `codex exec` runs non-interactively; `--cd {workspace}` makes the workspace its root; `--sandbox workspace-write` confines the commands it runs to writing inside it.
- `--skip-git-repo-check` is required: Codex otherwise refuses to run outside a trusted git repository.
- `--ephemeral` stores no session files; `--ignore-user-config` ignores `~/.codex/config.toml` (MCP servers, profiles, instructions). Authentication still comes from `CODEX_HOME` (`codex login`) or `OPENAI_API_KEY`/`CODEX_API_KEY`.
- To pass the prompt on stdin instead, replace `{prompt_text}` with `- < {prompt}`.
- Model: set `CODEX_MODEL` (the shell expansion adds `--model` only when it is set). Update `model:` to match.
- Flags were checked against `codex exec --help` for codex-cli 0.163.

### Other CLI agents

Follow the recipe above with your agent's own flags. If it prints usage in a format `wcb.agents.wrap` does not know, write `.wcb/usage.json` yourself from a small wrapper script kept next to the adapter (`cmd: "{adapter_dir}/run.sh"`).

## 8. Isolation

The runner keeps workspaces in the system temp directory, away from worlds, gold and run directories, but an agent with shell access can still read anything your user can. For trustworthy results, and always for leaderboard submissions, run each session in a container that mounts only the workspace and the session directory, with network access limited to your model endpoint:

```yaml
cmd: >-
  docker run --rm --init --user "$(id -u):$(id -g)"
  -v {workspace}:/work -w /work -v {session_dir}:/session
  -e WCB_DATE -e WCB_PHASE -e WCB_TRACK -e WCB_WORKSPACE=/work
  -e WCB_PROMPT_FILE=/session/prompt.md -e WCB_SESSION_DIR=/session
  -e ANTHROPIC_API_KEY
  my-agent-image:latest
  python -I -m wcb.agents.wrap --format claude -- claude --print {prompt_text} --bare
  --dangerously-skip-permissions --no-session-persistence --output-format stream-json --verbose
env_passthrough: [ANTHROPIC_API_KEY]
```

- `-e NAME` without a value forwards the session's variable into the container. Paths inside the container differ, so the `WCB_*` path variables are set explicitly.
- `--init` makes the agent receive the runner's SIGTERM on timeout. If the runner has to SIGKILL the `docker` client, the container can outlive it: give containers a name (e.g. `--name wcb-{phase}-{date}`) and clean up leftovers.
- `--user` keeps files written in the workspace owned by you, so the runner can snapshot and delete them. Claude Code also refuses `--dangerously-skip-permissions` as root.
- Build the image with your agent (and `pip install white-collar-bench` if you use `wcb.agents.*` inside it).

## 8a. Tools your agent's runtime needs

Agents read every input format: `.eml` email, `.ics` calendar, `.vtt` transcript, `.json` chat export, `.md` notes and records with YAML front matter, and `.pdf`, `.docx`, `.xlsx` and `.pptx` documents ([formats §1.6](formats.md#16-artifact-file-formats)). The Python standard library covers the first five apart from YAML. For the rest, install readers in the environment where the agent's own commands run, which is often not the host virtualenv (a container, or a sandbox with its own system Python):

| Need | Tool | Version in the reference image |
|---|---|---|
| YAML front matter | PyYAML | 6.0.3 |
| PDF text | pypdf; optionally poppler-utils' `pdftotext` | 7.0.1; Debian bookworm's poppler |
| Word documents | python-docx | 1.2.0 |
| Spreadsheets | openpyxl | 3.1.5 |
| Slide decks | python-pptx | 1.0.2 |

The reference image, [`docker/Dockerfile.simple`](../docker/Dockerfile.simple), installs these at build time from [`docker/requirements-tools.txt`](../docker/requirements-tools.txt) (exact pins, which also pin `wcb`'s own PyYAML) and adds `pdftotext`. `wcb.agents.docs_text.extract_text` is a standard-library alternative for office documents and PDFs where `wcb` is installed.

- **Pin them.** Every session of every run should see the same tools; record the versions with your results, and treat a change as a new adapter variant.
- **Install before the run, never during it.** Sessions must not `pip install` or `apt-get` anything: it costs time against `timeout_s`, needs network access beyond the model endpoint, and makes runs differ.
- **Smoke-test inside the agent's actual sandbox**, not on the host, before any paid run. [`docker/smoke_tools.py`](../docker/smoke_tools.py) checks each reader and, given directories, extracts text from every document in them; run it with the interpreter the agent's tools use, on public synthetic inputs:

  ```bash
  docker run --rm -v "$PWD/docker:/check:ro" -v "$PWD/worlds/dev/gen-s2-w1/inbox:/in:ro" \
    wcb-simple python -I /check/smoke_tools.py /in
  ```

## 9. The simple harness

`wcb.agents.simple` benchmarks a raw model with no agent of its own. It is deliberately minimal and identical for every model, so scores compare models rather than harnesses.

```bash
python -m wcb.agents.simple --provider anthropic --model <model-id>
python -m wcb.agents.simple --provider openai --model <model-id> [--max-turns 80] [--max-tokens 8000]
```

Inside `wcb run` it reads the workspace, prompt, phase and session directory from the `WCB_*` variables.

### What it does

- **System prompt** (generic, no world knowledge): "You are an assistant maintaining a knowledge store in your working directory. Follow the task. Use tools. Be precise and cite artifact IDs." plus two sentences saying that paths are relative and nobody will answer questions. Replace it with `--system-prompt-file` (still generic).
- **User message**: the session prompt, unchanged.
- **Tools**, all confined to the workspace (absolute paths, `..`, and symbolic links pointing outside are rejected; `.git/` is hidden and read-only):

| Tool | Behaviour |
|---|---|
| `list_files(path=".", recursive=false)` | Entries under a directory; directories end with `/`. |
| `read_file(path, offset=0, limit=400)` | A window of lines of a text file, with a header and a hint for the next page. |
| `read_document(path, offset=0, limit=400)` | Extracted text of `.docx`, `.xlsx`, `.pptx`, `.pdf`, `.eml`, `.ics` (other files as text). |
| `write_file(path, content)` | Create or overwrite a file; parent directories are created. |
| `edit_file(path, old, new)` | Replace one exact, unique occurrence of `old`. |
| `delete_file(path)` | Delete a file or an empty directory. |
| `move_file(src, dst)` | Move or rename; `dst` must not exist. |
| `search(pattern, path=".", regex=true, ignore_case=true)` | grep-like `path:line: text` matches over text files and extracted document text, capped at 200. |
| `finish(summary)` | End the session. |

- **Query sessions** are read-only except `.wcb/`. When the model calls `finish`, the harness checks `.wcb/answers.json`: it must exist, be a JSON object, answer every question with the right `type`, and validate against `.wcb/answer-schema.json`. If not, `finish` is rejected with the problems listed (twice at most).
- **Stopping**: the loop ends when the model calls `finish`; when it replies without tool calls (after one reminder in ingest sessions; in query sessions only once the answers are valid); after 4 replies in a row without tool calls that were cut off at `--max-tokens` or left invalid answers; or at `--max-turns`. Reaching `--max-turns` exits 0, so the work done so far is kept.
- **Context management**: each tool result is capped at `--max-tool-output` characters. When the conversation's estimated size (characters / 4) exceeds `--context-budget` tokens, the oldest tool results and long arguments of old `write_file` calls are replaced with short placeholders until it is under 60% of the budget. The task prompt and the latest messages are always kept. If the API still says the context is too long, the harness prunes harder and retries.
- **Retries**: HTTP 408, 409, 425, 429, 5xx and 529, connection errors and timeouts are retried with exponential backoff (honouring `Retry-After`), `--retries` times.
- **Outputs**: `.wcb/usage.json` (always, also on errors and SIGTERM); a JSONL transcript at `$WCB_SESSION_DIR/simple-transcript.jsonl` (every request, reply, tool call and result); one line per tool call on stdout.
- **Exit status**: 0 normal end; 1 model API failure after retries; 2 configuration error (missing key, prompt or workspace); 128+signal when stopped.

### Options

| Option | Default | Meaning |
|---|---|---|
| `--provider` | required | `anthropic` (Messages API) or `openai` (Chat Completions, any compatible server). |
| `--model` | required | Model ID as the endpoint expects it. |
| `--max-turns` | 80 | Model calls per session. |
| `--max-tokens` | 8000 | Output tokens per call. Reasoning models spend thinking tokens from this too. |
| `--context-budget` | 100000 | Estimated conversation tokens before old tool output is dropped. |
| `--max-tool-output` | 20000 | Characters per tool result. |
| `--temperature` | provider default | Sampling temperature. Some reasoning models reject it. |
| `--base-url` | see below | API base URL. |
| `--api-key-env` | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Variable holding the key. Add it to `env_passthrough`. |
| `--no-prompt-cache` | off | Anthropic: do not send `cache_control` breakpoints. |
| `--request-timeout` | 600 | Seconds per API call. |
| `--retries` | 6 | Retries for transient errors. |
| `--price-input`, `--price-output` | none | USD per million tokens; fills `cost_usd`. |
| `--price-cache-read` | `--price-input` | USD per million cached input tokens. Anthropic cache writes are charged at 1.25 x the input price. |
| `--system-prompt-file` | built in | Replace the system prompt. |
| `--workspace`, `--prompt-file`, `--prompt`, `--phase` | `WCB_*` | For running outside `wcb run`. |
| `--transcript` | `$WCB_SESSION_DIR/simple-transcript.jsonl` | Transcript path; `''` disables it. |
| `--quiet` | off | Print only the final summary line. |

### Providers

**Anthropic** (`--provider anthropic`): `POST {ANTHROPIC_BASE_URL or https://api.anthropic.com}/v1/messages` with `x-api-key: $ANTHROPIC_API_KEY` and `anthropic-version: 2023-06-01`, native `tool_use` blocks. Prompt caching is on: the system prompt, the tool list and the newest message carry `cache_control` breakpoints, so each turn re-reads earlier turns from cache. A base URL ending in `/v1` is accepted too.

**OpenAI-compatible** (`--provider openai`): `POST {OPENAI_BASE_URL or https://api.openai.com/v1}/chat/completions` with `Authorization: Bearer $OPENAI_API_KEY` and `function` tools. The key is required only for `api.openai.com`; without a key no `Authorization` header is sent. The harness sends `max_completion_tokens` to api.openai.com and `max_tokens` elsewhere, and switches automatically if the server rejects one of them.

### Any OpenAI-compatible endpoint

The model must support tool (function) calling through the endpoint; models that only answer in text will stop after a few turns without doing anything.

**OpenRouter**

```bash
export OPENAI_BASE_URL=https://openrouter.ai/api/v1
export OPENROUTER_API_KEY=...
```

```yaml
model: openrouter/<vendor>/<model>
cmd: [python, -I, -m, wcb.agents.simple, --provider, openai, --model, "<vendor>/<model>",
      --api-key-env, OPENROUTER_API_KEY]
env_passthrough: [OPENROUTER_API_KEY, OPENAI_BASE_URL]
```

Pick a model whose OpenRouter page lists tool support.

**vLLM**

```bash
vllm serve <hf-org>/<model> --enable-auto-tool-choice --tool-call-parser <parser> --max-model-len 65536
export OPENAI_BASE_URL=http://localhost:8000/v1
```

The tool-call parser must match the model family (for example `hermes` for Qwen-style models, `llama3_json` for Llama 3.x, `mistral` for Mistral); see the vLLM tool-calling docs. `--model` is the served model name. Set `--context-budget` to about 70% of `--max-model-len`, leaving room for `--max-tokens`.

**Ollama**

```bash
OLLAMA_CONTEXT_LENGTH=32768 ollama serve      # or PARAMETER num_ctx 32768 in a Modelfile
ollama pull <model>
export OPENAI_BASE_URL=http://localhost:11434/v1
```

Ollama's default context window is small and it truncates silently when it is exceeded, so the model loses the task. Raise it as above, and pass `--context-budget 20000 --max-tool-output 8000` for a 32k window. Use a model tagged with tool support.

**Others**: LM Studio (`http://localhost:1234/v1`), llama.cpp server (`--jinja` for tool calls), Together, Groq, Fireworks, Mistral, Gemini's OpenAI-compatible endpoint and corporate gateways work the same way: set `OPENAI_BASE_URL`, the key variable and `--model`.

### Budgets

Each turn resends the conversation, so input tokens grow roughly with the square of the number of turns until pruning kicks in. With prompt caching (explicit for Anthropic; automatic at OpenAI and some other providers) most of it is billed at the cached rate. Expect tens of turns per ingestion day. Start with `--max-days 1`, read the transcript, and set `--max-turns` and `timeout_s` from what you see.

## 10. Example commands

Start with `wcb doctor`. It checks the adapter file, looks for its commands on `PATH`, plays the two-day mini world (two ingestion and two query sessions, plus the seed session in Track B, no oracle sessions), validates every store and answers file, and scores the run. Each problem comes with a hint and the last lines of the session's `stderr.log`. It exits 0 when nothing failed.

```bash
wcb doctor --adapter my-agent.yaml                  # Track A on the mini world
wcb doctor --adapter my-agent.yaml --track B
wcb doctor --adapter my-agent.yaml --world pilot --out runs/doctor   # a bigger world, kept
```

```text
  [ok]   adapter file is valid: /path/to/my-agent.yaml
  [warn] env_passthrough: ANTHROPIC_API_KEY is not set here, so sessions will not get it
         export ANTHROPIC_API_KEY=... before running, or remove it from env_passthrough
  [ok]   ingest command found: my-agent
  [FAIL] session 2027-01-11.ingest: failed (exit 1) in 2.3s
         logs: runs/doctor/mini/r1/sessions/2027-01-11.ingest/stderr.log
         last stderr lines:
           KeyError: 'ANTHROPIC_API_KEY'
```

The null adapter scores 16.7 WCB on the mini world; anything that ingests correctly should beat it.

```bash
# Smoke test on the pilot: one day, no oracle sessions
wcb run --adapter adapters/examples/simple-openai.yaml --world pilot --out runs/smoke --max-days 1 --no-oracle

# Query side only, against oracle stores (cheap; measures synthesis)
wcb run --adapter my-agent.yaml --world pilot --out runs/synthesis --skip-ingest

# Several repeats on the dev split, then score
wcb run --adapter my-agent.yaml --split dev --repeats 3 --out runs/my-agent-dev
wcb score runs/my-agent-dev

# Inspect a session
cat runs/smoke/pilot/r1/sessions/*/session.json | jq '{phase, date, status, wall_s, usage}'
jq -c 'select(.event == "turn") | .reply.tool_calls[].name' \
  runs/smoke/pilot/r1/sessions/<date>.ingest/simple-transcript.jsonl | sort | uniq -c
wcb validate store runs/smoke/pilot/r1/snapshots/<date>
wcb validate answers runs/smoke/pilot/r1/answers/cp1.json \
  --questions runs/smoke/pilot/r1/sessions/cp1.query/questions.json

# Run the simple harness by hand on a copy of a store
python -m wcb.agents.simple --provider anthropic --model <model-id> \
  --workspace /tmp/store-copy --prompt "Today is 2027-03-01. ..." --phase ingest
```

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` / `OPENAI_API_KEY is not set` | Export the key in the shell that runs `wcb`, and list it in `env_passthrough`. |
| `--model is still the placeholder <model-id>` | Edit the adapter: replace `<model-id>` in `cmd` and `model:`. |
| `authentication failed (HTTP 401)` | Wrong key for that endpoint, or the key is for another provider. With `--api-key-env`, check the variable name is in `env_passthrough`. |
| `HTTP 404 ... does not exist there or the base URL is wrong` | Check the model ID and the base URL. OpenAI-compatible URLs usually end in `/v1`. |
| `not JSON` response | The base URL points at a web page or a login proxy, not the API. |
| `giving up ... after 7 attempts` | Rate limits or an outage. Lower concurrency, raise `--retries`, or try later. |
| `context too long ... no old tool output is left to drop` | Lower `--max-tool-output`, `--context-budget` and `--max-tokens` (the server reserves room for the output), or use a model with a larger context. |
| Simple harness stops with `stop: no_progress` or after a few turns without writing anything | The model is not making tool calls: use a model and server with tool calling enabled (vLLM needs `--enable-auto-tool-choice`). |
| `stop: max_turns` on every ingest day | Raise `--max-turns` (and `timeout_s`), or use a model that batches its work. |
| Answers `missing` in a query session | The agent did not write `.wcb/answers.json` in `{workspace}`. CLI agents: make sure their root is the workspace (`--cd {workspace}` for Codex). |
| `Permission denied` writing the store in a query session | Expected: query sessions are read-only. Write only `.wcb/answers.json`. |
| Every session times out | The agent is waiting for input or approval. Use its non-interactive mode and permission flags, and read `stdout.log`/`stderr.log`. |
| `'claude' was not found on PATH` | Install the CLI, or set `PATH` in `env` (the session `PATH` is yours with the `wcb` interpreter first). |
| Claude Code: `Not logged in` or `Invalid API key` | `--bare` uses only `ANTHROPIC_API_KEY`; export it and keep it in `env_passthrough`. |
| Claude Code refuses `--dangerously-skip-permissions` | It refuses to run that way as root. Run as a normal user (`docker run --user ...`). |
| Codex: `Not inside a trusted directory` | Keep `--skip-git-repo-check`. |
| Codex: sandbox errors on Linux (Landlock or seccomp) | The kernel or container does not support Codex's sandbox. Inside a container that already isolates the session, replace `--sandbox workspace-write` with `--dangerously-bypass-approvals-and-sandbox`. |
| `usage.json` missing or all zeros for a CLI agent | Run it under `wcb.agents.wrap` with the agent's JSON output format (`--output-format stream-json --verbose` for Claude Code, `--json` for Codex). |
| Ollama answers nonsense after a few turns | Its context window is too small and it truncates silently; raise `num_ctx` / `OLLAMA_CONTEXT_LENGTH` and lower `--context-budget`. |
| The adapter loads with `unknown key` warnings | Phase blocks accept only `cmd`, `cwd` and `timeout_s`; top-level keys are listed in section 2. |

See [running §13](running.md#13-troubleshooting) for runner-side problems (unbuilt worlds, resume, leftover workspaces).
