# Motivation and related work

## The workload

Much senior knowledge work is coordination rather than production. Each day, a knowledge worker receives a stream of email, chat messages, meeting notes, documents and status updates. Some of these items create commitments, record decisions or change a project's status. Others change what the worker owes a colleague or what a colleague owes them. The work is to keep an accurate picture of that state and to act on it.

white-collar-bench models this work as a **knowledge store**: a repository of plain files, usually Markdown under version control, containing interlinked records:

- **Projects:** goals, current status, durable context and a dated log.
- **Open loops:** tasks, asks, commitments and decisions, each with an owner, status and evidence.
- **People:** roles, relationships and active threads with the worker.
- **Logs and sources:** meeting notes, journals, captured emails and documents that provide evidence for the records.

Two workloads dominate.

1. **Synthesis.** Answer high-level questions whose answers are spread across many records and sources. Examples include "What is the status of Project Thistledown?", "What am I working on with Priya?", "What do I owe whom this week?" and "What changed since Monday?" A good answer is current, complete, grounded in evidence and honest about uncertainty.
2. **Ingestion.** Incorporate new material into the existing network of records. The agent must recognize which projects and people an item concerns, including aliases and indirect references. It must also update status and logs, create new projects, people or loops only when warranted, and avoid duplicates, stale state and contradictions between records.

These workloads depend on each other. Synthesis is only as good as the store that previous ingestions produced, and errors accumulate over time. A misattributed email or a duplicated person record will distort later answers.

## Why a new benchmark

There is no standard way to compare models and agent harnesses on this workload. Practitioners choose models for a personal or team knowledge store based on general benchmarks, anecdotes or vendor claims. A useful benchmark must:

- Exercise the store as a **persistent artifact** that the agent reads and writes, rather than a fixed corpus that it only queries.
- Measure **cumulative correctness** across a sequence of ingestions, not just one-shot accuracy.
- Grade **synthesized judgment**, such as whether a status summary is current, complete and prioritized, as well as factual recall.
- Respect **store conventions**: schema, record boundaries, evidence requirements and privacy rules that a real knowledge store enforces.
- Use **entirely synthetic data**. Real knowledge stores contain confidential projects and people, so the benchmark can borrow structure and failure modes from real stores but must never contain their content.

## Related work

The benchmarks below each cover part of this workload. Descriptions are based on each paper's abstract or summary.

### Enterprise and workplace agents

| Benchmark | What it measures | Writes persistent state? |
|---|---|---|
| **TheAgentCompany** (Xu et al., 2024) [1] | About 175 tasks in a simulated software company with internal sites for code hosting, file sharing, project tracking and chat. Agents browse, code and communicate with simulated colleagues. Checkpoint-based partial credit. | Yes, in third-party services |
| **WorkBench** (Styles et al., 2024) [2] | 690 tasks across five workplace databases (email, calendar, project management, analytics, CRM) using 26 tools. Graded by the resulting database state. | Yes, in tool databases |
| **CRMArena / CRMArena-Pro** (Huang et al., 2024; 2025) [3, 4] | Professional CRM tasks in a synthetic Salesforce environment, extended to sales, service and confidentiality-awareness scenarios in the Pro version. | Yes, in CRM records |
| **WorkArena / WorkArena++** (Drouin et al., 2024; Boisvert et al., 2024) [5, 6] | Browser-based knowledge-work tasks in ServiceNow, extended in the ++ version to compositional tasks that require planning and reasoning. | Yes, in platform records |
| **OfficeBench** (Wang et al., 2024) [7] | Office automation across several applications per task. | Yes, in output files |
| **AppWorld** (Trivedi et al., 2024) [8] | 750 everyday tasks across nine simulated consumer apps, graded by state checks. | Yes, in app databases |
| **τ-bench / τ²-bench** (Yao et al., 2024; Barres et al., 2025) [9, 10] | Tool-using customer-service agents that must follow domain policy during multi-turn dialogue. | Yes, in transactions |
| **GDPval** (OpenAI, 2025) [11] | 1,320 expert-designed deliverables from 44 occupations, graded by blinded experts against human work. | One-shot artifacts |

These benchmarks show that grading by environment state works and that realistic workplace simulation is feasible. However, the state they write is a set of **transactional records**, such as tickets, bookings, CRM fields and calendar entries, in a fixed schema. They do not test maintaining an evolving, interpretive model of a person's work. Tasks are largely independent, so errors do not compound across a sequence of updates. GDPval tests the quality of high-value deliverables, but each task is self-contained and does not involve accumulated context.

### Cross-source enterprise and personal search

| Benchmark | What it measures | Writes persistent state? |
|---|---|---|
| **HERB** (Choubey et al., 2025) [12] | Multi-hop "deep search" over 39,190 synthetic enterprise artifacts: documents, meeting transcripts, Slack messages, GitHub items and URLs. Covers simulated product planning, development and support workflows, with answerable and unanswerable questions. | No |
| **PersonaBench** (Tan et al., 2025) [13] | Questions about a user's biography, preferences and social connections, answered from synthetic private documents. | No |
| **EnronQA** (2025) [14] | Retrieval and question answering over the real Enron email corpus. | No |

HERB is the closest match to synthesis. It uses synthetic data, mixes heterogeneous workplace sources, includes human-to-human interactions and contains unanswerable questions. PersonaBench is close for questions about people. Both treat the corpus as fixed and read-only, and their questions mostly have short factual answers. Neither tests the store that a worker or agent builds from those sources, nor open-ended synthesis such as a status summary.

### Agent memory

| Benchmark | What it measures | Writes persistent state? |
|---|---|---|
| **LongMemEval** (Wu et al., 2024) [15] | 500 questions over long chat histories, covering information extraction, multi-session reasoning, temporal reasoning, knowledge updates and abstention. | No; the system under test may maintain memory |
| **LoCoMo** (Maharana et al., 2024) [16] | Very long multi-session conversations evaluated by question answering, event summarization and dialogue generation. | No |
| **MemoryAgentBench** (Hu et al., 2025) [17] | Memory agents that receive information incrementally across turns, tested on retrieval, test-time learning, long-range understanding and selective forgetting. | Internal memory |
| **MEMTRACK** (Deshpande et al., 2025) [18] | Long-term memory and state tracking over interleaved Slack, Linear and Git timelines with noisy, conflicting and cross-referencing events. Scores correctness, efficiency and redundancy. | Internal memory |
| **LongMemEval-V2** (2026) [19] | Whether web agents internalize environment-specific experience over time. | Internal memory |
| **EvalMem** (2026) [20] | Diagnoses memory-system failures as encoding, retrieval or generation errors. | Internal memory, inspected |

This group is closest to ingestion. MEMTRACK is the nearest overall: it uses multi-platform workplace timelines with conflicting updates and penalizes redundancy. EvalMem's separation of encoding failures from retrieval failures matches the distinction between ingestion errors and synthesis errors. However, these benchmarks treat memory as an **internal mechanism** of the system under test and grade it mainly through downstream questions. They do not inspect a shared, human-readable store, or check whether it follows conventions, whether its records stay consistent or whether a person could audit it. Their source material is usually conversation or software-development telemetry, not the broader mix of a knowledge worker's inputs.

### Meetings and extraction

**QMSum** [21] and **MeetingBank** [22] evaluate meeting summarization, with QMSum adding query-focused summaries. **DocRED** [23] evaluates document-level relation extraction. These tasks are useful components of ingestion: extracting decisions, actions and owners from a transcript, and resolving entity references. However, they are single-document tasks with no persistent target.

### Aggregates

**EGI-BENCH** [24] combines eight existing enterprise benchmarks, including CRMArena, HERB and PersonaBench, into one evaluation harness. Its scope suggests that individual-scale knowledge management is not yet a recognized category of its own.

## Gaps that white-collar-bench addresses

1. **The store is the subject of evaluation.** The agent reads and writes a human-readable repository. Grading inspects the resulting files, including entity links, status fields, logs and evidence, as well as answers.
2. **Errors compound.** Ingestion tasks run as ordered sequences against an evolving store. Duplicates, misattributions and stale status persist and degrade later synthesis. This measures long-run reliability rather than isolated accuracy.
3. **Entity resolution and creation are central.** People appear under nicknames, email handles and roles; projects appear under code names and informal references. The agent must decide when an item concerns an existing record and when it warrants a new one.
4. **Temporal and evidential reasoning.** A scheduled meeting is not evidence that it happened, and a later email can supersede an earlier decision. Answers must reflect the current state and cite evidence.
5. **Judgment-heavy synthesis.** Status summaries and relationship briefs are graded for currency, completeness, prioritization and honest uncertainty, not just factual recall.
6. **Convention adherence.** Each store defines a schema, record boundaries and privacy rules. Following them is part of the task.
7. **Mixed real-world inputs.** Email threads, chat messages, meeting transcripts, documents and the worker's own shorthand notes appear together, with realistic noise.
8. **Synthetic by construction.** Every project, person and organization is generated, which avoids the confidentiality problem that prevents real knowledge stores from being shared.

## References

1. Xu et al. *TheAgentCompany: Benchmarking LLM Agents on Consequential Real World Tasks.* 2024. arXiv:2412.14161.
2. Styles et al. *WorkBench: a Benchmark Dataset for Agents in a Realistic Workplace Setting.* 2024. arXiv:2405.00823.
3. Huang et al. *CRMArena: Understanding the Capacity of LLM Agents to Perform Professional CRM Tasks in Realistic Environments.* 2024. arXiv:2411.02305.
4. Huang et al. *CRMArena-Pro: Holistic Assessment of LLM Agents Across Diverse Business Scenarios and Interactions.* 2025. arXiv:2505.18878.
5. Drouin et al. *WorkArena: How Capable Are Web Agents at Solving Common Knowledge Work Tasks?* 2024. arXiv:2403.07718.
6. Boisvert et al. *WorkArena++: Towards Compositional Planning and Reasoning-based Common Knowledge Work Tasks.* 2024. arXiv:2407.05291.
7. Wang et al. *OfficeBench: Benchmarking Language Agents across Multiple Applications for Office Automation.* 2024. arXiv:2407.19056.
8. Trivedi et al. *AppWorld: A Controllable World of Apps and People for Benchmarking Interactive Coding Agents.* 2024. arXiv:2407.18901.
9. Yao et al. *τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains.* 2024. arXiv:2406.12045.
10. Barres et al. *τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment.* 2025. arXiv:2506.07982.
11. OpenAI. *GDPval: Evaluating AI Model Performance on Real-World Economically Valuable Tasks.* 2025. arXiv:2510.04374.
12. Choubey et al. *Benchmarking Deep Search over Heterogeneous Enterprise Data.* 2025. arXiv:2506.23139.
13. Tan et al. *PersonaBench: Evaluating AI Models on Understanding Personal Information through Accessing (Synthetic) Private User Data.* 2025. arXiv:2502.20616.
14. *EnronQA: Towards Personalized RAG over Private Documents.* 2025. arXiv:2505.00263.
15. Wu et al. *LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory.* 2024. arXiv:2410.10813.
16. Maharana et al. *Evaluating Very Long-Term Conversational Memory of LLM Agents.* 2024. arXiv:2402.17753.
17. Hu et al. *Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions.* 2025. arXiv:2507.05257.
18. Deshpande et al. *MEMTRACK: Evaluating Long-Term Memory and State Tracking in Multi-Platform Dynamic Agent Environments.* 2025. arXiv:2510.01353.
19. *LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues.* 2026. arXiv:2605.12493.
20. *EvalMem: An Operation-Level Diagnostic Framework for Long-Term Memory Systems.* 2026. arXiv:2609.22231.
21. Zhong et al. *QMSum: A New Benchmark for Query-based Multi-domain Meeting Summarization.* 2021. arXiv:2104.05938.
22. Hu et al. *MeetingBank: A Benchmark Dataset for Meeting Summarization.* 2023. arXiv:2305.17529.
23. Yao et al. *DocRED: A Large-Scale Document-Level Relation Extraction Dataset.* 2019. arXiv:1906.06127.
24. *EGI-BENCH: An Enterprise General Intelligence Benchmark Suite.* 2026. arXiv:2610.27234.
