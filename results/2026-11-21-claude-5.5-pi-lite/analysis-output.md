## Headline

| Model | Track | WCB-lite | 95% CI | WCB-micro | Synthesis (lite) | SIS (lite) |
|---|---|---:|---|---:|---:|---:|
| haiku | A | 81.4 | 76.4–85.7 | 83.9 | 90.1 | 99.4 |
| haiku | B | 64.7 | 58.8–69.6 | 64.8 | – | – |
| sonnet | A | 83.8 | 80.5–87.3 | 85.5 | 92.0 | 99.5 |
| sonnet | B | 71.1 | 65.0–76.5 | 67.0 | – | – |

## Per world (WCB-lite world score)

| World | haiku A | haiku B | sonnet A | sonnet B |
|---|---:|---:|---:|---:|
| pilot | 69.4 | 42.7 | 75.9 | 60.8 |
| gen-s9-large | 88.1 | 80.1 | 87.2 | 68.8 |
| gen-s8-w4 | 87.5 | 70.7 | 88.6 | 79.3 |
| gen-s4-w2 | 91.2 | 67.0 | 89.8 | 70.7 |
| gen-s7-w2 | 66.6 | 56.8 | 77.0 | 80.9 |
| gen-s1-w1 | 86.3 | 71.7 | 94.5 | 84.4 |
| gen-s2-w1 | 72.1 | 67.4 | 84.0 | 64.2 |
| gen-s3-w1 | 82.1 | 64.9 | 86.4 | 72.6 |
| gen-s6-w1 | 85.5 | 65.2 | 77.6 | 79.4 |
| gen-s10-w2-small | 81.9 | 63.0 | 80.7 | 70.8 |
| gen-s5-small | 84.5 | 62.3 | 80.3 | 50.2 |

## By bucket (mean question score; agent store, oracle store in brackets for A)

| Bucket | haiku A | haiku B | sonnet A | sonnet B |
|---|---:|---:|---:|---:|
| point | 0.93 (0.96) | 0.65 | 0.93 (0.97) | 0.78 |
| list | 0.78 (0.90) | 0.48 | 0.87 (0.93) | 0.56 |
| status | 0.89 (0.79) | 0.55 | 0.88 (0.78) | 0.65 |
| brief | 0.82 (0.92) | 0.53 | 0.82 (0.91) | 0.50 |
| change | 0.37 (0.72) | 0.26 | 0.35 (0.84) | 0.36 |
| temporal | 1.00 (1.00) | 0.95 | 1.00 (1.00) | 1.00 |
| priority | 0.72 (0.94) | 0.76 | 0.88 (0.93) | 0.86 |
| unanswerable | 1.00 (1.00) | 1.00 | 1.00 (1.00) | 1.00 |

## Loss decomposition (WCB-lite points; questions affected)

| Model | Track | Lost | invalid | wrong_abstention | answered_unanswerable | base_zero | base_partial | citation_penalty |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| haiku | A | 18.64 | 0.00 (0) | 0.38 (1) | 0.00 (0) | 6.20 (9) | 10.52 (39) | 1.54 (52) |
| haiku | A oracle | 9.89 | 0.00 (0) | 0.38 (1) | 0.00 (0) | 1.14 (1) | 7.10 (32) | 1.27 (44) |
| haiku | B | 35.28 | 0.23 (1) | 0.54 (2) | 0.00 (0) | 12.12 (23) | 17.75 (49) | 4.64 (90) |
| sonnet | A | 16.18 | 0.00 (0) | 0.00 (0) | 0.00 (0) | 4.84 (7) | 10.09 (39) | 1.25 (40) |
| sonnet | A oracle | 8.04 | 0.00 (0) | 0.38 (1) | 0.00 (0) | 2.65 (3) | 4.32 (24) | 0.69 (20) |
| sonnet | B | 28.90 | 0.00 (0) | 1.52 (4) | 0.00 (0) | 8.56 (16) | 16.24 (51) | 2.59 (65) |

## By planted challenge (mean agent score; tags overlap)

| Challenge | n | haiku A | haiku B | sonnet A | sonnet B |
|---|---:|---:|---:|---:|---:|
| alias | 36 | 0.73 | 0.53 | 0.82 | 0.60 |
| correction | 1 | 0.94 | 0.00 | 0.86 | 0.29 |
| draft_vs_sent | 1 | 0.00 | 0.00 | 0.92 | 0.00 |
| duplicate_signal | 47 | 0.83 | 0.67 | 0.88 | 0.76 |
| endorsement | 20 | 0.75 | 0.55 | 0.81 | 0.65 |
| implied_commitment | 32 | 0.69 | 0.50 | 0.79 | 0.61 |
| name_collision | 19 | 0.92 | 0.46 | 0.93 | 0.64 |
| new_entity | 5 | 0.91 | 0.41 | 0.85 | 0.58 |
| scattered_evidence | 38 | 0.77 | 0.64 | 0.81 | 0.70 |
| silent_closure | 2 | 0.53 | 0.40 | 0.54 | 0.32 |
| supersession | 23 | 0.80 | 0.51 | 0.78 | 0.69 |
| transfer | 11 | 0.79 | 0.75 | 0.81 | 0.83 |
| unobservable | 21 | 0.97 | 0.97 | 1.00 | 0.99 |
| worker_directive | 16 | 0.79 | 0.64 | 0.83 | 0.77 |

## Sessions, tokens and cost (lite; micro in the second table)


### lite

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| haiku | A | 33 | 0 | 0 | 607 | 0.00M | 32.72M | 3.18M | 1.26M | 1.35 | 0.25 | 1.35 |
| haiku | B | 44 | 0 | 0 | 911 | 0.00M | 59.27M | 4.16M | 1.63M | 1.93 | 0.00 | 1.93 |
| sonnet | A | 33 | 0 | 0 | 267 | 0.00M | 6.84M | 1.50M | 0.33M | 7.72 | 2.04 | 7.72 |
| sonnet | B | 44 | 0 | 0 | 266 | 0.00M | 5.19M | 1.58M | 0.30M | 7.48 | 0.00 | 7.48 |

### micro

| Model | Track | Sessions | Incomplete | Failed | Calls | Input (uncached) | Cache read | Cache write | Output | Agent $ | Oracle $ | Self-reported agent $ |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| haiku | A | 15 | 0 | 0 | 294 | 0.00M | 16.99M | 1.51M | 0.58M | 0.65 | 0.11 | 0.65 |
| haiku | B | 20 | 0 | 0 | 435 | 0.00M | 29.22M | 1.98M | 0.76M | 0.92 | 0.00 | 0.92 |
| sonnet | A | 15 | 0 | 0 | 129 | 0.00M | 3.78M | 0.74M | 0.16M | 3.86 | 0.90 | 3.86 |
| sonnet | B | 20 | 0 | 0 | 126 | 0.00M | 2.58M | 0.77M | 0.15M | 3.64 | 0.00 | 3.64 |

## Lowest-scoring agent answers (lite)


### haiku A: 17 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: Holworth site visit (30 Aug, with Akosua, Amani Xu and you) discussed Catrin Dang's translation help vendor comparison; no owner was agreed. A suggested review for you was logged but is not accepted.
- gen-s2-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Update the Mistral access request after Bilal's comments  
  predicted: Decide on the Mistral access request update for Bilal (due 2027-03-10); Decide on sending Yael the Mistral retention schedule (needed by 2027-03-11); Prepare for the Mistral equity impact review walk…
- gen-s3-w1 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Eleni?  
  gold: Send Eleni the referral triage discovery interview guide  
  predicted: []
- gen-s6-w1 cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Rike currently owe me?  
  gold: Send Despina the notes from the research computing session  
  predicted: abstain
- gen-s7-w2 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Complete the Garnet privacy impact assessment  
  predicted: Respond to Tyrone Duarte on the Garnet privacy impact assessment (he asked for it by 2027-07-07; not yet accepted, so confirm or decline); Send Andrei Laurent the Siskin one-page summary; Prepare for…
- gen-s7-w2 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Anastasia Mizrahi confirmed Corrie will be built in-house rather than bought (decision recorded as done); Corrie check-in at the Corrie / Garnet sync; Corrie sync with Zawadi Grigoryan, Kristen Ochie…
- gen-s7-w2 cp1 q-006 `loop_owner` score 0.00 (base 0.00): Who is responsible for "Return the Merol security questionnaire again"?  
  gold: Bolat Oyelami  
  predicted: Bolat Farah
- gen-s9-large cp1 q-015 `project_attr` score 0.00 (base 0.00): What is currently blocking Cirrus?  
  gold: real patient data paused pending the security review  
  predicted: Security review
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Prepare the Tinderbox security review package for Hyun-woo Park (Hugo). Draft is unsent (em-0031) and needs the sub-processor list before it goes out.
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: []
- pilot cp1 q-014 `project_changes` score 0.06 (base 0.07): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Hosting decided: option 2, the shared Kettleyard tenant; option 1 (dedicated Kestrow deployment) dropped.; ARB rejected interface spec v1 and wants an event-based context API; the 5 Mar context API d…
- pilot cp1 q-013 `i_owe` score 0.36 (base 0.40): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Send the weekly AI & Data update for the week of 1 Mar (three bullets and one risk).; One-page Council of Campus CIOs summary on chargeback (three bullets and one risk, leading with 'no Tinderbox at …
- gen-s9-large cp1 q-003 `project_changes` score 0.41 (base 0.44): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Kasane sandbox access was set up for the worker (temporary credentials redacted, not recorded).; Worker said they will send Anh the bed management selection pricing comparison.; Anh moved the decisio…
- gen-s3-w1 cp1 q-003 `project_changes` score 0.43 (base 0.44): What changed on Okapi since the end of Friday 17 September?  
  gold: Okapi accessibility review blocked: waiting on a vendor fix; I promised Bisi the Okapi action log; I said I could get Katarzyna the Okapi evaluation rubric som…  
  predicted: Okapi accessibility review (to Bisi) marked blocked, waiting on a vendor fix.; Okapi scoping call held; I said I'd try to send Katarzyna the evaluation rubric (not accepted).; I committed to send Bis…
- gen-s6-w1 cp1 q-003 `project_changes` score 0.46 (base 0.48): What changed on Axolotl since the end of Friday 19 February?  
  gold: Liisa shared the Axolotl architecture diagram with Despina; I said I could get Nathaniel the Axolotl stakeholder map sometime next week; I said I'd take a look…  
  predicted: Liisa shared the Axolotl architecture diagram with you; loop marked done.; You sent Andres the Axolotl stakeholder map v1; loop marked done.; Stakeholder map v1 open questions recorded: whether it go…
- pilot cp1 q-001 `project_status` score 0.47 (base 0.50): What's the status of the Kestrow course assistant pilot?  
  gold: Tinderbox is active; Current phase: build (dummy-data mode); Tinderbox blockers now include the ARB's rejection of spec v1; Current blocker: Real student data …  
  predicted: The Kestrow course assistant pilot is Tinderbox (projects/tinderbox), active and in build phase on dummy data. The tenant on Kettleyard went live on 2027-03-02 as the first production tenant. Real st…
- gen-s1-w1 cp1 q-001 `focus_tomorrow` score 0.48 (base 0.50): What should I focus on tomorrow?  
  gold: Assemble the Marten security review package; Send Jalen the ranked benefits screening discovery use cases  
  predicted: Send Jalen the ranked benefits screening discovery use cases; Walk Jalen through the plain language workshop speaker brief; Attend the Nantgate partnership sync with Jalen and Petra; Send Thandiwe th…

### haiku B: 47 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: A 30 Aug auto-generated site-visit summary mentions a "Catrin's translation help selection vendor comparison" with no owner, and suggests Aoife review it. The comparison is not in the store and the s…
- gen-s10-w2-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with our programs manager?  
  gold: peer  
  predicted: Close working partner
- gen-s2-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Tendai Santos?  
  gold: stakeholder  
  predicted: Selfell Customer Service Manager; working counterpart on PRTS and the inspection/parking work
- gen-s2-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on the workshop?  
  gold: Turn the AI in public service workshop questions into an FAQ; Send Dina the AI in public service workshop run sheet; Share the AI in public service workshop fe…  
  predicted: FAQ from the workshop questions (cross-department AI forum); Reply on the workshop room plan; Run sheet; Speaker brief (not agreed); Registration list (unconfirmed); Feedback form (Nomvula says she i…
- gen-s3-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Lena?  
  gold: stakeholder  
  predicted: Ketford colleague on the Okapi team (Revenue Cycle Analyst)
- gen-s4-w2 cp1 q-008 `project_attr` score 0.00 (base 0.00): What phase is Fjord in?  
  gold: build  
  predicted: Scoping/design
- gen-s4-w2 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Meera Bondarenko?  
  gold: peer  
  predicted: Colleague in SLIO (Head of Learning Services); day-to-day collaborator
- gen-s5-small cp1 q-008 `project_attr` score 0.00 (base 0.00): What is currently blocking Wagtail?  
  gold: real patient data paused pending the security review  
  predicted: Friederike Bhatt's overdue Wagtail change request
- gen-s5-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Rodrigo Okada?  
  gold: executive  
  predicted: Falbury client-side stakeholder (Chief Medical Information Officer)
- gen-s6-w1 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of Axolotl?  
  gold: Axolotl is active; Current phase: build; Axolotl target date moved to 7 April; Current target date: 2027-04-07 (moved from 2027-03-30); Send Nathaniel the Axol…  
  predicted: Axolotl (aka lab safety training pilot / Dorcliff pilot) is in build, per an unverified auto summary. The pilot is limited to five courses (agreed 18 Feb). API contract v2 was delivered to Tomas on 2…
- gen-s6-w1 cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Rike currently owe me?  
  gold: Send Despina the notes from the research computing session  
  predicted: abstain
- gen-s7-w2 cp1 q-002 `project_status` score 0.00 (base 0.00): What is the status of the Crandale pilot?  
  gold: Garnet is active; Current phase: security review; Garnet target date moved to 3 August; Current blocker: real student data paused pending the security review; …  
  predicted: The Crandale pilot (Project Garnet) is in the build stage and moving into security review. The security review package went to Andrei on 07-06. Tyrone Duarte's privacy impact assessment is due 7 Jul …
- gen-s7-w2 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Anastasia Mizrahi decided Corrie will be built in-house rather than bought.; Corrie sync held 09:00-09:30 with Zawadi Grigoryan, Bolat Oyelami and Kristen Ochieng; the auto transcript has little cont…
- gen-s7-w2 cp1 q-008 `project_attr` score 0.00 (base 0.00): What is the current target date for Garnet?  
  gold: 2027-08-03  
  predicted: 2027-07-26
- gen-s7-w2 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on Corrie?  
  gold: Write up the Corrie usability findings; Confirm the Corrie usability test script with Zawadi  
  predicted: Write up Corrie usability findings. Anastasia asked (via Bolat) on 06-23; Hiba's acceptance is not in the inbox. May be moot after the 07-06 handover.; Confirm the Corrie usability test script with Z…
- gen-s9-large cp1 q-009 `person_attr` score 0.00 (base 0.00): Which organization is Mikayla Babic with?  
  gold: Network Digital Office  
  predicted: abstain
- gen-s9-large cp1 q-015 `project_attr` score 0.00 (base 0.00): What is currently blocking Cirrus?  
  gold: real patient data paused pending the security review  
  predicted: Security review (real patient data paused until it clears)
- gen-s9-large cp1 q-016 `person_attr` score 0.00 (base 0.00): What is my working relationship with Mathieu Wijaya?  
  gold: peer  
  predicted: Internal NDO colleague (Principal, Integration Platform)
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Security review package for Tinderbox (architecture, data flows, retention, sub-processor list, prompt-log retention sentence). Draft exists but is unsent; still missing the sub-processor list and at…
- pilot cp1 q-006 `i_owe` score 0.00 (base 0.00): What do I owe Ramona at Brackwater?  
  gold: Write Ramona Iturbe a concept note for the library research assistant  
  predicted: Library research assistant concept note (Brackwater library idea). Owed to Ramona Iturbe; no date; she said no rush. The project is parked until after midterms.
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: REQ-2207 reference checks (two references, her process; starts Wed 3 Mar). Second-hand. Sade decides after references.; REQ-2207 candidate compensation (left to Sol).
- pilot cp1 q-009 `project_loops` score 0.00 (base 0.00): What loops are open on the writing tool bake-off?  
  gold: Send Scrivelo's accessibility conformance report; Send Scrivelo's LMS integration API documentation; Send two Scrivelo customer references from comparable camp…  
  predicted: RFQ requirements section (functional, technical, security, accessibility, support, data handling) to Clement, Word format.; Vendor scorecard summary, both vendors side by side (with internal-build co…
- pilot cp1 q-011 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Ramona the workshop deck v2  
  predicted: Send Ramona S. the workshop deck v2 before the 07:30 bus. The noon deadline is at risk because you are at the all-day offsite with no laptop.; Plan the Tinderbox spec v2 (event-based) so it can be wr…
- pilot cp1 q-012 `person_attr` score 0.00 (base 0.00): What is Hana's role?  
  gold: Privacy Officer  
  predicted: Kestrow Privacy Officer
- pilot cp1 q-013 `i_owe` score 0.00 (base 0.00): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Weekly update to Sade, 'Weekly update: w/e 5 Mar' (three bullets + one risk).; Chargeback one-pager for Sade: three bullets + one risk (no actuals), leading with the conditional. Internal only, not t…

### sonnet A: 15 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: Holworth site visit recap suggested reviewing Catrin's translation help selection vendor comparison; not accepted and no owner agreed, so it is only a suggested open loop. No other changes to the pro…
- gen-s5-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Rodrigo Okada?  
  gold: executive  
  predicted: Executive stakeholder (Chief Medical Information Officer at Falbury Community Clinics)
- gen-s6-w1 cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Send Andres the Fennel rollout checklist  
  predicted: Decide on and, if accepting, prepare the Fennel rollout checklist for Andres (due 2027-02-24, not yet accepted); Prepare the Axolotl stakeholder map for Nathaniel (wanted by 2027-02-25, not yet accep…
- gen-s7-w2 cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Project Corrie since the end of Saturday 3 July?  
  gold: Decided to build Corrie in-house rather than buy; I'm handing Corrie over to Iselbury; I handed Corrie over to Iselbury  
  predicted: Anastasia confirmed Corrie will be built in-house rather than bought; Corrie / Garnet sync held; check-in on Corrie; Handover of Corrie to Iselbury reported done; Corrie sync held with Iselbury (Zawa…
- gen-s7-w2 cp1 q-006 `loop_owner` score 0.00 (base 0.00): Who is responsible for "Return the Merol security questionnaire again"?  
  gold: Bolat Oyelami  
  predicted: Bolat Farah
- gen-s9-large cp1 q-015 `project_attr` score 0.00 (base 0.00): What is currently blocking Cirrus?  
  gold: real patient data paused pending the security review  
  predicted: Security review (real patient data paused pending it); also SSO role mapping waiting on an unsigned agreement and the support playbook waiting on a vendor fix
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: []
- pilot cp1 q-014 `project_changes` score 0.13 (base 0.14): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Hosting decided: shared Kettleyard tenant (option 2); option 1 pricing dropped; ARB rejected interface spec v1; wants event-based context API; Mara owns spec v2; Dmitri parked polling work; KSD-20931…
- gen-s9-large cp1 q-003 `project_changes` score 0.23 (base 0.25): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Kasane sandbox access set up for Aroha by Eleni Rattanakorn; Aroha promised Anh the bed management selection pricing comparison; Adebayo needs the pricing comparison by 2027-11-04; only an unsent dra…
- pilot cp1 q-013 `i_owe` score 0.37 (base 0.40): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Send Sade the one-page chargeback brief for the Council of Campus CIOs; Send Sade the weekly AI/data update (three bullets and one risk), week ending 5 Mar; Get Sade and Bart Ngata together on Tinder…
- gen-s2-w1 cp1 q-003 `project_changes` score 0.37 (base 0.38): What changed on Mistral since the end of Saturday 6 March?  
  gold: I promised Cassandra the Mistral vendor comparison; I sent Imani the Mistral change request; I said I could get Yael the Mistral retention schedule sometime ne…  
  predicted: Sent Imani the Mistral change request v1; Mistral rollout checklist received from Yael; New asks: vendor comparison to Cassandra and Thibault; duplicate notifications to look into; equity impact walk…
- gen-s3-w1 cp1 q-003 `project_changes` score 0.41 (base 0.44): What changed on Okapi since the end of Friday 17 September?  
  gold: Okapi accessibility review blocked: waiting on a vendor fix; I promised Bisi the Okapi action log; I said I could get Katarzyna the Okapi evaluation rubric som…  
  predicted: Accessibility review for Bisi became blocked on a vendor fix; I said I'd send Bisi the Okapi action log; Suggested (not accepted) that I try to send Katarzyna the evaluation rubric; Agreed to walk Pe…
- gen-s6-w1 cp1 q-003 `project_changes` score 0.45 (base 0.46): What changed on Axolotl since the end of Friday 19 February?  
  gold: Liisa shared the Axolotl architecture diagram with Despina; I said I could get Nathaniel the Axolotl stakeholder map sometime next week; I said I'd take a look…  
  predicted: Liisa shared the Axolotl architecture diagram (loop done); Tentative plan to send Nathaniel the stakeholder map (not accepted); Lindiwe to send access request; I took on slow page loads; Offered Liis…
- gen-s4-w2 cp1 q-003 `project_changes` score 0.48 (base 0.50): What changed on Fjord since the end of Saturday 4 September?  
  gold: I promised Darius the Fjord data dictionary; I said I could get Meera the Fjord help-desk script sometime next week; Darius wrote the Fjord support playbook; R…  
  predicted: Darius sent the Fjord support playbook; loop done; Asked Ratna to book faculty onboarding sessions; she agreed; Ratna confirmed she drafted the load test plan on 2027-09-02; Meera asked me to look in…
- gen-s4-w2 cp1 q-010 `project_loops` score 0.49 (base 0.56): What loops are open on Cairn platform?  
  gold: Set gateway rate limits for Cairn tenants; Review Nomvula's Cairn pilot charter; Send Darius the Cairn support model; Confirm the Cairn comms plan with Theresa  
  predicted: Review the Cairn model allow-list (suggested, not accepted); Publish the Cairn tenant onboarding guide (suggested); Set gateway rate limits for Cairn tenants; Review Nomvula's Cairn pilot charter; Re…

### sonnet B: 34 answers below 0.5

- gen-s10-w2-small cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on Translation Help Tool Selection since the end of Friday 27 August?  
  gold: Catrin asked me to review the translation help selection vendor comparison; I asked Amani for the Noris accessibility conformance report  
  predicted: Catrin Dang's THTS vendor comparison review raised at 30 Aug site visit recap; no owner agreed; Amani Xu (Holworth) said she'd send Aoife the Noris accessibility conformance report (relevance to THTS…
- gen-s10-w2-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with our programs manager?  
  gold: peer  
  predicted: abstain
- gen-s2-w1 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Tendai Santos?  
  gold: stakeholder  
  predicted: Client counterpart: Customer Service Manager at Selfell Public Works
- gen-s2-w1 cp1 q-011 `person_brief` score 0.00 (base 0.00): What am I working on with Imani Quaye?  
  gold: Imani Quaye owes me: Send Dina the notes from the inspection scheduling session; Imani Quaye is Account Executive at Torthen Civic  
  predicted: Imani Navarro (Director of Delivery) works with Dina across Mistral, Fennel, Funding Model, IRRD, pothole selection and the workshop. Dina owes Imani the IRRD findings summary, review of her pothole …
- gen-s3-w1 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Eleni?  
  gold: Send Eleni the referral triage discovery interview guide  
  predicted: []
- gen-s3-w1 cp1 q-010 `project_loops` score 0.00 (base 0.00): What loops are open on Rosix Enterprise Agreement?  
  gold: Draft our counter-proposal to Rosix; Send Alasdair the Rosix volume tiers; Send Alasdair the Rosix enterprise agreement term sheet  
  predicted: []
- gen-s4-w2 cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Tariq?  
  gold: Send Tariq the Friday status note for w/e 10 September  
  predicted: Weekly Friday status note (half page: moved/slipped/needs); next is w/e 10 Sep
- gen-s4-w2 cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Meera Bondarenko?  
  gold: peer  
  predicted: Colleague at Drayhurst (Head of Learning Services); works with Ottavio on Fjord, HCAD, HSRD, Open Courseware
- gen-s5-small cp1 q-001 `focus_tomorrow` score 0.00 (base 0.00): What should I focus on tomorrow?  
  gold: Review Anahit's Wagtail service blueprint  
  predicted: Review Anahit's Wagtail service blueprint (she asked for it by 31 Mar; Hiba only said 'thanks for flagging'); Send Rike the Wagtail RACI chart (Rike needs it by Thu 1 Apr; Hiba earlier said next week…
- gen-s5-small cp1 q-008 `project_attr` score 0.00 (base 0.00): What is currently blocking Wagtail?  
  gold: real patient data paused pending the security review  
  predicted: abstain
- gen-s5-small cp1 q-009 `person_attr` score 0.00 (base 0.00): What is my working relationship with Rodrigo Okada?  
  gold: executive  
  predicted: abstain
- gen-s6-w1 cp1 q-005 `owed_to_me` score 0.00 (base 0.00): What does Rike currently owe me?  
  gold: Send Despina the notes from the research computing session  
  predicted: abstain
- gen-s9-large cp1 q-003 `project_changes` score 0.00 (base 0.00): What changed on the Kasane/Clelera evaluation since the end of Friday 29 October?  
  gold: I said I could get Adebayo the bed management selection pricing comparison sometime next week; I promised Anh the bed management selection pricing comparison; …  
  predicted: Aroha promised pricing comparison to Anh on 1 Nov; on 2 Nov pricing comparison is needed by Adebayo by Thu 4 Nov (Aroha 'got it'); email draft em-0118 unsent; Decision memo for bed management selecti…
- gen-s9-large cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Winifred Tanaka?  
  gold: Introduce Winifred to Anh for the referral triage work  
  predicted: []
- gen-s9-large cp1 q-009 `person_attr` score 0.00 (base 0.00): Which organization is Mikayla Babic with?  
  gold: Network Digital Office  
  predicted: Kirkmarsh Health Partners
- gen-s9-large cp1 q-015 `project_attr` score 0.00 (base 0.00): What is currently blocking Cirrus?  
  gold: real patient data paused pending the security review  
  predicted: Waiting on a vendor fix (Cirrus support playbook)
- gen-s9-large cp1 q-016 `person_attr` score 0.00 (base 0.00): What is my working relationship with Mathieu Wijaya?  
  gold: peer  
  predicted: Colleague at NDO: Principal, Integration Platform; owns Kittiwake and supplies Cirrus/hiring inputs to Aroha
- pilot cp1 q-004 `i_owe` score 0.00 (base 0.00): What do I currently owe Hugo?  
  gold: Send Hyun-woo the Tinderbox security review package  
  predicted: Tinderbox security review package (architecture, data flows, retention, sub-processor list) - draft unsent, needs sub-processor list and finishing retention section; Hugo gave no date
- pilot cp1 q-007 `owed_to_me` score 0.00 (base 0.00): What does Sol owe me?  
  gold: Collect two references for Mateus  
  predicted: Reference checks (two references) for Mateus Okonedo, REQ-2207, starting Wed 3 Mar, then Sade's decision
- pilot cp1 q-013 `i_owe` score 0.00 (base 0.00): What do I owe Sade?  
  gold: Send Sade the weekly AI & Data update (week of 1 March); Send Sade a one-page chargeback summary for the Council of Campus CIOs  
  predicted: Weekly update email 'Weekly update: w/e 5 Mar' (three bullets + one risk); Council of CIOs one-pager (3 bullets + 1 risk, lead with the conditional; to Sade only); Convene Sade + Bart Ngata on Tinder…
- pilot cp1 q-014 `project_changes` score 0.07 (base 0.07): What changed on Tinderbox since last Friday?  
  gold: Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931); Saanvi's load-test plan is done; she'll run it once the tenan…  
  predicted: Hosting decided: shared Kettleyard tenant (option 2); ARB rejected spec v1; wants event-based API; Dmitri's 5 Mar date void, now 10 Mar conditional on spec v2 (Mara due 4 Mar); KSD-20931 group claims…
- pilot cp1 q-008 `person_brief` score 0.08 (base 0.08): I'm meeting Delphine on Thursday. What am I working on with her?  
  gold: Shared project: Writing Feedback Tool Selection (Delphine Arceneaux is sponsor); Shared project: Saltmarren Transfer Evaluation Discovery (Delphine Arceneaux i…  
  predicted: Check-in with Delphine Arceneaux Thu 4 Mar 11:00 (video). Agenda: scorecard summary (Scrivelo vs Penmarq), DSA, and what Mara saw at the transfer-eval site visit. Keep asks small (she's overloaded).
- gen-s2-w1 cp1 q-003 `project_changes` score 0.18 (base 0.19): What changed on Mistral since the end of Saturday 6 March?  
  gold: I promised Cassandra the Mistral vendor comparison; I sent Imani the Mistral change request; I said I could get Yael the Mistral retention schedule sometime ne…  
  predicted: Mistral change request v1 sent to Imani (scope unchanged); Standup held, Yael prefers not to escalate yet; Duplicate notifications issue: Dina to look; vendor comparison owed; Mistral review schedule…
- gen-s5-small cp1 q-010 `project_loops` score 0.18 (base 0.19): What loops are open on Falbury Clinical Documentation Discovery?  
  gold: Send Hiba the clinical documentation discovery opportunity list; Present the clinical documentation discovery readout to Falbury; Share the clinical documentat…  
  predicted: Present readout to Falbury with Anahit; Opportunity list from Anahit; Findings summary from Anahit; Decide whether referral backlog becomes its own effort
- gen-s5-small cp1 q-002 `project_status` score 0.27 (base 0.31): What is the status of the Falbury pilot?  
  gold: Wagtail is active; Current phase: readiness; Next step on Wagtail: go-live checklist; Current blocker: real patient data paused pending the security review; Cu…  
  predicted: Assuming the Falbury pilot is Wagtail (AI prior-auth triage on Okapi, owner Isla Faure): in readiness phase as of 25 Mar with no blockers; security review held 24 Mar; pilot limited to four wards; ta…
