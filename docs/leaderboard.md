# Submissions and the leaderboard

Status: v0.1 draft. This describes how results are produced for the public leaderboard (plan milestone M6). The private test split and metered model proxy are not yet available; until they are, results on `pilot` and `dev` are self-reported.

## What to submit

1. **An agent image.** A container image that runs one session given the `WCB_*` environment (see [adapters](adapters.md#environment)) and only reads and writes `/workspace`. It must not contain benchmark worlds or gold.
2. **An adapter.** Usually [`adapters/examples/docker.yaml`](../adapters/examples/docker.yaml) with your image name and command filled in. Adapters may wrap the standard prompt with your own generic system prompt, but must not contain knowledge specific to any world.
3. **Model identifiers.** Every model the agent calls, with versions, so results can be reproduced.

## How verified runs work

Maintainers run the submission on the private `test` split:

- **Track A** and/or **Track B**, 3 repeats per world.
- **Isolation:** one fresh container per session, with no access to anything outside the workspace.
- **Scoring:** the pinned judge for the release (see [judges](judge.md)).
- **Metered mode (planned):** model calls go through the runner's proxy (`WCB_LLM_BASE_URL`) so token use and cost are measured, not self-reported.

Published results include the harness version, the wcb version, the models, the date, cost per simulated day, and the WCB score with its 95% confidence interval. Entries whose intervals overlap are reported as tied. Test worlds are regenerated for each release, and older results are marked with their release.

## Self-reported results on dev worlds

Before submitting, develop and debug on `pilot` and `dev`, which ship with gold:

```bash
wcb run --adapter my-adapter.yaml --split dev --track A --repeats 3 --out runs/my-agent
wcb score runs/my-agent
```

When you report dev results, include `runs/my-agent/scores/report.json`, the adapter file and the models used. State whether sessions ran in containers ([docker.yaml](../adapters/examples/docker.yaml)) or directly on the host.

## Rules

- No world-specific knowledge in prompts, tools or training data. Dev and pilot worlds are public; tuning on them is fine, but test worlds are new for each release.
- The agent may keep anything it likes inside the workspace between sessions (Track B), or anything allowed by the [contract](../contract/CONTRACT.md) (Track A). No other state may persist between sessions.
- Query sessions are read-only; any changes are discarded.
- One submission per agent version per release.
