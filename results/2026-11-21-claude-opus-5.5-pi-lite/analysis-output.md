## Headline

| Model | Track | WCB-lite | 95% CI | WCB-micro | Synthesis (lite) | SIS (lite) |
|---|---|---:|---|---:|---:|---:|
| opus | A | 87.5 | 83.2–91.2 | 86.6 | 93.1 | 99.6 |
| opus | B | 72.4 | 65.6–78.2 | 71.5 | – | – |

## Per world (WCB-lite world score)

| World | opus A | opus B |
|---|---:|---:|
| pilot | 71.1 | 49.9 |
| gen-s9-large | 94.4 | 80.1 |
| gen-s8-w4 | 93.3 | 68.1 |
| gen-s4-w2 | 91.5 | 82.0 |
| gen-s7-w2 | 82.9 | 77.9 |
| gen-s1-w1 | 88.7 | 87.6 |
| gen-s2-w1 | 89.1 | 75.0 |
| gen-s3-w1 | 88.8 | 75.6 |
| gen-s6-w1 | 95.2 | 72.3 |
| gen-s10-w2-small | 80.6 | 70.1 |
| gen-s5-small | 87.2 | 57.9 |

## By bucket (mean question score; agent store, oracle store in brackets for A)

| Bucket | opus A | opus B |
|---|---:|---:|
| point | 0.98 (0.97) | 0.77 |
| list | 0.85 (0.93) | 0.68 |
| status | 0.93 (0.98) | 0.72 |
| brief | 0.81 (0.90) | 0.66 |
| change | 0.52 (0.76) | 0.43 |
| temporal | 1.00 (1.00) | 1.00 |
| priority | 0.92 (0.91) | 0.57 |
| unanswerable | 1.00 (1.00) | 1.00 |

## Loss decomposition (WCB-lite points; questions affected)

| Model | Track | Lost | invalid | wrong_abstention | answered_unanswerable | base_zero | base_partial | citation_penalty |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| opus | A | 12.46 | 0.00 (0) | 0.00 (0) | 0.00 (0) | 3.11 (4) | 7.84 (36) | 1.51 (51) |
| opus | A oracle | 6.87 | 0.00 (0) | 0.00 (0) | 0.00 (0) | 0.00 (0) | 5.33 (25) | 1.54 (44) |
| opus | B | 27.60 | 0.00 (0) | 0.54 (2) | 0.00 (0) | 8.73 (13) | 15.13 (52) | 3.20 (77) |

## By planted challenge (mean agent score; tags overlap)

| Challenge | n | opus A | opus B |
|---|---:|---:|---:|
| alias | 36 | 0.83 | 0.64 |
| correction | 1 | 0.81 | 0.50 |
| draft_vs_sent | 1 | 0.00 | 0.00 |
| duplicate_signal | 47 | 0.90 | 0.76 |
| endorsement | 20 | 0.83 | 0.69 |
| implied_commitment | 32 | 0.79 | 0.64 |
| name_collision | 19 | 0.93 | 0.69 |
| new_entity | 5 | 0.87 | 0.70 |
| scattered_evidence | 38 | 0.87 | 0.68 |
| silent_closure | 2 | 0.70 | 0.64 |
| supersession | 23 | 0.87 | 0.64 |
| transfer | 11 | 0.86 | 0.81 |
| unobservable | 21 | 0.97 | 0.99 |
| worker_directive | 16 | 0.82 | 0.72 |

## Sessions, tokens and cost (lite; micro in the second table)


### lite

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opus | A | 33 | 0 | 0 | 365 | 0.00M | 13.76M | 2.07M | 0.43M | 21.72 | 6.43 | 21.72 |
| opus | B | 44 | 0 | 0 | 449 | 0.00M | 18.33M | 2.54M | 0.62M | 28.78 | 0.00 | 28.78 |

### micro

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| opus | A | 15 | 0 | 0 | 174 | 0.00M | 7.64M | 1.06M | 0.22M | 11.18 | 3.00 | 11.18 |
| opus | B | 20 | 0 | 0 | 209 | 0.00M | 9.43M | 1.28M | 0.31M | 14.50 | 0.00 | 14.50 |

## Lowest-scoring agent answers (lite)


### opus A: 7 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: At the Holworth site visit, Catrin's translation help selection vendor comparison was discussed; a review by me was suggested but no owner agreed (not accepted). Project otherwise unchanged: still in…
- gen-s7-w2 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Anastasia confirmed Corrie will be built in-house rather than bought (decision made); Hiba committed to handing Corrie over to Iselbury and reported it done to Zawadi
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Pull together the Tinderbox security review package (draft exists; needs the sub-processor list before sending; draft email unsent)
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: Schedule the panel interview for Mateus (done; panel held 1 March)
- pilot cp1 q-014 `project_changes` score 0.06 (base 0.07): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Hosting decided: option 2, the Kettleyard shared tenant. Option 1 (dedicated Kestrow deployment) pricing dropped.; ARB rejected interface spec v1 and wants an event-based context API. I committed to …
- pilot cp1 q-013 `i_owe` score 0.47 (base 0.50): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: One-page Council of Campus CIOs brief on chargeback (three bullets, one risk; lead with the conditional); Weekly AI & Data update (week of 1 March)
- gen-s1-w1 cp1 q-001 `focus_tomorrow` score 0.49 (base 0.50): What should I focus on tomorrow?  
  gold: Assemble the Marten security review package; Send Jalen the ranked benefits screening discovery use cases  
  predicted: Send Jalen the ranked benefits screening discovery use cases; Walk Jalen through the plain language workshop speaker brief (walkthrough scheduled 2027-11-10; due 2027-11-15); Send Thandiwe the notice…

### opus B: 25 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: At the Holworth site visit, Catrin Dang's translation help selection vendor comparison was discussed. Reviewing it was suggested for Aoife, but no owner was agreed; Amani Xu said she will send Aoife …
- gen-s10-w2-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with our programs manager?  
  gold: peer  
  predicted: Frequent 1:1 partner
- gen-s2-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Tendai Santos?  
  gold: stakeholder  
  predicted: Cross-department collaborator: the Selfell lead (Customer Service Manager, Selfell Public Works)
- gen-s3-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Lena?  
  gold: stakeholder  
  predicted: External collaborator: Eleni Fontaine (Lena), Revenue Cycle Analyst at Ketford, working with Alasdair on Okapi, Ketford Referral Triage Discovery and Sirocco
- gen-s4-w2 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Meera Bondarenko?  
  gold: peer  
  predicted: Colleague in my own org (SLIO)
- gen-s5-small cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Review Anahit's Wagtail service blueprint  
  predicted: Prepare and send Friederike (Rike) the Wagtail RACI chart — Anahit says she needs it by Thu 1 Apr, which is earlier than your 'next week'. Reply to reset expectations or deliver it; Reply to Anahit a…
- gen-s5-small cp1 q-008 `project_attr` score 0.00 (base 0.00): What is currently blocking Wagtail?  
  gold: real patient data paused pending the security review  
  predicted: Nothing
- gen-s5-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Rodrigo Okada?  
  gold: executive  
  predicted: abstain
- gen-s6-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Andres the Fennel rollout checklist  
  predicted: Finish and send Andres the Fennel access request (draft saved 23 Feb but not sent; attachment missing); Reply to Andres about the Fennel rollout checklist he wants by Wed 24 Feb (decide yes or no); S…
- gen-s8-w4 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Complete the Fulmar privacy impact assessment  
  predicted: Finish and send the Fulmar privacy impact assessment to Goran Liu. It was due 14 Sep and no completion has been seen, so it is probably overdue; Walk Adwoa Kocak through the operator AI basics worksh…
- gen-s9-large cp1 q-009 `person_attr` score 0.00 (base 0.00): Which organization is Mikayla Babic with?  
  gold: Network Digital Office  
  predicted: abstain
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Tinderbox security review package (architecture, data flows, retention, sub-processor list; identity section from Teo's ticket). Drafted (em-0031) but NOT sent: retention is half done and the sub-pro…
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: Reference checks (two references) for MLE candidate Mats Okonedo, starting Wed 3 Mar. After that it is Sade's decision
- pilot cp1 q-011 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Ramona the workshop deck v2  
  predicted: Get workshop deck v2 to Ramona Szabo before the 07:30 offsite bus (no laptop all day); Attend the leadership offsite (bus 07:30 sharp; back ~17:00). Ramona covers the standup and workshop logistics; …
- pilot cp1 q-013 `i_owe` score 0.00 (base 0.00): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Weekly update (3 bullets + 1 risk), subject 'Weekly update: w/e 5 Mar'; Council one-pager on chargeback (3 bullets + 1 risk), leading with the conditional; for Sade only; Get Sade and Bart Ngata in a…
- pilot cp1 q-014 `project_changes` score 0.12 (base 0.12): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Hosting decided: option 2, the Kettleyard shared tenant. Jack stops pricing option 1; ARB rejected LMS spec v1 and requires an event-based context API via the integration bus. Dima's 5 Mar date is de…
- gen-s2-w1 cp1 q-010 `project_loops` score 0.15 (base 0.17): What loops are open on the workshop?  
  gold: Turn the AI in public service workshop questions into an FAQ; Send Dina the AI in public service workshop run sheet; Share the AI in public service workshop fe…  
  predicted: Turn the workshop questions into an FAQ; Workshop slides (Dina owns them; delivery not recorded); Room plan for Tendai (not agreed: 'let me check'); Run sheet from Catrin; Feedback form from Nomvula …
- pilot cp1 q-008 `person_brief` score 0.16 (base 0.18): I'm meeting Delphine on Thursday. What am I working on with her?  
  gold: Shared project: Writing Feedback Tool Selection (Delphine Arceneaux is sponsor); Shared project: Saltmarren Transfer Evaluation Discovery (Delphine Arceneaux i…  
  predicted: Thu 4 Mar 11:00–11:30 video check-in with Delphine Arceneaux (interim registrar, Saltmarren). She sponsors two of your projects: the WFT bake-off and the Saltmarren transfer evaluation discovery. The…
- gen-s9-large cp1 q-003 `project_changes` score 0.18 (base 0.20): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Kasane sandbox access set up for Aroha by Eleni (Lena) Rattanakorn, Kasane Solutions Engineer; the sandbox resets every Sunday night; At the Cirrus standup Aroha said tentatively she 'can probably se…
- gen-s7-w2 cp1 q-003 `project_changes` score 0.29 (base 0.33): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Decision: Corrie will be built in-house rather than bought (confirmed by Anastasia); Corrie sync held. The documentation is still described as thin, and no new actions came out of it.; Hiba handed Co…
- pilot cp1 q-001 `project_status` score 0.47 (base 0.50): What's the status of the Kestrow course assistant pilot?  
  gold: Tinderbox is active; Current phase: build (dummy-data mode); Tinderbox blockers now include the ARB's rejection of spec v1; Current blocker: Real student data …  
  predicted: Tinderbox (Kestrow course assistant pilot) is in build, in dummy-data mode, with go-live still at 29 Mar 'for now'. The Kettleyard tenant went live on 2 Mar (tinderbox-kes-01) and the load test runs …
- gen-s3-w1 cp1 q-010 `project_loops` score 0.48 (base 0.52): What loops are open on Rosix Enterprise Agreement?  
  gold: Draft our counter-proposal to Rosix; Send Alasdair the Rosix volume tiers; Send Alasdair the Rosix enterprise agreement term sheet  
  predicted: Alasdair to draft the counter-proposal to Rosix (probably moot); Bisi Njoroge to send the Rosix volume tiers (possibly moot); Bisi Chatterjee to send the Rosix EA term sheet (possibly moot); Alasdair…
- gen-s4-w2 cp1 q-005 `owed_to_me` score 0.49 (base 0.56): What does Meera Kariuki currently owe me?  
  gold: Send Ottavio the Ithic deep-dive materials; Collect two customer references from Ithic; Collect two customer references from Ithic again; Send Ottavio the note…  
  predicted: Two customer references from Ithic (blocked, waiting on access approval); Notes from the alumni outreach session (offered to send 'again' in the @meerak DM, and I accepted). The original promise came…
- gen-s4-w2 cp1 q-010 `project_loops` score 0.49 (base 0.59): What loops are open on Cairn platform?  
  gold: Set gateway rate limits for Cairn tenants; Review Nomvula's Cairn pilot charter; Send Darius the Cairn support model; Confirm the Cairn comms plan with Theresa  
  predicted: Review Nomvula's Cairn pilot charter; Confirm the Cairn comms plan with Theresa; Set gateway rate limits for Cairn tenants; Ratna to send Darius the Cairn support model; Theresa (Resi) may publish th…
- pilot cp1 q-009 `project_loops` score 0.50 (base 0.52): What loops are open on the writing tool bake-off?  
  gold: Send Scrivelo's accessibility conformance report; Send Scrivelo's LMS integration API documentation; Send two Scrivelo customer references from comparable camp…  
  predicted: Scorecard summary of both vendors side by side, plus an internal-build (Kettleyard) column; RFQ requirements section (Word doc), with the named tier-2 support owner and data handling. Do not quote th…
