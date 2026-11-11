# Contributing

Contributions are welcome: new worlds, grader fixes, adapters, baselines and results. Read [AGENTS.md](AGENTS.md) first. Every person, organization, project, message and date in this repository must be synthetic, and generated content that resembles a real person or organization must be replaced ([privacy](docs/privacy.md)).

## Repository layout

```text
contract/       Track A store contract, record schemas, answer schema, Track B goals
wcb/            Python package: world model, renderers, store tools, questions, runner, grading, privacy, agents
worlds/         pilot world and generated dev worlds (inputs, hidden truth; gold is built, not committed)
adapters/       example adapters for CLI agents, raw models and custom scripts
docker/         reference container image for agent sessions
docs/           design, formats, scoring, running, adapters, worlds, questions, judges, generator, privacy
results/        recorded benchmark runs, with configuration, costs and evidence
scripts/        maintenance scripts: dev-world generation, test splits, name pools, realism packets
tests/          unit and end-to-end tests (pytest)
```

## Development

```bash
uv venv && uv pip install -e '.[dev]'
source .venv/bin/activate
pytest                 # unit and end-to-end tests
ruff check .
wcb world build --all  # gold is deterministic; bump GOLD_VERSION (wcb/world/build.py) when it changes
```

- Dev worlds are regenerated with `scripts/make_dev_worlds.py`; `--check` verifies the committed worlds match.
- A change that alters built gold needs a `GOLD_VERSION` bump, so runs graded against older gold are flagged.
- Keep scorer changes measurable: add regression cases, and regrade saved runs rather than rewriting recorded results ([results](results/README.md)).
- Update the docs alongside code.
