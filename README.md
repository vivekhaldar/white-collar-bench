# white-collar-bench

**Can an AI agent keep track of your work?**

A lot of senior knowledge work is not producing things but keeping track of them. Every day brings a stream of email, chat, meetings, documents and calendar changes. Buried in that stream are commitments ("I'll send you the costing by Friday"), decisions, handoffs, slipped deadlines and quiet reversals. The job is to keep an accurate picture of who owes what to whom, where each project really stands and what changed, and to act on it.

That bookkeeping is exactly what people hope AI assistants will take over. white-collar-bench measures whether they can. It runs an agent through weeks of simulated work and checks whether it keeps an accurate, usable record that it can still answer from days later.

## Why another benchmark

Existing benchmarks cover parts of this work: workplace tool use, search over enterprise documents, memory of long conversations. None of them tests the whole job as it plays out in practice:

- **Memory is a durable artifact.** The agent keeps its knowledge in files it reads and writes, the way a person keeps notes, not in a hidden context window.
- **Errors compound.** Inputs arrive day by day and are gone afterwards. A missed handoff on Tuesday is a wrong answer on Friday, so the benchmark measures sustained reliability, not one-shot accuracy.
- **Judgment counts, not just recall.** Questions such as "What is the status of the pilot?" or "What should I focus on tomorrow?" need current, complete, prioritized answers, with honest abstention when the record does not support one.

More in [motivation and related work](docs/motivation.md).

## What it measures

Each run replays a stretch of simulated workdays for one knowledge worker: about 300 messages and documents in a typical week, across a dozen projects and dozens of people.

1. **Ingestion: keeping the record right.** Each simulated day a fresh agent process receives that day's inbox and updates its store, its notes about people, organizations, projects and open commitments. Then the inbox disappears. The store is the agent's only memory.
2. **Synthesis: answering from the record.** At checkpoints a fresh process answers questions from the store alone, with citations to the evidence. For example: "What do I owe Ramona?", "Who now owns the retention schedule?", "What changed on the pilot since Monday?", "When was the hosting decision made?" Some questions have no knowable answer yet, and the right response is to abstain.

The inputs are hard in the ways real work is hard:

- **Names:** people appear under nicknames, initials, email handles and job titles, and two colleagues can share a first name.
- **Facts change:** deadlines move, owners hand work off, decisions get reversed, and corrections arrive days later.
- **Evidence is weak:** a draft that was never sent, a calendar acceptance that proves nothing, a task that is only implied to be done.
- **Inputs are messy:** meeting transcripts with misheard names, attachments, newsletters and notices that are pure noise, and an embedded instruction that a careful assistant must not obey.

All of this is generated from a hidden, event-sourced model of what really happened, so every answer has an exact, auditable gold standard. See [design](docs/design.md) for how that works.

### Scores

| Score | What it tells you |
|---|---|
| **WCB score** (headline) | How well the agent answers from the record it built, macro-averaged over question types, 0–100 |
| **Synthesis** | The same questions answered from a perfect record: answering skill on its own |
| **Ingestion cost** | The gap between the two: what imperfect record-keeping costs |
| **Store integrity (SIS)** | Whether the record stays valid, grounded in evidence and current |

There are two tracks. In **Track A** the agent starts from a correct store and must maintain it under a published [store contract](contract/CONTRACT.md). In **Track B** it starts from raw history and organizes its memory however it likes; only its answers are graded.

## Run your agent

The runner drives the simulated days, and you provide a small adapter file that tells it how to start your agent. Adapters for Claude Code, Codex, any model behind a simple tool loop (Anthropic or OpenAI-compatible), Docker containers and custom scripts are included.

| I want to… | Read |
|---|---|
| Install, smoke-test and run an agent | [Running the benchmark](docs/running.md) |
| Connect my own agent or model | [Adapters](docs/adapters.md) |
| Understand how answers are graded | [Scoring](docs/scoring.md) and [judges](docs/judge.md) |
| Know what my agent will see and must write | [Data formats](docs/formats.md) and the [store contract](docs/contract.md) |
| Submit results | [Submissions and the leaderboard](docs/leaderboard.md) |
| Use it from Python | [Python API](docs/api.md) |

## Documentation

**Understand the benchmark**
- [Motivation and related work](docs/motivation.md)
- [Benchmark design](docs/design.md)
- [Status and open items](docs/status.md)
- [Results](results/README.md)

**Run it**
- [Running the benchmark](docs/running.md), including a command reference
- [Adapters](docs/adapters.md)
- [Scoring and run protocol](docs/scoring.md)
- [Judges](docs/judge.md)
- [Submissions and the leaderboard](docs/leaderboard.md)

**How it is built**
- [Worlds](docs/worlds.md), [questions and gold answers](docs/questions.md) and [data formats](docs/formats.md)
- [World generator](docs/generator.md) and [calibration targets](docs/calibration.md)
- [Store contract and validator](docs/contract.md)
- [Privacy policy and leak scanner](docs/privacy.md)
- [Construction plan](docs/plan.md)

**Contribute**
- [Contributing](CONTRIBUTING.md): repository layout, tests and the synthetic-data rule

## License

Apache License 2.0; see [LICENSE](LICENSE). All worlds, people, organizations and documents in this repository are synthetic.
