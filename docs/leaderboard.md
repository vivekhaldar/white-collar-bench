# Submissions and the leaderboard

Status: v0.1 draft. This describes how results are produced for the public leaderboard (plan milestone M6). The tooling for the private test split (`scripts/make_test_split.py`) and metered runs (`wcb run --meter`) is in place. Until the first release's test split is published, results on `pilot` and `dev` are self-reported.

## What to submit

1. **An agent image.** A container image that runs one session given the `WCB_*` environment (see [adapters](adapters.md#environment)) and only reads and writes `/workspace`. It must not contain benchmark worlds or gold.
2. **An adapter.** Usually [`adapters/examples/docker.yaml`](../adapters/examples/docker.yaml) with your image name and command filled in. Adapters may wrap the standard prompt with your own generic system prompt, but must not contain knowledge specific to any world.
3. **Model identifiers.** Every model the agent calls, with versions, so results can be reproduced.

## How verified runs work

Maintainers run the submission on the private `test` split:

- **Track A** and/or **Track B**, 3 repeats per world.
- **Isolation:** one fresh container per session, with no access to anything outside the workspace.
- **Scoring:** the pinned judge for the release (see [judges](judge.md)).
- **Metered mode:** `wcb run --meter` sends model calls through the runner's proxy (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`, `WCB_LLM_BASE_URL`), so token use is measured rather than self-reported. Agents must honour these variables. See [running](running.md#7a-metered-runs).

Published results include the harness version, the wcb version, the models, the date, cost per simulated day, and the WCB score with its 95% confidence interval. Entries whose intervals overlap are reported as tied. Test worlds are regenerated for each release, and older results are marked with their release.

## Self-reported results on dev worlds

Before submitting, develop and debug on `pilot` and `dev`, which ship with gold:

```bash
wcb run --adapter my-adapter.yaml --split dev --track A --repeats 3 --out runs/my-agent
wcb score runs/my-agent
```

When you report dev results, attach a bundle and name the models used. State whether sessions ran in containers ([docker.yaml](../adapters/examples/docker.yaml)) or directly on the host.

```bash
wcb bundle runs/my-agent                     # writes runs/my-agent.tar.gz
wcb bundle runs/my-agent --logs              # also session logs and agent transcripts
```

A bundle holds `run.json`, the score report, the adapter file (if unchanged since the run), each session's `session.json` and `usage.json`, and the answers. `MANIFEST.json` lists every file with its SHA-256, plus the headline numbers and judge. Logs and store snapshots (`--snapshots`) are left out by default, because they are large and logs can contain environment details. Check them before you share them.

## Rules

- No world-specific knowledge in prompts, tools or training data. Dev and pilot worlds are public; tuning on them is fine, but test worlds are new for each release.
- The agent may keep anything it likes inside the workspace between sessions (Track B), or anything allowed by the [contract](../contract/CONTRACT.md) (Track A). No other state may persist between sessions.
- Query sessions are read-only; any changes are discarded.
- One submission per agent version per release.

## Preparing a release (maintainers)

Test worlds are generated from secret seeds and never committed. `worlds/test/` is git-ignored, and the split can also live outside the repository:

```bash
python scripts/make_test_split.py --release 2027.1 --out ~/wcb-private/test-2027.1 --mix 1w:4,2w:1,small:1
wcb run --adapter submission.yaml --split ~/wcb-private/test-2027.1 --track A --repeats 3 --out runs/<entry>
wcb score runs/<entry> --judge llm --judge-model <pinned judge>
```

The script writes the worlds, `SEEDS.private.json` (keep it secret) and `commitments.json`. For each world, `commitments.json` records the generation parameters, a salted hash of the seed, and the SHA-256 of `world.jsonl` and `questions.yaml`. Publish `commitments.json` when the release opens. When the release is retired, publish the seeds. Then anyone can run `python scripts/make_test_split.py --verify DIR` to regenerate the worlds and check that they match what was committed before any submission was scored. Regeneration is deterministic only for the same wcb version, which both files record.
