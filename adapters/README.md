# Adapters

An adapter is a small YAML file that tells `wcb run` how to start your agent for one session. The full reference, with rules, worked examples and troubleshooting, is [docs/adapters.md](../docs/adapters.md). The runner side is described in [docs/running.md](../docs/running.md).

## Examples

| File | What it runs | Needs |
|---|---|---|
| [`examples/null.yaml`](examples/null.yaml) | The null baseline: does nothing, abstains on every question. The score floor. | Nothing |
| [`examples/simple-anthropic.yaml`](examples/simple-anthropic.yaml) | A raw Anthropic model in the simple tool loop (`python -m wcb.agents.simple`). | `ANTHROPIC_API_KEY`; replace `<model-id>` |
| [`examples/simple-openai.yaml`](examples/simple-openai.yaml) | A raw model over the OpenAI Chat Completions API: OpenAI, OpenRouter, vLLM, Ollama and other compatible servers. | `OPENAI_API_KEY` (not for local servers), optional `OPENAI_BASE_URL`; replace `<model-id>` |
| [`examples/claude-code.yaml`](examples/claude-code.yaml) | Claude Code in `--print` mode, with usage from its stream-json output. | `claude` on `PATH`, `ANTHROPIC_API_KEY`; a container for verified runs |
| [`examples/codex.yaml`](examples/codex.yaml) | OpenAI Codex CLI (`codex exec`) in a workspace-write sandbox, with usage from its JSON events. | `codex` on `PATH`, `OPENAI_API_KEY`/`CODEX_API_KEY` or `codex login` |
| [`examples/custom-script.yaml`](examples/custom-script.yaml) + [`examples/custom_agent_template.py`](examples/custom_agent_template.py) | A heavily commented, standard-library-only agent script to copy and extend. Works as shipped (logs inputs, abstains). | Nothing |

```bash
wcb world build pilot
wcb run --adapter adapters/examples/null.yaml --world pilot --out runs/null
wcb run --adapter adapters/examples/simple-anthropic.yaml --world pilot --out runs/simple --max-days 1
wcb score runs/simple
```

## Writing your own

1. Copy the example closest to your agent.
2. Set `name`, `version` and `model` to what you actually run.
3. Put API keys in `env_passthrough`; sessions get nothing else from your environment.
4. Keep prompts and system prompts generic: no knowledge of any world, its people or its questions.
5. Make every session a fresh process with no memory outside the workspace, and write `.wcb/usage.json`.
6. Try it with `--max-days 1`, then read `runs/<name>/<world>/r1/sessions/*/stdout.log`.

Reusable pieces in `wcb.agents`:

- `wcb.agents.simple`: the simple harness (one model, fixed file tools, usage reporting).
- `wcb.agents.tools`: the workspace-confined file tools it uses.
- `wcb.agents.providers`: `urllib`-only Anthropic and OpenAI-compatible clients with retries.
- `wcb.agents.docs_text`: text extraction for `.docx`, `.xlsx`, `.pptx`, `.pdf`, `.eml` and `.ics`.
- `wcb.agents.wrap`: runs a CLI agent and writes `.wcb/usage.json` from its JSON output.
