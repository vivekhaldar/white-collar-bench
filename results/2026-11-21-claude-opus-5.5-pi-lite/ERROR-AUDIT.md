# Error audit: where Claude Opus 5.5 lost its WCB-lite points

Every point Claude Opus 5.5 lost on [WCB-lite](../../docs/lite.md), put into one of four classes. Scores are the rescored ones (`scores-fixed-lite`, scorer fixes from `ec9ff3d`): **Track A 87.5, Track B 72.4**. All worlds, people and organizations are synthetic.

## Conclusion

**Most of the missing points are not Opus's mistakes.** Opus's own errors cost about 2.3 points on Track A and 2.8 on Track B. The largest class is the grader: the heuristic judge misses answers that are right but worded differently. Next come gold items that are arguable or underspecified, then citation penalties.

| Class | Track A points (questions) | Track B points (questions) |
|---|---:|---:|
| 1. Model error | **2.3** (14) | **2.8** (21) |
| 2. Scoring or judge problem | **5.6** (18) | **16.0** (38) |
| 3. Gold or benchmark ambiguity | **3.0** (20) | **5.6** (35) |
| 4. Citation penalty | **1.5** (51) | **3.2** (77) |
| **Total lost** | **12.5** | **27.6** |

A question can appear in more than one class: its loss is split.

- **The LLM judge agrees.** Rescoring the same answers with the LLM judge (Claude Opus 5.5, 3 samples) gives **89.9 on Track A (+2.4) and 85.0 on Track B (+12.6)**.
- **Without grader and gold problems, Opus would score about 96 on A and 94 on B.** What is left is its own errors and citation penalties.
- **Track B's extra 15-point loss is mostly grading, not memory.** With the LLM judge, Track B trails Track A by 5.0 points, not 15.1. On the questions I checked, Track B's memory files held the facts the answers missed.
- **Caveat: the judge is the same model as the one being tested.** The LLM judge is Opus 5.5 grading Opus 5.5. [docs/judge.md](../../docs/judge.md) recommends a judge from another model family. I spot-checked the recoveries below, and the judge is not uniformly lenient: it rejects some matches and is stricter than the heuristic on tentative commitments. Still, class 2 is an upper estimate.

## Method

1. **Weights.** I re-ran the heuristic scorer in process to get each question's grader details (the report rows have none). I reused `weighted()` and `components()` from [analyze.py](analyze.py). Losses add up to 100 minus the score: 12.46 on A and 27.60 on B, both exact.
2. **Citation penalty (class 4).** The `base - score` part of each loss.
3. **Grader false negatives (class 2).** I scored every answer again with the LLM judge, `anthropic:claude-opus-5-5` with 3 samples per decision. The judge is the docs' default. The extra base credit it gives a question is counted as class 2. I filled the judge cache in parallel, then `wcb score --judge llm` read it. The Track B report gives 84.96, the same as my in-process scoring. For Track A I scored in process without SIS, which does not enter the WCB headline.
4. **The rest, by hand.** I read the gold item, the answer and, where needed, the inputs and memory snapshots for each remaining loss. I split it into model error (1), a grader or rubric problem the LLM judge also has (2), or arguable or underspecified gold (3). The per-question assignments are in `classify.py` (see Reproduction).
5. I read every question that has a loss. That covers 100% of the lost points, not only the top 90%. The long tail is mostly partial list credit and citations; I classified it by pattern.

## Track A (12.5 lost)

| # | Question | Loss | Class |
|---:|---|---:|---|
| 1 | gen-s10-w2-small q-003 change | 1.52 | 3 (1.14), 1 (0.38) |
| 2 | gen-s7-w2 q-003 change | 1.14 | 2 (heuristic 0.00, LLM 0.80) |
| 3 | pilot q-014 change | 1.06 | 2 (0.58), 3 (0.27), 1 (0.20) |
| 4 | gen-s1-w1 q-001 priority | 0.58 | 2 (heuristic 0.49, LLM 0.97) |
| 5 | pilot q-001 status | 0.49 | 2 (0.28), 1 (0.19) |
| 6 | gen-s5-small q-003 change | 0.45 | 2 mostly |
| 7 | gen-s2-w1 q-003 change | 0.42 | 2 (heuristic 0.63, LLM 0.94) |
| 8 | gen-s9-large q-003 change | 0.40 | 2 (0.25), 1 (0.13) |
| 9 | gen-s5-small q-002 status | 0.39 | 1: the next step is missing |
| 10 | pilot q-008 brief | 0.38 | 2 (heuristic 0.68, LLM 0.95) |
| 11 | gen-s2-w1 q-011 brief | 0.38 | 3: the inputs never state the gold role |
| 12 | gen-s3-w1 q-003 change | 0.36 | 2 mostly |
| 13 | gen-s7-w2 q-011 brief | 0.36 | 1: five shared projects are missing |
| 14–20 | change and brief answers in gen-s4-w2, gen-s3-w1, gen-s8-w4, gen-s6-w1 and gen-s1-w1 | 1.9 | mixed |
| 21 | pilot q-004 i_owe | 0.23 | 2 (heuristic 0, LLM 0.94) |
| 22 | pilot q-007 owed_to_me | 0.23 | 1 |
| rest | partial list credit, priority distractors, citations | ~2.6 | mostly 3 and 4 |

## Track B (27.6 lost)

| # | Question | Loss | Class |
|---:|---|---:|---|
| 1 | gen-s10-w2-small q-003 change | 1.52 | 2 (0.76), 3 (0.76) |
| 2 | gen-s5-small q-001 priority | 1.52 | 2 (heuristic 0, LLM 0.93) |
| 3 | gen-s8-w4 q-001 priority | 1.14 | 2 (heuristic 0, LLM 0.92) |
| 4 | gen-s6-w1 q-001 priority | 1.14 | 2 (heuristic 0, LLM 0.94) |
| 5 | pilot q-011 priority | 1.14 | 2 (LLM 0.70; the rest is a mislabelled distractor) |
| 6 | pilot q-014 change | 1.00 | 2, 3 and 1 |
| 7 | pilot q-008 brief | 0.95 | 2 (heuristic 0.16, LLM 0.71), 1 |
| 8 | gen-s9-large q-003 change | 0.93 | 2 (0.68), 1 (0.23) |
| 9 | gen-s7-w2 q-003 change | 0.81 | 2 mostly |
| 10 | 10 status answers that say "in build" or "in security review" but not "active" | 2.5 | 2 |
| 11 | person_attr relationship ×4 ("Colleague in my own org (SLIO)" for gold "peer") | 1.23 | 3 |
| 12 | gen-s5-small q-008 blocker: "Nothing" | 0.38 | 3 |
| 13 | gen-s5-small q-009: abstained on Rodrigo's relationship | 0.38 | 1 |
| 14 | gen-s9-large q-009: abstained on Mikayla's org | 0.16 | 3 |
| 15 | person briefs that drop "member" projects (gen-s7-w2, gen-s8-w4, gen-s6-w1, gen-s3-w1) | ~1.4 | 1 mostly |
| rest | change partial credit, lists, citations | ~9 | 2, 3 and 4 |

## Class 2: the grader misses right answers (A 5.6, B 16.0)

The LLM judge gives more credit than the heuristic on 18 Track A questions and 38 Track B questions. By question type, it recovers:

| Type | A | B |
|---|---:|---:|
| Priority ("what should I focus on tomorrow") | 0.6 | **4.7** |
| Change ("what changed on X since …") | **2.9** | **4.5** |
| Status and brief | 0.6 | **3.5** |
| List | 0.4 | 1.4 |

The patterns:

- **Explanation in the item text.** Gold for gen-s8-w4 B q-001 is "Complete the Fulmar privacy impact assessment". Opus's first item is "Finish and send the Fulmar privacy impact assessment to Goran Liu. It was due 14 Sep and no completion has been seen, so it is probably overdue." It is the right item, ranked first. The heuristic gives 0 because less than 40% of the item's words belong to the gold loop (`KEYWORD_PRECISION`). The LLM judge gives 0.92.
- **A different verb.** Gold for pilot q-004 is "Send Hyun-woo the Tinderbox security review package". Opus wrote "Pull together the Tinderbox security review package (draft exists; needs the sub-processor list before sending; draft email unsent)", with counterparty "Hyun-woo (Hugo) Park". That is exactly the worker's own wording in nt-0005. Heuristic 0, LLM 0.94.
- **One prediction for two gold events.** Gold for gen-s7-w2 A q-003 has three items: the in-house decision, "I'm handing Corrie over to Iselbury", and "I handed Corrie over to Iselbury". Opus wrote "Anastasia confirmed Corrie will be built in-house rather than bought (decision made)" and "Hiba committed to handing Corrie over to Iselbury and reported it done to Zawadi". Heuristic 0 (zero matches). LLM 0.80. The one-to-one matching still costs the third event, so I count that residual as class 2 too.
- **A literal status word.** On Track B, 10 status rubrics require "X is active". Opus wrote "Garnet … is in security review and blocked" or "Cirrus … is in security review". The heuristic wants one of the listed status synonyms; the LLM judge accepts these. This costs 2.5 points on B. On A, Opus happened to write "active" every time.
- **Reworded owed items in briefs.** For pilot B q-008, Opus wrote "You owe her a writing-feedback use-case list. She owes last year's ENGL 101/102 essay volumes" in one claim. The heuristic matches items per segment and misses both. Heuristic 0.16, LLM 0.71.
- **Hedged asks in priority lists.** Gold for gen-s5-small B q-001 is "Review Anahit's Wagtail service blueprint". Opus's second item is "Reply to Anahit about her Wagtail service blueprint review, which she wants by tomorrow (31 Mar). Do it or decline". Heuristic 0, LLM 0.93. The `ec9ff3d` hedge fix ignores "reply" and "decide", but "do it or decline" plus the explanation still pushes the item under the precision threshold.

Grader problems that the LLM judge also has (counted in class 2 by hand):

- **Wrong distractor flags.** In pilot B q-011, "Tinderbox load test at 10:00 runs without you (Saanvi + Bartosz); check the results afterwards" is counted as a distractor (Saanvi's loop). In gen-s3-w1 A q-001, "Chase Nurlan on the Sirocco SSO broker" is counted as Nurlan's loop. Both are reasonable actions for the worker, and each costs 12.5–25% of the question.
- **Padding penalty** on long briefs (pilot q-008: 0.05 on A, 0.09 on B).
- **Merged or split events** in long change lists (gen-s4-w2, gen-s6-w1, gen-s1-w1).

## Class 3: arguable or underspecified gold (A 3.0, B 5.6)

- **A suggestion written as a commitment.** Gold for gen-s10-w2-small q-003 includes "Catrin asked me to review the translation help selection vendor comparison". The source, mn-0015, is a meeting-assistant summary that says "Discussed Catrin's translation help selection vendor comparison. No owner agreed yet" and "(suggested) Aoife Everett: Review Catrin's …". The world event itself has `accepted: false, basis: inferred`. Opus reported exactly that: "a review by me was suggested but no owner agreed (not accepted)". The LLM judge also says NO, because the gold summary claims an ask that never happened. This costs 1.14 on A and 0.76 on B. On A, Opus also missed the second item: it filed Amani's Noris accessibility report under the Noris diligence project, because ch-0041 does not name a project. I count that as a model error.
- **"I'll try, no promises" counts as owed.** gen-s2-w1 c-064 comes from "I'll try to send Yaell the Mistral retention schedule, no promises", and gold calls it an accepted commitment. Opus listed it as tentative or left it out. gen-s1-w1 e-0199 is "(suggested) Camila: Send Jalen the Marten retention schedule" (`accepted: false`), but the gold change summary reads "I promised Jalen …". Under [contract rule 7](../../contract/CONTRACT.md), Opus's reading is defensible. One case goes against Opus: in gen-s6-w1, "try to send Nathaniel the Axolotl stakeholder map (soft)" is in the worker's own notes, which rule 7 counts as taking it on.
- **Unanswered asks counted as accepted.** gen-s6-w1 c-077 rests only on Andres's "can you send me the Fennel rollout checklist by Wednesday?", with no reply, yet gold says "I promised Andres …". The same holds for gen-s5-small c-050, where the only reply was "thanks for flagging". Opus keeps flagging these as "not yet agreed", which is fair, and the lists that leave them out lose recall.
- **Unaccepted asks in project-loop lists.** Opus includes items such as "Review the Cairn model allow-list (Theresa's ask; not yet accepted)" and labels them. Gold leaves them out, so each one lowers precision (gen-s4-w2, gen-s8-w4, gen-s10-w2-small, gen-s3-w1 and gen-s9-large q-010). Whether a "what loops are open" answer should show pending asks is a matter of taste.
- **open vs waiting.** Many `owed_to_me` items lose 1/6 of their credit because Opus says "open" and gold says "waiting" for something another person owes. The contract defines "waiting" from the owner's side, so either label works for someone else's loop. This costs 0.2 on A and 0.6 on B.
- **Facts the inputs never give.** For gen-s2-w1 q-011, gold says "Imani Quaye is Account Executive at Torthen Civic". Her only appearance is ch-0081, a DM signed "Imani (@imaniq)" that mentions Torthen Civic; no input states her role. On Track B, Opus correctly answered "Her role and org are unknown". For gen-s9-large q-009 (Track B only), the inputs never say which organization Mikayla Babic is with. Track A's oracle seed store does say, so Opus answered it on A.
- **A blocker the owner said was gone.** For gen-s5-small B q-008, "What is currently blocking Wagtail?", gold is "real patient data paused pending the security review". At the 25 March standup (mt-0011), Hiba asked "Any blockers there?" and the owner, Isla, said "Not right now, no." Opus answered "Nothing". The world never logs the pause being lifted, but the most recent statement from the owner supports Opus.
- **Relationship vocabulary that Track B never sees.** Four Track B `person_attr` questions want one label from the contract's list (`peer`, `stakeholder`, …). Track B agents never get the contract, and the query prompt only says "put only the answer in `value`". Opus answered "Colleague in my own org (SLIO)" for `peer`, and "External collaborator: Eleni Fontaine (Lena), Revenue Cycle Analyst at Ketford" for `stakeholder`. All four score 0. On Track A, Opus used the contract labels and got all four right. This costs 1.23 points on B and is a benchmark specification gap.

## Class 1: Opus's own errors (A 2.3, B 2.8)

- **Completed loop listed instead of the open one.** For pilot A q-007, "What does Sol owe me?", Opus answered "Schedule the panel interview for Mateus (done; panel held 1 March)" instead of "Collect two references for Mateus". The cause is ingestion. Opus's store had `loops/run-reference-checks-for-mateus` with counterparty Sade instead of the worker, so the loop did not count as owed to the worker. On Track B, Opus got it right; the heuristic gives 0 because Opus wrote "Mats Okonedo", but the LLM judge gives 1.0.
- **Briefs leave out minor shared projects.** gen-s7-w2 q-011 (Bolat) lists 5 of 11 shared projects and leaves out the Garnet login loop. gen-s8-w4, gen-s4-w2 and gen-s1-w1 each leave out one membership. Gold counts every project where the person is a member, and Opus listed the ones with active threads.
- **Status answers leave out a rubric item.** gen-s5-small A q-002 does not give the next step, "run the go-live checklist with Falbury". Opus's Track B answer has it. pilot A q-001 does not say the ARB rejection of spec v1 is a blocker; it only mentions the rejection as context for spec v2.
- **Abstained although memory had the fact.** For gen-s5-small B q-009, Opus abstained on its relationship with Rodrigo Okada, although its memory lists him as "Chief Medical Information Officer, Falbury". Gold is "executive".
- **Change items under the wrong project** (gen-s9-large: Kasane sandbox access), and real omissions in the 19-item pilot q-014 answer: Greta's runbook, the risk-register ask and the dashboard lines.

## Class 4: citation penalties (A 1.5, B 3.2)

A citation penalty is the `(0.75 + 0.25c)` multiplier. Most of it is not Opus citing irrelevant sources.

| Penalized cite | A | B | Reading |
|---|---:|---:|---|
| An artifact about the question's project or person, outside the gold support set | 0.67 | 1.75 | Support-set limit |
| An artifact that reveals no world event (calendar invites, unsent drafts such as em-0031) | 0.48 | 0.63 | Mostly a support-set limit: Opus cites the draft to show the package was not sent |
| A store record whose evidence is outside the support (A only) | 0.24 | – | Comes from content beyond gold, such as unaccepted asks in a brief |
| An artifact about a different subject | 0.11 | 0.53 | Mostly genuine. Some are support-set limits, for example ch-0012 ("Tinderbox tenant live"), which is tagged to the Kettleyard project |
| An unrecognized format (`commitments.md#A20`) | – | 0.28 | Genuine: Track B answers must cite artifact IDs |

Roughly 75–80% of the citation penalty is support-set limits. About 0.1–0.2 points on A and 0.5–0.8 on B are genuinely wrong or badly formatted cites.

## Track B vs Track A

The heuristic gap is 15.1 points; the LLM-judge gap is 5.0. So about 10 points of the difference come from how the heuristic treats Track B's answer style. Track B answers are longer and explain more: hedged focus items, statuses without "active", long brief claims.

The 5 points that remain:

- **About 1.7 more citation penalty.** Track B can cite only artifacts. It cites more artifacts outside the support set and sometimes cites its own files by mistake.
- **About 1.2 from relationship labels**, the specification gap above.
- **About 0.5 from Track A's oracle seed store.** That store supplies facts the Track B inputs never state: Mikayla's org, and the Wagtail blocker that the owner later called "none".
- **The rest is answering choices, not lost memory.** I searched Track B's memory files for every list item it missed. The Nettle data dictionary, the two-week sprint, the workshop slides v2, the Fulmar dependency list, the Ithic deep-dive materials and the readout were all in memory. Opus labelled several as "not agreed" or "no reply seen" and left them out of the answer, or put them under the wrong person.

Ingestion is not the main issue on Track A either. The agent store scores 87.5 and the oracle store 93.1 with the heuristic, a 5.6-point ingestion cost. With the LLM judge they score 89.9 and 94.8, a 4.9-point cost. Even with the oracle store, Opus loses 6.9 heuristic points: 1.5 to citations and 2.5 that the LLM judge recovers. Most of the rest is pilot q-014, the 19-item change question.

## Reproduction

Scratch scripts are in `.amp/in/orb-backup/opus_audit/`, outside the tracked tree:

- `dump.py`: re-scores with grader details; add `--llm` to read the LLM caches.
- `prefetch.py`: parallel LLM-judge cache fill.
- `split.py`, `classify.py`: class totals.
- `cites.py`, `cite_rel.py`: citation analysis.
- `rubrics.py`, `unmatched.py`, `attr.py`: per-question diagnostics.

The LLM-judge caches (2,999 decisions for A, 1,385 for B) and the Track B LLM-judge report are saved there too, so the LLM scores can be reproduced without new calls. The command was:

```
wcb score <run>/track-b/measured --suite lite --judge llm --judge-model anthropic:claude-opus-5-5
```
