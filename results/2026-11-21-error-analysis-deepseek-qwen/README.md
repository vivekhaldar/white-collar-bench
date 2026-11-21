# Error analysis: DeepSeek V4.1 Flash and Qwen3.8-27B (Pi harness)

What the two committed runs got wrong, where their points went, and which losses are model errors and which are grader limitations. No new model runs: this re-analyzes the committed score reports.

- [DeepSeek V4.1 Flash 1017 / Pi](../2026-11-11-deepseek-v4.1-flash-1017-pi/README.md): Track A 84.6, Track B 67.5 (benchmark `c623e77`, gold v4).
- [Qwen3.8-27B / Pi](../2026-11-11-qwen3.8-27b-pi/README.md): Track A 72.3, Track B 55.0 (benchmark `b66134a`, gold v3, older scorer).

All worlds, people and organizations named here are synthetic.

## Summary

- **DeepSeek is usually partly right.** It loses 15.4 points on Track A and 32.5 on B, mostly as partial credit: 32 zero-scored answers on A and 102 on B. Its biggest losses are change questions ("what changed on X since …"), list answers that include suggestions nobody accepted, and four ingestion days that hit the turn budget and were rolled back. Its errors grow later in the episode on both tracks.
- **Qwen fails outright more often.** It loses 27.7 on A and 45.0 on B, with 92 and 235 zero-scored answers. Its losses come from failed sessions (output cap, validator timeouts, a turn-limited seed ingestion), from owners not updated after handoffs, and from verbose answers that a strict grader zeroes. Its status scores are low even on the oracle store, which points to the older scorer more than to the model.
- **The difference between the models is mostly memory.** On questions whose gold is identical in both gold versions, the oracle-store scores are close (0.941 vs 0.929), but answers from the agents' own stores differ by 0.07 on A and 0.16 on B.
- **Both lose about 17 points from Track A to B**, but differently. DeepSeek loses it on synthesized answers (status, change, briefs) and citation quality on B. Qwen loses it almost entirely as extra zero scores (+13.5 points).
- **Both models share several hard cases.** The pilot world after its owner and date changes, the phase of a just-created project (both abstain), the owner of a commitment after a handoff, and change questions.

## Method

Each question gets the weight it has in the headline: one over the questions in its bucket at that checkpoint, over the buckets at that checkpoint, over the world's checkpoints, over the worlds ([scoring](../../docs/scoring.md#answers-and-aggregation)). Losses weighted this way are in **WCB points** and add up exactly to 100 minus the score. The reconstruction matches all six headlines (agent and oracle stores) to within 0.0002.

Each run is analyzed against the gold of its own benchmark revision, rebuilt from that revision. The script is [`error_analysis.py`](error_analysis.py); its docstring has the commands to reproduce the output.

Every loss is put in exactly one of these components:

| Component | Meaning |
|---|---|
| Invalid | The answer was missing or failed validation |
| Wrong abstention | Abstained on an answerable question |
| Answered unanswerable | Gave an answer where abstaining was correct |
| Base zero | Answered, and the answer scored 0 before citations |
| Base partial | Answered, and the answer scored between 0 and 1 before citations |
| Citation penalty | The `(0.75 + 0.25c)` multiplier on otherwise earned credit |

The raw answers are not in the repository, only the score rows. Concrete examples therefore come from each report's 10 worst answers (`failures[]`) and from the audit documents committed with each run. Only cases those documents audited are called grader limitations; "likely" marks an inference from score rows.

## 1. Where the points go

### By component (WCB points lost; affected questions in brackets)

| Arm | Lost | Invalid | Wrong abstention | Answered unanswerable | Base zero | Base partial | Citation penalty |
|---|---:|---:|---:|---:|---:|---:|---:|
| DeepSeek A | 15.36 | 0 | 0.19 (3) | 0.24 (2) | 2.34 (27) | **10.12 (204)** | 2.47 (338) |
| DeepSeek A, oracle store | 9.21 | 0 | 0 | 0.05 (1) | 1.20 (7) | 6.51 (151) | 1.45 (213) |
| DeepSeek B | 32.52 | 0 | 0.68 (10) | 0.09 (2) | **10.67 (90)** | **16.08 (260)** | 5.00 (433) |
| Qwen A | 27.66 | 0.76 (15) | 1.17 (9) | 0.05 (1) | **9.18 (67)** | **14.21 (220)** | 2.30 (233) |
| Qwen A, oracle store | 15.73 | 0 | 0 | 0.05 (1) | 2.45 (18) | 11.36 (185) | 1.87 (183) |
| Qwen B | 45.00 | 0 | 1.91 (39) | 0.71 (5) | **22.66 (191)** | 15.33 (220) | 4.39 (318) |

| Arm (745 questions each) | Full credit | Zero | Mean citation precision |
|---|---:|---:|---:|
| DeepSeek A | 327 | 32 | 0.855 |
| DeepSeek B | 176 | 102 | 0.637 |
| Qwen A | 357 | 92 | 0.830 |
| Qwen B | 150 | 235 | 0.581 |

- Citation penalties touch many answers but cost only 2–5 points.
- Qwen's 15 invalid answers are one checkpoint: gen-s8-w4 cp3 wrote no answers after hitting the 32k output cap.
- 30 of Qwen B's 39 wrong abstentions are in gen-s8-w4, whose seed ingestion hit the turn limit and was rolled back.
- Only one unanswerable question fools every arm, including both oracle-store arms: gen-s8-w4 cp9 q-135 (person_attr). Its gold may deserve a look.

### By question type (mean score / WCB points lost)

| Bucket | DeepSeek A | DeepSeek A oracle | DeepSeek B | Qwen A | Qwen A oracle | Qwen B |
|---|---|---:|---|---|---:|---|
| change | **.548 / 5.61** | .733 | **.243 / 9.06** | .499 / 6.03 | .723 | .345 / 8.16 |
| list | .808 / 2.40 | .900 | .581 / 5.22 | .687 / 3.59 | .872 | .397 / 7.29 |
| brief | .827 / 2.11 | .908 | .598 / 4.79 | .711 / 4.04 | .812 | .356 / 7.20 |
| priority | .850 / 1.88 | .947 | .693 / 3.62 | .663 / 4.02 | .949 | .464 / 6.16 |
| status | .867 / 1.53 | .821 | .599 / 5.12 | **.388 / 7.29** | **.438** | .339 / 7.94 |
| point | .875 / 1.35 | .959 | .727 / 3.31 | .838 / 2.00 | .946 | .467 / 6.33 |
| temporal | .977 / 0.24 | .985 | .884 / 1.29 | .931 / 0.56 | .997 | .883 / 1.23 |
| unanswerable | .974 / 0.24 | .987 | .974 / 0.09 | .961 / 0.14 | .987 | .934 / 0.71 |

Within point questions, `project_attr` (122 questions) loses the most for both models. For DeepSeek A it costs 1.02 points, with 11 zero scores, mostly "what is blocking X" and "what phase is X in" answers worded differently from gold. Temporal questions (`event_date`, `decision_date`, `loop_due`) are nearly solved by both models.

### By planted challenge

Questions carry several challenge tags, so these losses overlap and do not add up.

| Challenge | n | DeepSeek A | DeepSeek B | Qwen A | Qwen B |
|---|---:|---:|---:|---:|---:|
| duplicate_signal | 211 | 4.96 | 12.00 | 11.52 | 16.31 |
| implied_commitment | 130 | 4.04 | 9.72 | 10.59 | 14.57 |
| alias | 161 | 4.25 | 8.61 | 7.63 | 12.38 |
| supersession | 113 | 3.64 | 7.98 | 10.03 | 12.58 |
| new_entity | 130 | 4.03 | 7.77 | 8.13 | 12.10 |
| endorsement | 127 | 3.40 | 7.36 | 6.98 | 10.56 |

The lowest mean scores are on smaller tags: silent_closure (14 questions; DeepSeek A .756, B .414), restructuring (67; DeepSeek A .753, B .529), correction (56; DeepSeek B .560, Qwen A .528) and reversal (12; Qwen A .461).

### By world and by position in the episode

The pilot is the worst world in every arm: mean question score DeepSeek A .685, B .373; Qwen A .394, B .234. It accounts for 3.0 of DeepSeek A's 15.4 points lost. The lowest checkpoints:

- DeepSeek A: pilot cp3 61.9, pilot cp2 67.7, gen-s8-w4 cp7 71.6.
- DeepSeek B: pilot cp2 28.1, pilot cp3 50.6, gen-s7-w2 cp6 52.3. All three follow rolled-back ingestion days.
- Qwen A: gen-s8-w4 cp3 0.0 (no answers), pilot cp3 32.7, pilot cp1 47.2.
- Qwen B: gen-s8-w4 cp2 19.9, pilot cp3 24.8.

Mean question score by where the checkpoint falls in its episode:

| Position | DeepSeek A | DeepSeek B | Qwen A | Qwen B |
|---|---:|---:|---:|---:|
| First third | .882 | .720 | .729 | .483 |
| Middle third | .844 | .664 | .767 | .546 |
| Last third | .835 | .660 | .744 | .518 |

DeepSeek's errors compound over the episode on both tracks. Qwen has no clean trend, because its worst failures (pilot, gen-s8-w4) hit early checkpoints.

## 2. Track A: ingestion loss vs synthesis loss

"Ingestion" is the oracle-store score minus the agent-store score on the same question; "synthesis" is the oracle store's own shortfall from 1. Both are in WCB points.

| Template | DeepSeek ingestion | DeepSeek synthesis | Qwen ingestion | Qwen synthesis |
|---|---:|---:|---:|---:|
| project_changes | **2.16** | **3.45** | 2.55 | 3.47 |
| focus_tomorrow | 1.27 | 0.61 | **3.46** | 0.56 |
| person_brief | 1.01 | 1.10 | 1.68 | 2.36 |
| project_attr | 0.80 | 0.22 | 0.64 | 0.19 |
| project_loops | 0.41 | 0.74 | 0.75 | 0.65 |
| i_owe | 0.37 | 0.42 | 0.64 | 0.65 |
| owed_to_me | 0.27 | 0.18 | 0.64 | 0.27 |
| project_status | −0.55 | 2.08 | 0.45 | **6.84** |
| **All templates** | **6.15** | **9.21** | **11.93** | **15.73** |

- **Prioritization and point questions depend most on ingestion.** With a perfect store they score .95–.96, so their losses come from the agent's own store.
- **Change questions fail even with a perfect store** (DeepSeek .733 on the oracle store). That is partly synthesis and partly the change matcher (section 4).
- **Qwen's status questions score .438 on the oracle store**, mostly an artifact of the older scorer's rubric focus threshold (section 4).
- **Challenge tags with the largest ingestion cost.** DeepSeek: duplicate_signal and unobservable (1.50 each), alias 1.33, implied_commitment 1.32, new_entity 1.29, scattered_evidence 1.24. Relative to their size, silent_closure (agent .756 vs oracle .955) and restructuring (.753 vs .871) are hit hardest. Qwen: implied_commitment 4.80, duplicate_signal 4.28, unobservable 2.73.
- **Largest single drops (agent 0, oracle 1):**
  - DeepSeek: pilot cp3 q-033 and q-034 (Tinderbox owner and go-live date, after the rolled-back March 5 day), pilot cp3 q-047, pilot cp2 q-018, gen-s8-w4 cp5 q-069 and cp8 q-112 (owner after a handoff), gen-s8-w4 cp7 q-095 and q-099, gen-s7-w2 cp6 q-088, gen-s5-small cp1 q-008.
  - Qwen: 14 of the 15 largest drops are in the pilot, including cp1 q-004, q-006, q-007 and q-013, and most of cp3 (q-033 to q-052).

## 3. The Track A to B gap

Weights are the same on both tracks, so the gap splits exactly.

| | DeepSeek (17.16) | Qwen (17.35) |
|---|---|---|
| By bucket | status 3.59, change 3.45, list 2.82, brief 2.68, point 1.97, priority 1.74, temporal 1.05, unanswerable −0.14 | point 4.33, list 3.69, brief 3.16, priority 2.14, change 2.13, temporal 0.68, status 0.65, unanswerable 0.57 |
| By component | base zero +8.32, base partial +5.96, citation +2.53, wrong abstention +0.49 | base zero +13.49, citation +2.09, base partial +1.13, wrong abstention +0.74 |
| By challenge | duplicate_signal 7.04, implied_commitment 5.68, alias 4.37, supersession 4.35, endorsement 3.96 | duplicate_signal 4.79, alias 4.75, implied_commitment 3.98, new_entity 3.97, endorsement 3.58 |

DeepSeek's gap is in synthesized answers and citations: on B it writes long, cautious answers that the heuristic grader matches poorly, and its citation precision falls from 0.86 to 0.64. Qwen's gap is almost all extra zero scores: wrong owners, abstentions in gen-s8-w4, and wordy point values.

## 4. Failure modes, ranked

### DeepSeek

1. **Change questions** (5.6 points on A, 9.1 on B; 7 zero scores on A, 21 on B, 3 even on the oracle store). These mix events it really left out with a known weakness of the matcher.
   - Likely grader limit: A gen-s10-w2-small cp4 q-036 ("Akosua Bergstrom said she would send me the Pipit action log…") matched nothing against gold event e-0192 ("Akosua owes Aoife the Pipit action log"). A gen-s4-w2 cp3 q-033 (Bruna's fix to the Cairn deep links) likewise matched nothing against e-0238.
   - Audited grader limit, not full credit either: B gen-s10-w2-small cp1 q-003 describes two real events inside long caveats. Keyword precision is 0.22 and 0.17 against a 0.4 threshold, and the answer also speculates ([answer audit](../2026-11-11-deepseek-v4.1-flash-1017-pi/ANSWER-AUDIT.md)).
2. **Lists suggestions nobody accepted as commitments** (a model error). A gen-s10-w2-small cp1 q-004 earns only 2/3 base credit (final 0.6), and q-010 0.796. B gen-s10-w2-small cp2 q-019 lists 8 items and matches none; cp3 q-029 lists 4 and matches none. B also turns a calendar booking into a hard due date.
3. **Ingestion days rolled back after hitting the turn budget** (4 sessions: pilot day 4 on B, pilot day 5 on A and B, gen-s7-w2 day 11 on B). The sessions did the work but kept reconciling and validating until the 120-turn cap, and the rollback discarded the day. Pilot A cp3 then answers Mara and 2027-03-29 where gold is Yusra and 2027-04-05. Pilot B cp2 q-018 answers with an empty list. B gen-s7-w2 cp6 q-080 misses a questionnaire introduced on the lost day ([failure traces](../2026-11-11-deepseek-v4.1-flash-1017-pi/FAILURE-TRACES.md)).
4. **Leaves stored decisions out of status answers.** gen-s10-w2-small cp1 q-002 omits the "approach A" test-plan decision on both tracks (A 0.784, B 0.594), although the query session read the record that holds it. This is answer selection, not memory.
5. **Point answers worded differently from gold.**
   - A gen-s10-w2-small cp6 q-065: "Unsigned Holworth data-sharing agreement and process-map access approval" against gold "unsigned data-sharing agreement with Holworth". The extra clause scores 0; likely grader strictness.
   - A gen-s5-small cp1 q-008: "Security review" against "real patient data paused pending the security review"; too terse.
   - A gen-s7-w2 cp2 q-021 answers "None" where gold names a blocker. A gen-s7-w2 cp6 q-085 answers "merged" where gold is "placeholder".
   - B gen-s10-w2-small cp1 q-009 answers "Akosua Bergstrom (colleague; Programs Manager, FDO)" where gold is "peer".
6. **Owner not updated after a handoff on B.** gen-s1-w1 cp2 q-028 answers Yasmin, not Nadia, though its note quotes the handoff; gen-s10-w2-small cp5 q-052 answers Akosua Carmichael, not Jia Delacroix.
7. **Citations** (2.5 points on A, 5.0 on B). Some are protocol errors, such as citing `people/me` or generic files. Some are limits of the closed support set: a real calendar invite (`ca-0002`) and a real checklist confirmation (`mn-0017`) supporting gen-s10-w2-small cp1 answers were marked invalid ([answer audit](../2026-11-11-deepseek-v4.1-flash-1017-pi/ANSWER-AUDIT.md)).
8. **Abstention is well calibrated.** It answers two unanswerable questions (gen-s1-w1 cp3 q-045, "Office of Civic Technology"; gen-s8-w4 cp9 q-135) and wrongly abstains on 3 answerable ones on A and 10 on B.

### Qwen

1. **Failed sessions.**
   - A gen-s8-w4 cp3 wrote no answers after hitting the 32k output cap: 15 questions, 0.76 points.
   - Two ingestion sessions (pilot March 6, gen-s8-w4 September 22) timed out inside validators the model wrote itself.
   - An output-cap truncation on gen-s7-w2 July 5 lost the original decision, so cp6 q-082 abstains.
   - B gen-s8-w4's seed ingestion hit the turn limit and was rolled back: 30 wrong abstentions, world score 42.6.
2. **Status questions score .388 on A and only .438 on the oracle store.** This is mostly the older scorer's rubric focus threshold: the [Qwen report](../2026-11-11-qwen3.8-27b-pi/README.md) records 45 Track B rubric answers zeroed by the 0.5 threshold, such as B gen-s1-w1 cp3 q-038, where four keyword groups matched at focus 0.48.
3. **Owner not updated after a handoff, by three different mechanisms** (traced in the Qwen report and `evidence/pi-traces.json`):
   - Lanmoor (gen-s3-w1 cp2 q-027): the handoff was never written to memory.
   - Mistral (gen-s2-w1 cp2 q-027): memory was right, and the query still answered Dina.
   - Fulmar (gen-s8-w4 cp8 q-118): misread the transfer as a change of recipient.
   - More cases: B gen-s1-w1 cp2 q-028, gen-s8-w4 q-112, gen-s10-w2-small q-052, and A gen-s10-w2-small cp3 q-032, which answers "Aoife Everett (people/me)" where gold is Gaurav Laine.
4. **Verbose point values zeroed by the strict grader** (grader false negatives). The Qwen report verified 9 on A (such as pilot cp1 q-012 and gen-s3-w1 cp1 q-009; +0.76 points if credited) and 3 on B (+0.34):
   - gen-s1-w1 cp3 q-036: "Complete — …" where gold is "closed".
   - q-040: the right date, but parsed from the wrong place in the answer.
   - q-041: no date was parsed at all.

   The report lists 66 more unverified candidates on B. The current scorer handles several of these patterns: the leading date is read first.
5. **Prioritization and obligation lists from its own store.** focus_tomorrow loses 3.46 points to ingestion alone. A gen-s10-w2-small cp4 q-034 and cp6 q-056 have recall 0: the must-include items are missing.
6. **Change and brief answers.** A gen-s10-w2-small cp2 q-014 describes the project split correctly and matches nothing. The brief rubrics for A gen-s2-w1 cp1 q-011 and gen-s10-w2-small cp5 q-050 come back all "missing". Likely partly heuristic-grader limits.

## 5. DeepSeek vs Qwen on comparable questions

Only questions whose text, gold and support are identical in gold v3 and v4 are compared: 521 of 745 (509 for Track A agent stores, excluding Qwen's missing checkpoint). The scorers still differ (about 720 changed lines in `wcb/grade/answers.py` and `judge.py` between the revisions), so list, change and text-point comparisons are approximate.

| Arm | Questions | DeepSeek mean | Qwen mean | Both < .5 | DeepSeek only < .5 | Qwen only < .5 |
|---|---:|---:|---:|---:|---:|---:|
| A, agent store | 509 | .872 | .806 | 26 | 12 | 52 |
| A, oracle store | 521 | .941 | .929 | 4 | 3 | 13 |
| B | 521 | .721 | .558 | 93 | 24 | 127 |

**Shared weaknesses** (both score 0):

- The pilot after its state changes: A pilot cp3 q-033 and q-034 (Tinderbox owner and go-live date), cp2 q-018, cp3 q-047.
- The phase of a newly created project: gen-s10-w2-small cp2 q-017 and gen-s9-large cp3 q-042. Both models abstain on A.
- The owner after a handoff: A gen-s8-w4 cp5 q-069; B gen-s1-w1 cp2 q-028 (both answer Yasmin, not Nadia).
- Change questions: A gen-s4-w2 cp3 q-033; B gen-s10-w2-small cp1 q-003.
- Prioritization: gen-s7-w2 cp4 q-046.

**Where Qwen is specifically weaker**:

| Template | Qwen | DeepSeek | Note |
|---|---:|---:|---|
| person_attr | .728 | .962 | Wordy values; still .749 vs .977 on the oracle store |
| focus_tomorrow | .677 | .848 | |
| i_owe | .688 | .830 | |
| owed_to_me | .751 | .872 | |

By challenge, Qwen also trails on implied_commitment (.663 vs .826), correction (.702 vs .858) and name_collision (.697 vs .859), and on B on restructuring (.330 vs .607) and new_entity (.401 vs .659).

**Where DeepSeek is specifically weaker**: project_attr (A .770 vs .826; oracle .930 vs .996), and the precision of its lists, which include suggestions nobody accepted (most of its 204 partial list and brief answers on A).

## Implications

- **For the harness.** Two of the costliest failure modes are operational, not cognitive: turn-budget rollbacks (DeepSeek) and output caps and validator timeouts (Qwen). A harness that writes and finishes early, exposes its remaining budget, and keeps partial state would recover points with either model ([DeepSeek recommendations](../2026-11-11-deepseek-v4.1-flash-1017-pi/README.md#issues-and-recommendations-before-another-run)).
- **For the models.** The shared cognitive weaknesses are tracking commitment acceptance (suggested vs agreed), state changes after handoffs and restructurings, and selecting what changed.
- **For the benchmark.**
  - The change matcher under-credits long event descriptions, and the closed support set rejects some genuine evidence. Both are documented in the DeepSeek report's recommendations.
  - gen-s8-w4 cp9 q-135 is answered by every arm, including both oracle-store arms, which suggests a gold or question problem.
  - Every late-episode rollback here would be invisible to the [reduced suites](../../docs/lite.md), which stop after day 2.

## Caveats

- **Not a controlled comparison.** The gold version (v3 vs v4), scorer code, prompts, document tooling and output budgets differ between the runs (Qwen's Track A used a 32k output cap).
- **The ingestion/synthesis split is diagnostic, not causal.** The oracle query is a separate stochastic session: DeepSeek's status questions score 0.55 points better on its own store than on the oracle store.
- **One repeat of the public worlds per run.** Small categories are noisy (9 comparable change questions, 5 comparable briefs).
- **No regrading.** Only the committed audits establish grader limitations; everything else called a grader limit here is marked "likely".
