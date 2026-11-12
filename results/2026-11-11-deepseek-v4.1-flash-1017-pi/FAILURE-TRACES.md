# Why four productive ingestions failed

All four turn-budget failures made substantial updates but failed to stop after processing the inputs. The model kept synchronizing duplicated memory, repairing its own edits and performing marginal checks until 120 assistant turns. The last tool calls completed; this is not evidence of half-written final files. The runner then rolled the entire day back, discarding useful work along with any unfinished consistency changes.

These source-grounded traces do **not** establish the counterfactual score under a larger cap or retained partial store. Original failed sessions remain in the reported evaluation. All world content is synthetic. Paths are relative to `runs/pi-deepseek-v41-flash-1017/`; line references name JSONL lines in each session's `stdout.log`.

## A pilot, March 5: repeated validation after essential updates

Session: `track-a/shards/pilot/pilot/r1/sessions/2027-03-05.ingest`.

1. Lines 10–76 read contract, manifest and new email/chat/meeting/note artifacts. From line 87 it reads affected existing records.
2. Line 261 starts a large successful write batch creating new loops/projects. It incorporates the four-course Tinderbox scope, April 5 go-live, Yusra's ownership, revised dependencies, vendor-scorecard correction and workshop/community follow-ups.
3. Lines 960–980 repair an agent-created YAML syntax error: an unquoted evidence note contains another colon. Line 977 quotes it. This is self-repair, not an input or harness blocker.
4. Lines 985–988 run a broad validator reporting 18 errors on 201 records. Its “privacy possible” matches include prose about an API-key rotation incident; terminology matches are not proof of a literal secret.
5. Lines 1056–1060 report **“diff check ok”** and **“semantic checks done.”** Lines 1076–1079 report **“artifacts 16 missing []”** and **“bullets 16.”** It also searches outside the working store for a benchmark validator (1067), finding none.
6. Instead of concluding, it edits the workshop current-state paragraph again at 1086–1087. The replacement succeeds, but the session reaches the turn limit.

**Durable consequence:** March 5's official snapshot is restored to March 4. `projects/tinderbox.md` still gives the old owner and March 29 go-live. At pilot cp3, A q-033 answers **Mara Ilves** for current owner, q-034 answers **2027-03-29** for go-live; oracle gives **Yusra Haddad** and **2027-04-05**. These stale answers are consistent with discarded March 5 updates. No discarded-store counterfactual was graded.

## B pilot, March 4: synchronization fan-out and a silent replacement miss

Session: `track-b/shards/pilot/pilot/r1/sessions/2027-03-04.ingest`.

1. Lines 10–64 read goals, existing overviews and new artifacts. Lines 299–300 successfully write a 21-artifact daily log.
2. Lines 317–318 pass `edits` as a string rather than an array; the tool rejects it, and line 325 corrects the call.
3. From line 333 it updates decisions, commitments, risks, open questions, timeline, projects, people and overviews. Exact-text edits misfire at 428, 566 and 651, forcing rereads/repairs. By 797–803 the tracked diff spans 19 files plus new daily-log/advising-project files.
4. Late work clarifies an architecture tenant ID versus operational gateway-route name across Kettleyard, Tinderbox, risks and open questions (1185–1212).
5. Line 1219 runs a Python `str.replace` intended to propagate wording to both `CURRENT_STATE.md` and Tinderbox. Output at 1222 confirms the change in Tinderbox, not the overview. It then spends final turns searching the overview for nonexistent text.

Decisive final searches at 1239 and 1248 return no matches (exit 1):

```sh
grep -n 'courses and running' CURRENT_STATE.md && sed -n '45,55p' CURRENT_STATE.md
grep -n 'shared Kettleyard tenant' CURRENT_STATE.md
```

**Failure mode:** useful ingestion followed by unfinished consistency repair after an unchecked no-op replacement. Many prose mirrors increase synchronization cost; exact-match assumptions add churn.

**Durable consequence:** no March 4 daily log survives, and the snapshot retains March 3. At cp2 q-018, “What do I currently owe Ilya Marchetti?”, B returns an empty list and explicitly says no commitment is recorded **“as of 3 Mar.”** Gold expects the new v4 follow-up sync with Ilya and Bettina, supported by `em-0036`; oracle includes it. A is not a clean successful control: it lists a different review and excludes the invite as unaccepted.

## B pilot, March 5: recovery from March 3 discarded again

Session: `track-b/shards/pilot/pilot/r1/sessions/2027-03-05.ingest`.

1. Lines 10–170 read March 5 inputs and discover memory is still through March 3. Lines 171–198 inspect local history; its conclusion is **“So no 3/4 data. We'll work from 3/3 state plus 3/5 inputs.”** This is a downstream rollback effect, not a replay of the missing day.
2. Line 199 writes March 5's daily log; from 226 it updates indexes, decisions, commitments, risks, questions, timeline and projects.
3. A section replacement aborts with **“missing”** (284–287); another method repairs it at 304–307. Project rewrites continue through 997, followed by people/overview work. By 1074–1078 the tracked diff covers 19 files plus the daily log and community project.
4. Lines 1158–1171 find and repair blank-line whitespace. Lines 1178–1202 repair self-created concatenated duplicate headings such as `## ARB and governance## ARB and governance` and `## Evaluation plan## Evaluation plan`.
5. More date/status/source/whitespace checks follow. Line 1286 prints overlapping `sed` ranges (1–45 and 45–90); lines 1297–1300 spend the final call checking a suspected duplicate using numbered lines. That read succeeds, but the session never concludes normally.

**Failure mode:** most late work is self-repair and final-polish checking, not unread input. The working store already contains March 5 scope, ownership, go-live and funding changes, but cannot reconstruct every March 4-only fact from the available day. Rollback discards this partial recovery too.

**Durable consequence:** March 5 memory remains March 3-based. At cp3 B q-033 gives **Sade Renwick**, with operational owner undecided; q-034 gives **March 29**; q-032 still describes the three-course pilot and old SSO blockers. Oracle gives Yusra/April 5. These are observable differences, not isolated causal score estimates.

## B gen-s7-w2, July 16: coverage passed, polishing continued

Session: `track-b/shards/gen-s7-w2/gen-s7-w2/r1/sessions/2027-07-16.ingest`.

1. Lines 10–226 read the day, including Corrie's build/buy reversal, Iselbury's merge, new questionnaire work and completions. Lines 237–246 write timeline/source indexes.
2. Lines 257–260 encounter unavailable `awk`; line 267 immediately switches to Python. This is a real runtime limitation, but it recovered and is not the terminal blocker.
3. From 287 it updates MEMORY, projects, commitments, decisions, calendar, people and questions. Editing mistakes at 514, 568 and 1025 add repair work; the latter gets a revised edit at 1032.
4. Lines 929–942 report **“unknown ids: {}”**, **“new missing from sources set()”**, no missing MEMORY-index entries and no missing timeline-table entries. Whitespace passes at 1070–1073; another diff/whitespace check ends **“OK”** at 1142–1146.
5. It nevertheless keeps adjusting historical acceptance wording, merge mentions and date caveats, and checking duplicates/status headers. The final command at 1238–1241 successfully lists project status headers. The cap is reached during checking, not an interrupted write.

**Durable consequence:** July 16's timeline is absent and Corrie remains labelled July 15, build in-house. At cp6 q-080, B lists old Torane deep-dive materials but misses Catalina's **security questionnaire due July 28**, introduced by `em-0161` on the lost day. A and oracle include it, though A's status label differs from gold. Control: q-082 asks the historical build-decision date, and B still correctly answers July 5; losing updates does not make every related answer wrong.

## Recommendations and experimental boundaries

- Give the agent a **finite completion checklist**: process all artifacts, update authoritative state, validate syntax/references, conclude. Do not invent another check after passing it.
- Surface remaining turns and reserve a finishing margin; otherwise extra “final” checks consume the entire budget.
- Keep authoritative facts in fewer places, with thin indexes, rather than reconciling many prose mirrors.
- Require replacement counts and immediate syntax validation to catch no-ops, YAML defects and heading corruption before they spread.
- Retain failed working trees as separately labelled diagnostic candidates if runner policy is extended. Do not silently promote them; traces contain valid content and self-created defects.
- Expose skipped-day coverage explicitly to later sessions, with a controlled recovery policy if desired. A fresh “as of today” header must not imply complete input coverage after rollback.
- Larger budgets or partial-state retention require a **separate experiment**. This run establishes neither their counterfactual WCB score nor that four failures would disappear under them.
