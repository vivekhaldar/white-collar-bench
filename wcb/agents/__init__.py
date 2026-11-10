"""Reference agents and helpers for connecting agents to white-collar-bench.

- :mod:`wcb.agents.simple`: the simple harness, one model behind a fixed file-tool loop
  (``python -m wcb.agents.simple --provider anthropic|openai --model <id>``).
- :mod:`wcb.agents.tools`: the workspace-confined file tools the harness exposes.
- :mod:`wcb.agents.providers`: ``urllib``-only Anthropic and OpenAI-compatible model clients.
- :mod:`wcb.agents.docs_text`: plain-text extraction for .docx, .xlsx, .pptx, .pdf, .eml, .ics.
- :mod:`wcb.agents.wrap`: runs a CLI agent and writes ``.wcb/usage.json`` from its JSON output.

See docs/adapters.md for how to use them from an adapter file.
"""
