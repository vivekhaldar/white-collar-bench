# Source-grounded answer audit

This is a diagnostic sample, not an exhaustive semantic regrade. Original answers, stores and heuristic scores are preserved. All quoted world content is synthetic. Findings distinguish model mistakes, intentionally strict scoring and limitations of the benchmark's support annotations.

## Track A: gen-s10-w2-small, cp1, 31 August 2027

A read-only analysis subagent graded the completed checkpoint with the existing `score_answers`, `HeuristicJudge`, `World.load`, gold checkpoint/state and **actual agent snapshot** for store-path citations. All eleven answers are schema-valid; no grader errors. Benchmark revision: `c623e777a59830ab9bd016dac1fd3ba6896e26d2`.

Paths below use:

- W: `worlds/dev/gen-s10-w2-small`
- R: `runs/pi-deepseek-v41-flash-1017/track-a/shards/gen-s10-w2-small/gen-s10-w2-small/r1`
- S: `R/snapshots/2027-08-31`

| Question | Base | Citation | Final |
| --- | ---: | ---: | ---: |
| q-001 | 1 | 0.916666667 | 0.979166667 |
| q-002 | 0.818181818 | 0.833333333 | 0.784090909 |
| q-003 | 1 | 1 | 1 |
| q-004 | 0.666666667 | 0.6 | 0.6 |
| q-005 | 1 | 1 | 1 |
| q-006 | 1 | 1 | 1 |
| q-007 | 1 | 0.75 | 0.9375 |
| q-008 | 1 | 1 | 1 |
| q-009 | 1 | 0.666666667 | 0.916666667 |
| q-010 | 0.857142857 | 0.714285714 | 0.795918367 |
| q-011 | 1 | N/A | 1 |

The arithmetic question-mean final is 0.9103038736155619. This is **not** the type-macro checkpoint score or full-run WCB score.

### Correct: preserving tentative commitments in a change answer

**q-003:** “What changed on Translation Help Tool Selection since the end of Friday 27 August?” Base/citation/final: **1 / 1 / 1**.

Gold identifies two events: Catrin's vendor-comparison review was raised (`mn-0015`, 30 August), and the Amani accessibility-report ask (`ch-0041`, 31 August). The answer gives:

1. “Catrin's translation help selection vendor comparison was discussed at the Holworth site visit; a review was suggested with no owner agreed yet.”
2. “Amani Xu said she would send me the Noris accessibility conformance report.”

`W/inbox/2027-08-30/mn-0015.md` explicitly says “Discussed Catrin's translation help selection vendor comparison. No owner agreed yet.” The action is labelled `(suggested)`. `W/inbox/2027-08-31/ch-0041.json` says “on it, i'll send the noris accessibility conformance report,” followed by the worker's “great, thank you.”

The 30 August ingestion writes the review loop with `accepted: false` and “Suggested, not yet accepted” (`stdout.log:110`), then preserves the uncertainty in the project (`:188`). The 31 August ingestion writes the Amani report loop (`:131`). The snapshot project retains both developments (`S/projects/translation-help-tool-selection.md:26–44`). The query reads the project (`R/sessions/cp1.query/stdout.log:33`), identifies the two changes (`:66`) and writes them (`:163`). Two events match and all eight citations validate. The answer's tentative wording is more precise than the compressed gold summary.

### Wrong: suggested work included in an obligations list

**q-004:** “What do I currently owe Akosua Bergstrom?” Base/citation/final: **2/3 / 0.6 / 0.6**.

Gold contains two accepted open obligations: confirm the Nettle data dictionary and send the pantry-inventory discovery pain-point list. The answer includes both, with correct attributes, **plus**:

- “Review Akosua's pantry inventory discovery opportunity list (suggested, not yet accepted)”
- “Update the Nettle RACI chart after Akosua's comments (suggested, not yet accepted)”

It adds the disclaimer: “The first two items are accepted commitments; the other two are open but only suggested/not yet accepted.” That does not remove the extra items from its formal result list.

`W/inbox/2027-08-19/mn-0004.md` says whether the worker picks up the opportunity-list review “is still open”; `W/inbox/2027-08-26/mn-0012.md` says “No owner agreed yet” for the RACI update. Both snapshot records have `accepted: false`. The RACI record nevertheless contains an overstrong log sentence, “I'll update the Nettle RACI chart after Akosua's comments,” inconsistent with the source and its own frontmatter.

The query explicitly enumerates accepted flags (`stdout.log:67`), reads all four loop records (`:141`) and notices the prose/frontmatter inconsistency (`:140,151`). It nevertheless chooses to include suggested loops (`:151–162`, reconsidered `:191–202`). This is **not a retrieval miss**. The templates deliberately select accepted active loops (`wcb/questions/templates.py:424–446`); the main failure is query-time set selection, with a contributing store-prose inconsistency. Precision 1/2, recall 1, F1 2/3; six of ten citations validate. The substantive deduction is justified.

### Wrong: a retained project decision disappears from status synthesis

**q-002:** “What is the status of Nettle?” Base/citation/final: **9/11 / 5/6 / 0.784090909**.

The answer correctly gives active status, security-review phase, the real-client-data pause, target date 11 October, and two dated next actions. It omits the rubric's project-level decision: **use approach A for the Nettle test plan** (weight 2 of 11).

`W/inbox/2027-08-30/nt-0006.md` says “decision: use approach a for the nettle test plan.” The first ingestion creates its completed decision loop (`stdout.log:106`) and adds it to the project's current-state paragraph and log (`:185`). The following ingestion replaces the current-state paragraph with newer loop developments (`31 August stdout.log:160`), but the decision survives in `S/projects/nettle.md:70` and its own record. The query reads the full project (`cp1.query/stdout.log:33`), plans around the newer current-state paragraph (`:140`) and omits the decision from both summary and claims (`:163`; later edit `:213` does not restore it).

This is a **compression/answer-selection failure despite successful durable retention**, not lost input. The status rubric intentionally selects the latest project-level change rather than the latest individual-loop update (`templates.py:715–786`). The other six checklist entries are covered; padding penalty is zero.

There is a **separate support-coverage limitation**: the answer also correctly says the Nettle safeguarding checklist is done. `W/inbox/2027-08-31/mn-0017.md:9` explicitly confirms it, and the cited completed-loop record retains that source. Yet `mn-0017` and `loops/send-akosua-the-nettle-safeguarding-checklist` are rejected because the completed checklist is absent from this status question's facts/rubric support. This does not erase the real missing-decision error. It demonstrates a source-supported optional detail losing citation credit under a closed support set, not a bug in path resolution.

### Wrong: open status confused with accepted commitment; supplementary calendar citation rejected

**q-010:** “What loops are open on Pipit?” Base/citation/final: **6/7 / 5/7 / 0.795918367**.

Gold has three accepted loops: Sipho's SSO-broker configuration (`owed_to_me`, waiting), send Gaurav the rollout checklist (`i_owe`, open), and walk Douglas through the one-page summary (`i_owe`, open). The answer includes all three correctly, plus “Review the Pipit model allow-list,” an unaccepted suggestion.

`W/inbox/2027-08-17/mn-0002.md` says “No owner agreed yet”; `W/inbox/2027-08-18/em-0012.eml` explicitly says “Not agreed yet.” Its snapshot loop preserves `accepted: false`. The query reads this loop directly (`stdout.log:50`) and enumerates accepted metadata (`:67`), but selects nonclosed loops rather than accepted active loops (`:162,191–202`). It correctly excludes completed loops, yet includes this suggestion. Precision 3/4, recall 1, F1 6/7: another genuine set-selection error.

Four of fourteen citation instances fail. Three accompany the extraneous suggestion; the fourth is **`ca-0002` on the correctly matched Douglas walkthrough**. This real invitation has `SUMMARY:Walkthrough: Pipit one-page summary`, starts 2 September, identifies the worker and Douglas, and is retained as scheduled evidence in the snapshot loop (`:19–22,29`). `em-0057` separately contains the accepted commitment, “Leave it with me, I'll walk you through the Pipit one-page summary.” Gold supports the loop with only `em-0057`; the supplementary calendar is excluded. That citation rejection is a closed-support coverage limitation, distinct from the extra-item error and the recently fixed per-item association logic.

The same calendar citation causes q-001's only deduction. Other citation deductions have different explanations: q-007's `mt-0011` describes the earlier dependency-list thread, not the particular due date; q-009 cites `people/me`, intentionally excluded as a record citation.

### Bounded conclusions

No scorer implementation defect was established in this checkpoint. The strongest observed model errors are accepted-versus-suggested selection and failure to surface a retained decision. Two supportive sources fall outside gold support: the completed safeguarding-checklist confirmation and walkthrough calendar. These merit reporting as annotation/metric limitations, without silently adjusting official results or extrapolating their frequency to all worlds.

## Track B: matched gen-s10-w2-small cp1

The same read-only analyst independently graded the completed B answers using **B's actual snapshot**, not the A store. Here B means `runs/pi-deepseek-v41-flash-1017/track-b/shards/gen-s10-w2-small/gen-s10-w2-small/r1`, and M means `B/snapshots/2027-08-31`. All eleven answers validate; no grader errors.

| ID | B base | B citation | B final | A final |
| --- | ---: | ---: | ---: | ---: |
| q-001 | 1 | 0.75 | 0.9375 | 0.979166667 |
| q-002 | 0.626893939 | 0.791666667 | 0.594243213 | 0.784090909 |
| q-003 | 0 | 0.285714286 | 0 | 1 |
| q-004 | 1 | 1 | 1 | 0.6 |
| q-005 | 1 | 0.5 | 0.875 | 1 |
| q-006 | 1 | 1 | 1 | 1 |
| q-007 | 1 | 0.5 | 0.875 | 0.9375 |
| q-008 | 1 | 1 | 1 | 1 |
| q-009 | 0 | 0.2 | 0 | 0.916666667 |
| q-010 | 0.666666667 | 0.375 | 0.5625 | 0.795918367 |
| q-011 | 1 | N/A | 1 | 1 |

B's arithmetic question-mean is 0.7131130193985308 versus A's 0.9103038736155619. These are checkpoint-local descriptive figures, not aggregate WCB or a causal comparison of memory formats.

### Correct: Akosua obligations list excludes the proposals A included

For **q-004**, B gives exactly the two gold items, with correct attributes:

- “Send Akosua the Holworth pantry-inventory discovery pain-point list (requested 30 August; the 30 and 31 August recaps say Aoife is picking it up)”
- “Confirm the Nettle data dictionary with Akosua (requested 25 August; no response recorded)”

All four citations validate; base/citation/final are **1 / 1 / 1**. `em-0038` requests the data-dictionary confirmation; `mn-0015` and `mn-0017` affirm the pain-point work. `M/commitments.md:22–36` labels the opportunity-list and RACI work “OPEN, proposed only,” while preserving the two expected items elsewhere. August 30/31 ingestions update this register (`stdout.log:79` and `:131` respectively); the query reads it (`:32`) and Nettle (`:53`), then writes only the two relevant obligations (`:127`).

This is a correct set unlike A q-004, but not proof that B uniformly enforces acceptance: it still describes the data-dictionary item as an unresponded request and makes the opposite inclusion mistake on Pipit below.

### Wrong: the missing Nettle decision recurs after explicit storage and retrieval

For **q-002**, B reports security review, the real-client-data pause, target date, scope and many workstreams, but omits **approach A for the test plan**. The decision is redundant in free-form memory: `M/projects/nettle.md:35` says “Nettle test plan — DECIDED (approach A)”; `:65` repeats the decision; `M/decisions.md:16`, D-08, says `Use "approach A" for the Nettle test plan.` August 30 ingestion wrote both records (`stdout.log:80,95`), and the query read both (`cp1.query/stdout.log:53,116`) before omitting the decision (`:127`).

B additionally never explicitly states active status. The heuristic covers the other five checklist items: covered weight 7/11, less padding 0.009469696969696961, yielding base **0.6268939393939394**. Citation **19/24** gives final **0.5942432133838385**. Treat “security review” without “active” as strict checklist behavior, not a proven matcher defect; the missing decision is independently substantive. Rejected citations concern optional workstreams outside status support, not the reason for the omitted-decision deduction.

### Scorer limitation: caution-heavy descriptions of two real changes receive no event matches

For **q-003**, the two gold events and direct source quotes are the same as in A above. B's first two items say:

> A 30 August Holworth site-visit auto-recap mentions "Catrin's translation help selection vendor comparison" with no owner agreed, and a suggested action for Aoife to review it. This is the only mention of such a THTS vendor comparison and is uncorroborated, so it may be a recap error or a confusion with Bisi's dropped Nettle vendor comparison.

> On 31 August an "Amani" DM account said she would send the Noris accessibility conformance report; no report arrived. This may relate to the THTS accessibility-review item, but the sender's surname and the project link are not stated, so it is an inference.

Both statements describe the source events, but add long caveats; the first speculates without evidence about confusion with another project. A third item asserts no confirmed stage/requirements/vendor-selection change, which is context rather than another changed event. **This answer does not deserve automatic full credit.** Nevertheless, identifying neither of its two actual event descriptions is a verified semantic matching limitation.

With the original strings, `heuristic_same_item` accepts neither corresponding pair. `different_objects` is false for both. Gold-token containment is 0.875 and 0.8333333333, but keyword precision is only 0.21875 and 0.1724137931, and Jaccard is 0.2121212121 and 0.1666666667. The heuristic requires keyword precision ≥ 0.4, Jaccard ≥ 0.5, or its terse route; verbose caution dilutes the match. There are no accepted edges, **not** a one-prediction/two-events assignment conflict. Official base/final remain **0 / 0**, with citation 2/7.

The caution originates in ingestion: August 30 `stdout.log:112` writes “Possible vendor comparison (uncorroborated)” and the unrelated-project suspicion; August 31 `:221` adds the report with identity/project caveats. `M/projects/translation-help-tool-selection.md:43–53` retains that framing; the query reads it (`:63`) and reproduces it (`:127`). The error chain combines overcautious/speculative memory with a brittle event-identity metric. A's concise descriptions score 1.0; do not interpret B's zero as no factual event recognition.

### Wrong: unaccepted Pipit work, invented follow-up obligation and calendar-as-deadline

For **q-010**, B includes the three gold loops plus:

- “Pipit model allow-list review: no owner agreed and no evidence Aoife accepted it” (`other`, open).
- “Finalise and sign off Pipit on-call rota v3: the document says two sections are still being drafted and asks who signs off the final version and which unit hosts the shared components” (`other`, open).

`M/projects/pipit.md:21` correctly calls the allow-list “OPEN, NOT ACCEPTED” and “a proposal, not a commitment.” B recognizes that distinction but still includes it. The rota sources contain real tension: `em-0062` says the rota is done, whereas attached `dc-0002.docx` says two sections are being drafted and asks who signs off and hosts shared components. The memory preserves this and explicitly says “no Aoife action is stated” (`:26`). These unresolved document questions **do not establish a new accepted, owned finalization commitment**. Ambiguous finality is a benchmark-content caveat, not enough to call the extra item a scorer false negative.

B also assigns the Douglas walkthrough due **2027-09-02**, using its calendar booking; gold due is null. Scheduled evidence and a hard commitment deadline are deliberately separate. Ingestion retains the rota tension (`31 August stdout.log:131,171`); the query reads the register and Pipit (`:32,63`) and produces the five-item list (`:127`). SSO/rollout get full attribute credit; walkthrough gets 2/3 because its due date is wrong. Precision 0.5333333333, recall 0.8888888889, base 2/3; three of eight citations validate, final **0.5625**. The calendar is again outside the closed support set, separately from these substantive errors.

### Remaining boundary

B q-009's other zero is not adjudicated as a defect: its point `value` is “Akosua Bergstrom (colleague; Programs Manager, FDO)” where gold is `peer`; its note says “peer/colleague,” but notes are ungraded. Across the matched sample, useful free-form retention does not guarantee query-time selection, and formatting/verbosity interacts with the deterministic scorer. The audit establishes two missed event matches, not an exhaustive substance-corrected score or an aggregate error rate.
