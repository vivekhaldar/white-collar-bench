## Headline

| Model | Track | WCB-lite | 95% CI | WCB-micro | Synthesis (lite) | SIS (lite) |
|---|---|---:|---|---:|---:|---:|
| sol | A | 69.3 | 63.9–74.6 | 70.8 | 86.2 | 99.5 |
| sol | B | 58.5 | 52.8–63.8 | 57.2 | – | – |

## Per world (WCB-lite world score)

| World | sol A | sol B |
|---|---:|---:|
| pilot | 56.9 | 47.8 |
| gen-s9-large | 80.8 | 68.7 |
| gen-s8-w4 | 63.3 | 51.7 |
| gen-s4-w2 | 84.4 | 70.0 |
| gen-s7-w2 | 71.2 | 67.5 |
| gen-s1-w1 | 74.8 | 61.5 |
| gen-s2-w1 | 59.4 | 58.7 |
| gen-s3-w1 | 67.1 | 55.3 |
| gen-s6-w1 | 73.3 | 59.5 |
| gen-s10-w2-small | 73.7 | 64.3 |
| gen-s5-small | 57.1 | 38.0 |

## By bucket (mean question score; agent store, oracle store in brackets for A)

| Bucket | sol A | sol B |
|---|---:|---:|
| point | 0.94 (0.96) | 0.69 |
| list | 0.67 (0.82) | 0.36 |
| status | 0.68 (0.84) | 0.44 |
| brief | 0.57 (0.78) | 0.47 |
| change | 0.17 (0.53) | 0.14 |
| temporal | 1.00 (1.00) | 0.95 |
| priority | 0.52 (0.94) | 0.68 |
| unanswerable | 1.00 (1.00) | 1.00 |

## Loss decomposition (WCB-lite points; questions affected)

| Model | Track | Lost | invalid | wrong_abstention | answered_unanswerable | base_zero | base_partial | citation_penalty |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| sol | A | 30.74 | 0.00 (0) | 0.00 (0) | 0.00 (0) | 15.47 (19) | 13.37 (40) | 1.90 (55) |
| sol | A oracle | 13.83 | 0.00 (0) | 0.00 (0) | 0.00 (0) | 1.75 (4) | 10.10 (37) | 1.97 (58) |
| sol | B | 41.55 | 0.00 (0) | 0.16 (1) | 0.00 (0) | 19.92 (34) | 17.73 (42) | 3.74 (79) |

## By planted challenge (mean agent score; tags overlap)

| Challenge | n | sol A | sol B |
|---|---:|---:|---:|
| alias | 36 | 0.67 | 0.45 |
| correction | 1 | 0.64 | 0.23 |
| draft_vs_sent | 1 | 0.00 | 0.00 |
| duplicate_signal | 47 | 0.69 | 0.56 |
| endorsement | 20 | 0.61 | 0.47 |
| implied_commitment | 32 | 0.53 | 0.46 |
| name_collision | 19 | 0.81 | 0.53 |
| new_entity | 5 | 0.70 | 0.38 |
| scattered_evidence | 38 | 0.59 | 0.54 |
| silent_closure | 2 | 0.26 | 0.18 |
| supersession | 23 | 0.64 | 0.50 |
| transfer | 11 | 0.88 | 0.70 |
| unobservable | 21 | 0.99 | 0.97 |
| worker_directive | 16 | 0.70 | 0.59 |

## Sessions, tokens and cost (lite; micro in the second table)


### lite

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sol | A | 33 | 0 | 0 | 515 | 1.50M | 14.03M | 0.00M | 0.40M | 8.38 | 1.72 | 4.57 |
| sol | B | 44 | 0 | 0 | 680 | 1.93M | 17.34M | 0.00M | 0.38M | 9.41 | 0.00 | 5.19 |

### micro

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sol | A | 15 | 0 | 0 | 232 | 0.73M | 6.71M | 0.00M | 0.19M | 4.05 | 0.80 | 2.21 |
| sol | B | 20 | 0 | 0 | 296 | 0.93M | 7.82M | 0.00M | 0.18M | 4.43 | 0.00 | 2.45 |

## Lowest-scoring agent answers (lite)


### sol A: 33 answers below 0.5

- gen-s1-w1 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of Marten?  
  gold: Marten is active; Current phase: security review; Marten target date moved to 31 December; Current target date: 2027-12-31 (moved from 2027-12-22); Assemble th…  
  predicted: Marten is active in security review: a four-service-center Birchcrest library help pilot hosted on Obsidian, owned by Petra Korkmaz. Its target is now December 31, 2027. Access approval still blocks …
- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: At Monday's Holworth site visit, Catrin's translation-help vendor comparison was discussed and a review was suggested for Aoife. No owner agreed, so this is a new unendorsed review request, not a com…
- gen-s2-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Update the Mistral access request after Bilal's comments  
  predicted: Address Bilal's Mistral access-request revision request; confirm whether you can take it on and revise it if agreed.; Prepare Cassandra's Mistral equity-impact-review walkthrough.; Resolve whether yo…
- gen-s2-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on the workshop?  
  gold: Turn the AI in public service workshop questions into an FAQ; Send Dina the AI in public service workshop run sheet; Share the AI in public service workshop fe…  
  predicted: Turn workshop questions into an FAQ — your accepted commitment.; Send Tendai the workshop room plan — recorded as suggested, not accepted; no delivery evidenced.; Catrin to send the speaker brief — r…
- gen-s3-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Eleni the referral triage discovery interview guide  
  predicted: Respond to Eleni's interview-guide request and agree whether you can deliver it tomorrow.; Attach and send Bisi the Okapi action log.; Prepare Penny's Okapi downtime-procedure walkthrough and clarify…
- gen-s4-w2 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Tariq?  
  gold: Send Tariq the Friday status note for w/e 10 September  
  predicted: Send Tariq the half-page Friday status note for w/e 10 September, by end of day; weekly reminder received, but no new explicit acceptance recorded. Cover what moved, what slipped and leadership needs.
- gen-s5-small cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Review Anahit's Wagtail service blueprint  
  predicted: Resolve tomorrow's Wagtail review requests: the service blueprint for Anahit and privacy impact assessment for Aylin. Confirm whether you will take them on; neither is an accepted commitment yet.; Pr…
- gen-s5-small cp1 q-008 `project_attr` score 0.00 (base 0.00): What is currently blocking Wagtail?  
  gold: real patient data paused pending the security review  
  predicted: Security review
- gen-s6-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Andres the Fennel rollout checklist  
  predicted: Respond to Andres's request for the Fennel rollout checklist; agree whether you can deliver it tomorrow, then send it if accepted.; Prepare Liisa's Axolotl decision-memo walkthrough and resolve Natha…
- gen-s7-w2 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Complete the Garnet privacy impact assessment  
  predicted: Resolve Tyrone's request for the Garnet privacy impact assessment: confirm ownership/acceptance and address the requested deadline.; Prepare the committed Siskin metrics-definition walkthrough with B…
- gen-s8-w4 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of Fulmar?  
  gold: Fulmar is active; Current phase: security review; Fulmar target date moved to 24 November; Current target date: 2027-11-24 (moved from 2027-11-12); Complete th…  
  predicted: As of 14 September, Fulmar is active in security review: a four-line Ivycrest warranty-claims pilot hosted on Wagtail, owned by Ottavio Bakker. Its current target is 24 November 2027. Export failures…
- gen-s8-w4 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on the responsible-use framework since the end of Friday 10 September?  
  gold: Decided to use approach C for the AI-use glossary; Dropped: share the AI-use principles draft with me (superseded by the approach C decision); I said I could g…  
  predicted: Amira selected approach C for the AI-use glossary and dropped sharing the principles draft as superseded.; A tentative suggestion to send Ottavio the glossary sometime in 20–26 September was recorded…
- gen-s9-large cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Kasane sandbox access became ready; Eleni (Lena) requested a password change at first login. No login or password change is evidenced.; Aroha promised Anh a pricing comparison, creating a separate ac…
- gen-s9-large cp1 q-015 `project_attr` score 0.00 (base 0.00): What is currently blocking Cirrus?  
  gold: real patient data paused pending the security review  
  predicted: Pending security review, an unsigned SSO agreement, and a vendor fix for the support playbook
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Finish and send the Tinderbox security review package: architecture, data flows, Kettleyard controls and dummy-data setup, with completed retention details and sub-processor list. Architecture/data f…
- pilot cp1 q-006 `i_owe` score 0.00 (base 0.00): What do I owe Ramona at Brackwater?  
  gold: Write Ramona Iturbe a concept note for the library research assistant  
  predicted: Write a concept note for the library research assistant. Still owed, but the idea is parked until after Brackwater midterms (mid-March); no hard deadline. This is Ramona Iturbe, not ODS's Ramona Szab…
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: Conduct two reference checks for Mateus under her process, starting March 3 now all three independent scorecards are in. Still open; March 3 is a start date, not a completion deadline. Shared hiring …
- pilot cp1 q-013 `i_owe` score 0.00 (base 0.00): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Email the weekly AI and Data update: three bullets and one risk, subject 'Weekly update: w/e 5 Mar'. Still unsent.; Send the Council chargeback one-pager to Sade only: three bullets and one risk, lea…
- pilot cp1 q-014 `project_changes` score 0.00 (base 0.00): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Since Friday February 26, hosting was settled on option 2, the shared Kettleyard tenant; dedicated Kestrow deployment pricing was dropped.; ARB rejected polling spec v1 in favor of integration-bus ev…
- gen-s5-small cp1 q-003 `project_changes` score 0.10 (base 0.11): What changed on Project Wagtail since the end of Saturday 27 March?  
  gold: I offered to walk Anahit through the Wagtail risk register; Anahit asked me to review the Wagtail order set review (not yet agreed); I sent Marcelo the Wagtail…  
  predicted: Hiba committed to a risk-register walkthrough with Anahit; it was scheduled for 1 April, 19:00–19:30 UTC, with Anahit still needing to respond. Anahit also requested a Wagtail order-set review, which…
- pilot cp1 q-008 `person_brief` score 0.10 (base 0.11): I'm meeting Delphine on Thursday. What am I working on with her?  
  gold: Shared project: Writing Feedback Tool Selection (Delphine Arceneaux is sponsor); Shared project: Saltmarren Transfer Evaluation Discovery (Delphine Arceneaux i…  
  predicted: You share Saltmarren transfer-evaluation discovery and the writing-feedback tool bake-off with sponsor Delphine. Thursday's check-in is March 4, 11:00–11:30, covering the scorecard summary, DSA and s…
- gen-s2-w1 cp1 q-003 `project_changes` score 0.18 (base 0.18): What changed on Mistral since the end of Saturday 6 March?  
  gold: I promised Cassandra the Mistral vendor comparison; I sent Imani the Mistral change request; I said I could get Yael the Mistral retention schedule sometime ne…  
  predicted: Sent Imani change request v1, completing that task. It preserves scope, records training/support/communications adjustments, and leaves security input and hosting/council questions unresolved.; Confi…
- gen-s3-w1 cp1 q-003 `project_changes` score 0.24 (base 0.25): What changed on Okapi since the end of Friday 17 September?  
  gold: Okapi accessibility review blocked: waiting on a vendor fix; I promised Bisi the Okapi action log; I said I could get Katarzyna the Okapi evaluation rubric som…  
  predicted: The accessibility review became blocked pending a vendor fix.; You committed to sending Bisi the Okapi action log. It remains open: the 21 September email is explicitly an unsent draft with no attach…
- gen-s6-w1 cp1 q-003 `project_changes` score 0.26 (base 0.26): What changed on Axolotl since the end of Friday 19 February?  
  gold: Liisa shared the Axolotl architecture diagram with Despina; I said I could get Nathaniel the Axolotl stakeholder map sometime next week; I said I'd take a look…  
  predicted: Liisa shared the Axolotl architecture diagram, closing that outstanding delivery.; Standup recorded an unaccepted action for Despina to send Nathaniel the stakeholder map. Separately, Despina sent An…
- gen-s8-w4 cp1 q-011 `person_brief` score 0.30 (base 0.32): What am I working on with Ottavio Bakker?  
  gold: Shared project: Fulmar (Ottavio Bakker is owner); Shared project: Wagtail (Ottavio Bakker is a member); Shared project: Work Instructions Tool Selection (Ottav…  
  predicted: Your most concrete current work with Ottavio Bakker (Tavo), Ivycrest's Production Planning Lead, is Fulmar: he owns the pilot and you owe him a vendor-comparison review. He also needs the responsible…

### sol B: 57 answers below 0.5

- gen-s1-w1 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of Marten?  
  gold: Marten is active; Current phase: security review; Marten target date moved to 31 December; Current target date: 2027-12-31 (moved from 2027-12-22); Assemble th…  
  predicted: Marten remains in security review for a four-service-center pilot hosted on Obsidian. Petra owns it and Fernanda sponsors it. The target is now 31 December. Recent decisions and completions have adva…
- gen-s1-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on Plain Language Workshop?  
  gold: Send Jalen the plain language workshop attendee list; Send the plain language workshop post-event survey; Send Sipho the plain language workshop session outlin…  
  predicted: Send the attendee list to Jalen; promised, no delivery shown.; Send slides v2 to Sipho. The 27 October email delivered them to Jalen, not Sipho, so it does not close this recipient-specific task.; Se…
- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: On 30 August, the Holworth site-visit recap raised reviewing Catrin Dang's translation-help-selection vendor comparison and suggested you as reviewer, explicitly saying no owner had agreed. This is a…
- gen-s10-w2-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with our programs manager?  
  gold: peer  
  predicted: Cross-portfolio colleague and collaborator
- gen-s2-w1 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Mistral since the end of Saturday 6 March?  
  gold: I promised Cassandra the Mistral vendor comparison; I sent Imani the Mistral change request; I said I could get Yael the Mistral retention schedule sometime ne…  
  predicted: Sent Mistral change request v1 to Imani, closing the earlier send promise. Scope is unchanged; support wording was revised and security/unit-host/council-routing questions remain open.; The rollout c…
- gen-s2-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Tendai Santos?  
  gold: stakeholder  
  predicted: Departmental counterpart at Selfell Public Works
- gen-s2-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on the workshop?  
  gold: Turn the AI in public service workshop questions into an FAQ; Send Dina the AI in public service workshop run sheet; Share the AI in public service workshop fe…  
  predicted: Convert workshop questions into FAQ — Dina's accepted task, with no individual completion or cancellation evidence.; Workshop slides — Dina owned them in the baseline, but individual delivery is not …
- gen-s3-w1 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Eleni?  
  gold: Send Eleni the referral triage discovery interview guide  
  predicted: Send the referral-triage discovery interview guide. Eleni requested it by Wednesday 22 September; no acceptance or delivery is recorded, so this is an outstanding request rather than a confirmed prom…
- gen-s3-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Lena?  
  gold: stakeholder  
  predicted: Project collaborator on Okapi and Ketford Referral Triage Discovery
- gen-s3-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on Rosix Enterprise Agreement?  
  gold: Draft our counter-proposal to Rosix; Send Alasdair the Rosix volume tiers; Send Alasdair the Rosix enterprise agreement term sheet  
  predicted: Draft the Rosix counter-proposal for Eun-ji: you offered on 7 September, but no delivery or explicit cancellation is evidenced; continued need after signing is unknown.; Confirm the enterprise-agreem…
- gen-s4-w2 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Tariq?  
  gold: Send Tariq the Friday status note for w/e 10 September  
  predicted: Friday status note for w/e September 10, by end of day: half a page on what moved, what slipped, and leadership needs. August 27 and September 3 notes were already sent.
- gen-s4-w2 cp1 q-006 `loop_owner` score 0.00 (base 0.00): Who is responsible for "Set up the Fjord single sign-on role mapping"?  
  gold: Ratna Nikolic  
  predicted: Ratna Nikolic and Meera Bondarenko
- gen-s4-w2 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Meera Bondarenko?  
  gold: peer  
  predicted: SLIO colleague and cross-project collaborator
- gen-s5-small cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Review Anahit's Wagtail service blueprint  
  predicted: Resolve the March 31 Wagtail review requests: respond to Anahit about the service blueprint and to Aylin about the privacy impact assessment; agree what you can actually deliver.; Confirm the acceler…
- gen-s5-small cp1 q-008 `project_attr` score 0.00 (base 0.00): What is currently blocking Wagtail?  
  gold: real patient data paused pending the security review  
  predicted: No currently reported blockers
- gen-s5-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Rodrigo Okada?  
  gold: executive  
  predicted: Wagtail project collaborator
- gen-s5-small cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on Falbury Clinical Documentation Discovery?  
  gold: Send Hiba the clinical documentation discovery opportunity list; Present the clinical documentation discovery readout to Falbury; Share the clinical documentat…  
  predicted: Present the discovery readout to Falbury with Anahit Fifita. Hiba committed to the presentation March 24; no date or completion is recorded, and Anahit's separate acceptance is not supplied.; Receive…
- gen-s6-w1 cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Rike currently owe me?  
  gold: Send Despina the notes from the research computing session  
  predicted: Send the notes from the research computing session. Friederike promised them February 11 and said the task was back on February 15; no delivery or due date is recorded.
- gen-s7-w2 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Anastasia explicitly confirmed build in-house rather than buy. The baseline already described an in-house prototype; this is a sponsor confirmation, not evidence of a newly reversed procurement choic…
- gen-s7-w2 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Dez?  
  gold: Review the Siskin model allow-list  
  predicted: Review the Siskin model allow-list; accepted directly in your June 24 DM with Dez and reaffirmed June 29, with no completion evidenced.
- gen-s8-w4 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Complete the Fulmar privacy impact assessment  
  predicted: Finish and send Goran the Fulmar privacy impact assessment, or explicitly report the slip if it remains undelivered.; Prepare the room plan and agenda, and walk Adwoa Kocak through the Operator AI Ba…
- gen-s8-w4 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of Fulmar?  
  gold: Fulmar is active; Current phase: security review; Fulmar target date moved to 24 November; Current target date: 2027-11-24 (moved from 2027-11-12); Complete th…  
  predicted: Fulmar, the four-line Ivycrest AI warranty claims pilot on Wagtail, is in security review. Its latest target is 24 November 2027. Several security and delivery commitments remain open, and its export…
- gen-s8-w4 cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Tane Haugen currently owe me?  
  gold: Send Amira the tooling wear wait-time export  
  predicted: Send the tooling-wear wait-time export. Adwoa relayed Tane's promise; no delivery is recorded. The earlier current safety-reporting process map was reported sent on 7 September, so is not an unqualif…
- gen-s9-large cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Kasane sandbox access was set up; first-login password change and Sunday-night resets were specified. There is no evidence of a completed sandbox evaluation.; Aroha explicitly committed to sending An…
- gen-s9-large cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Adebayo currently owe me?  
  gold: Draft the Cirrus load test plan  
  predicted: Draft the Cirrus load test plan. Stanley handed responsibility to Adebayo on 22 October; no delivery or explicit reverse handoff is recorded.
