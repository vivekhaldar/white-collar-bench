# white-collar-bench

**Can an AI agent keep track of your work?**

A lot of senior knowledge work is not producing things but keeping track of them. Every day brings a stream of email, chat, meetings, documents and calendar changes. Buried in that stream are commitments ("I'll send you the costing by Friday"), decisions, handoffs, slipped deadlines and quiet reversals. The job is to keep an accurate picture of who owes what to whom, where each project really stands and what changed, and to act on it.

That bookkeeping is exactly what people hope AI assistants will take over. white-collar-bench measures whether they can. It runs an agent through weeks of simulated work and checks whether it keeps an accurate record that it can still answer from days later.

## The gap it fills

Existing benchmarks each test part of this job. Workplace-agent benchmarks such as [TheAgentCompany](https://arxiv.org/abs/2412.14161) and [WorkBench](https://arxiv.org/abs/2405.00823) pose independent tasks, so a mistake never carries forward. Enterprise-search benchmarks such as [HERB](https://arxiv.org/abs/2506.23139) query a fixed, read-only corpus. Memory benchmarks such as [LongMemEval](https://arxiv.org/abs/2410.10813) and [MEMTRACK](https://arxiv.org/abs/2510.01353) treat memory as a hidden mechanism and grade it only through questions. white-collar-bench tests the whole job:

- **Memory is a store you can inspect.** The agent keeps what it knows in plain Markdown files, the way a person keeps notes. The benchmark grades those files day by day against what could be known so far, not just the answers given from them.
- **Errors compound.** Each day's inputs are deleted once that day is over. A missed handoff on Tuesday becomes a wrong answer on Friday, so the benchmark measures sustained reliability, not one-shot accuracy.
- **Judgment counts, not just recall.** "What's the status of the pilot?" needs an answer that is current, complete and prioritized. Some questions have no answer yet, and the right response is to say so.

More in [motivation and related work](docs/motivation.md).

## How it works

A run replays one to four weeks of simulated work for one knowledge worker. A typical week has about 300 emails, chats, meeting transcripts, documents and calendar invites, across a dozen projects and dozens of people. Two phases alternate:

1. **Ingestion.** Each simulated day, a fresh agent process receives that day's inbox and updates the **store**: a folder of Markdown records for people, organizations, projects, open commitments ("loops") and a daily log. Then the inbox is deleted. The store is the agent's only memory.
2. **Questions.** At checkpoints, a fresh process answers questions from the store alone and cites its evidence.

### An example

In the pilot world, the worker is Mara, an architect at a university system. On her first Monday, this exchange appears in a project chat channel:

> **Yusra:** @mara can you send the architecture one-pager before Thursday's ARB prep?<br>
> **Mara:** yep

A good agent turns that "yep" into a commitment, then closes it the next day when the one-pager goes out by email:

```markdown
<!-- loops/send-yusra-the-tinderbox-architecture-one-pager.md (abridged) -->
---
kind: ask
owner: people/me
counterparty: people/yusra-haddad
project: projects/tinderbox
status: done
evidence: [ch-0001, dc-0001, em-0004]
---
## Log
- 2027-02-15: Yusra asked me for the Tinderbox architecture one-pager before Thursday's ARB prep [src: ch-0001]
- 2027-02-16: Sent Yusra the Tinderbox architecture one-pager [src: dc-0001, em-0004]
```

Weeks later, the questions check whether the record kept up:

- *"When is Dmitri's LMS context API due now?"* In chat, Dmitri said "by Mar 5". A meeting transcript a week later moved it to "the 10th". The correct answer is 2027-03-10.
- *"What salary band did we offer Mats?"* Mats is what the candidate Mateus calls himself. No input ever states the band, so the agent should abstain.

The inputs are hard in the ways real work is hard. People go by nicknames, initials, handles and job titles, and two colleagues can share a first name. Deadlines move, owners hand work off and decisions get reversed. Evidence can be weak: a draft that was never sent, or a calendar acceptance that proves nothing. Newsletters and other noise mix with the signal, and one input even contains an instruction the agent must not obey.

### Exact gold answers

Every world is generated from a hidden, event-sourced log of what really happened: who committed to what, when deadlines moved, which decisions were reversed. The inputs are rendered from that log and the gold answers are computed from it. So every answer has an exact, auditable standard, and new worlds can be generated at will, which keeps the test set from being memorized. See [design](docs/design.md).

### Tracks and scores

In **Track A**, the agent starts from a correct store built from the prior weeks and must maintain it under a published [store contract](contract/CONTRACT.md). In **Track B**, it starts with an empty folder plus the prior weeks' raw inputs and organizes its memory however it likes; only its answers are graded.

| Score | What it tells you |
|---|---|
| **WCB score** (headline, per track) | How well the agent answers from its own record, 0–100, macro-averaged over eight question types: facts, lists, status, briefs, changes, dates, priorities and unanswerable |
| **Synthesis** (Track A) | The same questions answered from a perfect store: answering skill on its own |
| **Ingestion cost** (Track A) | Synthesis minus WCB: the points lost to imperfect record-keeping. Lower is better |
| **Store integrity, SIS** (Track A) | Whether the store stays valid, grounded in evidence and current. Lenient by design: an agent that never touches its correct starting store scores 91.5 |

## Results so far

Self-reported runs on the 11 public worlds, scored with the built-in heuristic judge. An agent that abstains on everything scores 12.7 (not zero: abstaining is the correct answer to unanswerable questions, one of the eight equally weighted question types, so it earns about 1/8 of the score).

| Agent | Track A | Track B |
|---|---:|---:|
| DeepSeek V4.1 Flash (Pi harness) | 84.6 | 67.5 |
| Qwen3.8-27B (Pi harness) | 72.3 | 55.0 |

Both models lose about 17 points when they have to design their own memory from scratch (Track B). The two runs used different benchmark revisions, so they are not a controlled comparison; see [results](results/README.md).

white-collar-bench is at v0.1. The public worlds, runner and scorer are complete. A private test split, the LLM judge's validation against human labels and verified leaderboard entries are still to come; see [status](docs/status.md).

## Try it

```bash
git clone https://github.com/vivekhaldar/white-collar-bench && cd white-collar-bench
uv venv && uv pip install -e '.[dev]' && source .venv/bin/activate
wcb run --adapter adapters/examples/null.yaml --world pilot --out runs/null
wcb score runs/null
```

To test your own agent, write a small adapter file that tells the runner how to start it. Adapters for Claude Code, Codex, any Anthropic or OpenAI-compatible model in a simple tool loop, Docker containers and custom scripts are included. `wcb doctor --adapter my-adapter.yaml` smoke-tests yours.

## Learn more

| I want to… | Read |
|---|---|
| Understand why the benchmark exists | [Motivation and related work](docs/motivation.md), [design](docs/design.md) |
| Install and run an agent | [Running the benchmark](docs/running.md), [adapters](docs/adapters.md) |
| Know what my agent sees and must write | [Data formats](docs/formats.md), [store contract](docs/contract.md) |
| Understand how answers are graded | [Scoring](docs/scoring.md), [judges](docs/judge.md) |
| See results or submit my own | [Results](results/README.md), [submissions and the leaderboard](docs/leaderboard.md) |
| Learn how worlds are built | [Worlds](docs/worlds.md), [questions](docs/questions.md), [generator](docs/generator.md), [calibration](docs/calibration.md), [privacy](docs/privacy.md) |
| Use it from Python, or contribute | [Python API](docs/api.md), [contributing](CONTRIBUTING.md), [status](docs/status.md), [plan](docs/plan.md) |

## License

Apache License 2.0; see [LICENSE](LICENSE). All worlds, people, organizations and documents in this repository are synthetic.
