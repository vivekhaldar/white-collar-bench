"""Episode day 2: Tuesday 2027-03-02 (checkpoint cp1 at end of day)."""

from dsl import art, commit, cres, cupd, decide, fact
from names import *  # noqa: F403

D = "2027-03-02"

art("T01", "email", f"{D} 07:00", "Reminder: interview feedback for Mateus Okonedo is pending", [
    "p-recruit-bot", ("c:panel-scorecard", "direct", "panel scorecard for Mateus Okonedo still pending in TarrowRecruit")],
    frm=["TarrowRecruit Notifications <noreply@recruit.tarrow.example>"], to=a(M), low_value=True, length="short",
    challenges=["duplicate_signal"],
    style="Automated ATS reminder: 'You have 1 pending panel scorecard: Mateus Okonedo - Staff ML Engineer (REQ-2207). "
          "Status: pending since 1 Mar 2027.' Button text 'Submit feedback'. Boilerplate footer.")

art("T18", "email", f"{D} 06:30", "[All Staff] Multi-factor sign-in becomes mandatory on 15 March", ["p-tus-itservices"],
    frm=["Tarrow IT Services <itservices@tarrow.example>"], to=["all-staff@tarrow.example"], noise=True, length="medium",
    challenges=["noise"],
    noise_notes="System-wide IT notice: MFA enforcement date, link to an enrollment guide, help-desk hours, a reminder that "
                "IT will never ask for your password. Nothing about any project.",
    style="All-staff notice, bulleted, with a 'Do not reply to this message' footer.")

art("T02", "chat", f"{D} 07:45", "DM Delphine / Mara: parking", [],
    participants=n(DELPH, M), length="short", noise=True, challenges=["noise"],
    noise_notes="Logistics only: visitor parking lot C, sign in at the front desk, coffee. No project content.",
    style="DM. Delphine 07:44: 'morning! visitor parking is lot C, sign in at the front desk, coffee's on us ☕'. Mara 07:45: "
          "'ty, see you at 10'.")

art("T20", "transcript", f"{D} 08:32", "ODS leads call (weekly)", [
    ("c:ilya-v4", "second-hand", "'Ilya: reference architecture v4 by end of week'"),
    ("c:cb-options", "second-hand", "'Sade: Mara's chargeback options at 4pm today'")],
    participants=n(SADE, M, RAMONA, ILYA, HW, BETT, LUCIA), sent=f"{D} 08:30",
    length="medium", challenges=["alias", "duplicate_signal"],
    noise_notes="Mostly round-the-table updates with no new asks: Lucía's offsite logistics (bus at 07:30 Wednesday, no "
                "laptops), Bettina's product roadmap review moving a week, Hyun-woo's review queue, Ramona's workshop "
                "registrations.",
    style="WebVTT auto-transcript of the 30-minute weekly leads call, 08:00-08:30; NOTE attendee list mangles two names: "
          "'Hyunwoo Parks' and 'Betina O'Dwyer'. Round-the-table, lots of backchannel. Sade: 'all principals at the "
          "leadership offsite Wednesday; Ilya covers Kettleyard ops'; 'Mara's chargeback options at 4pm today'. Ilya: "
          "'reference architecture v4 by end of week'. Speaker labels: Lucía joins from a room device 'ODS-SMALL-CONF'. No "
          "action items.")

commit("pia", f"{D} 08:05", "ask", "Complete the Tinderbox privacy impact assessment (PIA) questionnaire", M, HANA,
       project=LAN, due="2027-03-12", basis="received", keywords=["PIA", "privacy impact assessment"],
       summary="Hana, Kestrow's new privacy officer, asked me to complete the Tinderbox PIA questionnaire by 12 March")
commit("pia-walk", f"{D} 08:05", "ask", "Walk Hana through Tinderbox's data flows for the PIA", M, HANA, project=LAN,
       basis="received", keywords=["PIA walkthrough", "data-flow walkthrough"],
       summary="Hana also asked me to set up a 30-minute data-flow walkthrough for the PIA")
art("T03", "email", f"{D} 08:05", "Introduction: Tinderbox privacy review (PIA)", [HANA, "c:pia", "c:pia-walk"],
    frm=a(HANA), to=a(M, YUSRA), length="medium", challenges=["new_entity", "alias"],
    style="Formal introduction from the new privacy officer: 'I joined Kestrow as Privacy Officer last week.' Explains the "
          "campus privacy impact assessment (PIA) process; asks Mara to complete the attached PIA questionnaire for Tinderbox "
          "'by Friday 12 March'. Second ask: 'Could you also set up a 30-minute data-flow walkthrough with me before you "
          "fill it in? Think of it as a PIA walkthrough.' Notes real student data cannot be processed until both the PIA and "
          "the security review are complete. Signature: Hana Kobayashi-Reyes, Privacy Officer, TU Kestrow.")

cupd("sadebart-xfer", f"{D} 08:33", "sadebart",
     {"debtor": LUCIA, "creditor": M, "what": "Book a meeting with Sade and Bart Ngata on Tinderbox ownership"},
     "Handed the Sade / Bart Ngata ownership meeting to Lucía to book")
art("T04", "chat", f"{D} 08:33", "DM Mara / Lucía: Sade + Bart Ngata", ["sadebart-xfer"],
    participants=n(M, LUCIA), length="short", challenges=["transfer", "name_collision"],
    style="DM. Mara 08:31: 'can you find 45 min w/ sade + bart ngata re tinderbox ownership? this wk or next'. Lucía 08:33: "
          "'Sade's at the leadership offsite tomorrow too - I'll look at Thu/Fri. Invite to follow!' Signs nothing.")

cres("onboarding-done", f"{D} 08:50", "onboarding", "done", "Ingrid booked Tinderbox faculty onboarding sessions for 8-10 March")

# ---------------------------------------------------------------- Tinderbox standup (Mara dials in from the car)
cupd("ctx-due1", f"{D} 09:20", "context-api", {"due": "2027-03-10"},
     "Dmitri moved the context API to 10 March (needs spec v2)")
cres("tenant-done", f"{D} 09:22", "tenant", "done", "Bartosz: the Tinderbox tenant on Kettleyard is live")
fact("lan-s4", f"{D} 09:35", LAN, "summary",
     "The Tinderbox tenant on Kettleyard went live on 2 March. Dmitri now targets 10 March for the context API, pending "
     "my spec v2. Faculty onboarding sessions are booked for 8-10 March and Saanvi plans the load test for 3 March. Still "
     "in dummy-data mode pending the security package; SSO group claims still wait on the IdP patch. Hana, Kestrow's new "
     "privacy officer, wants a PIA by 12 March. Go-live 29 March.",
     "Tinderbox tenant live; context API now 10 March")
art("T06", "transcript", f"{D} 09:35", "Tinderbox standup (Tue)", [
    "ctx-due1", "tenant-done", ("c:load-test", "direct", "Saanvi: load test tomorrow at ten now the tenant is up"), "lan-s4",
    ("onboarding-done", "second-hand", "Yusra: 'Ingrid booked onboarding for the 8th, 9th and 10th - CHEM, HIST, BIOL, Library Room 2.14'"),
    ("c:group-claims", "direct", "Teo: claims still pending"),
    ("c:pia", "second-hand", "Yusra: 'and the new privacy officer, Hana, wants a PIA by the 12th'")],
    participants=n(YUSRA, DIMA, SAANVI, TEO, BARTOSZ, M), sent=f"{D} 09:31", length="short",
    challenges=["supersession", "alias", "name_collision", "duplicate_signal"],
    noise_notes="Road noise; Dmitri complains about the coffee machine; Yusra asks if anyone saw the hockey game.",
    style="Short WebVTT (16 min). NOTE attendee list auto-generated with the misspelling 'Teo Lisofsky'. Mara is on a phone in "
          "a car (road noise, '[inaudible]'). Dmitri: 'with the event-based v2 I can do the context API by the 10th.' "
          "Bartosz drops in: 'tenant's live as of this morning'. Saanvi: 'then load test tomorrow at ten.' Speaker drift: "
          "Teodor's label changes from 'Teodor Lisowski' to 'Teo L (iPad)'. Yusra calls Bartosz 'Bart'. Ends at 09:31 with "
          "Mara: 'I'm losing signal, pulling into Saltmarren.'")

art("T07", "meeting_notes", f"{D} 09:48", "Huddlescribe recap: Tinderbox standup", [
    ("ctx-due1", "second-hand"), ("tenant-done", "second-hand"), ("c:load-test", "second-hand", "load test Wed 10:00 (Saanvi)"),
    ("refarch-done", "second-hand", "WRONG DATE: claims Mara sent Ilya her reference-architecture comments 'today (Tue)'")],
    frm=["Huddlescribe Recaps <recaps@huddlescribe.example>"], participants=n(YUSRA, DIMA, SAANVI, TEO, BARTOSZ, M),
    length="short", challenges=["alias", "correction"],
    style="AI recap. Repeats ASR misspelling 'Teo Lisofsky' ('Teo Lisofsky: group claims pending vendor'). Wrongly states "
          "'Mara sent Ilya her reference-architecture comments today' (they were sent Monday 1 March). Lists: context API "
          "10 Mar (Dmitri), tenant live (Bart), load test Wed 10:00 (Saanvi). Disclaimer 'AI-generated, may contain errors'.")

fact("hub-s2", f"{D} 10:22", HUB, "summary",
     "The Tinderbox tenant (tinderbox-kes-01) went live on 2 March, Kettleyard's first production tenant. My comments on "
     "reference architecture v3 went to Ilya on 1 March; v4 is pending.",
     "Kettleyard: first tenant live")
fact("hub-next2", f"{D} 10:22", HUB, "next_step", "Publish reference architecture v4", "Kettleyard next step: v4 of the reference architecture")
art("T08", "chat", f"{D} 12:40", "#kettleyard: Tinderbox tenant live", [
    "hub-s2", "hub-next2", ("tenant-done", "direct", "tenant id tinderbox-kes-01 is live")],
    participants=n(BARTOSZ, ILYA, M), length="short", challenges=["privacy", "name_collision", "duplicate_signal"],
    secrets=["kyd_live_4f9a2c71e8b04d3aa6e1c0d2"],
    style="Bartosz (@bart) 10:18: 'tinderbox tenant live ✅ tenant id tinderbox-kes-01'. Bartosz 10:19: 'smoke test key: "
          "kyd_live_4f9a2c71e8b04d3aa6e1c0d2'. Bartosz 10:20: 'oops wrong window - rotating that'. Ilya 10:21: '🙄 pls do. "
          "next up: v4 of the ref arch'. Mara (on site at Saltmarren) only adds a 👍 reaction at 12:40; she posts nothing. "
          "(He says 'rotating' but nothing confirms it was rotated.)")

# ---------------------------------------------------------------- Scrivelo chases (salesy follow-up)
art("T19", "email", f"{D} 10:45", "Circling back: next steps for Saltmarren + our ACR", [
    ("c:scrivelo-acr", "direct", "'our compliance team will send the accessibility conformance report (ACR) by Friday'"),
    ("c:scrivelo-api", "direct", "'Hannah is finishing the LMS integration API documentation'")],
    frm=a(GREG), to=a(M), cc=a(DELPH, HANNAH), low_value=True, length="medium", challenges=["alias", "duplicate_signal"],
    noise_notes="Mostly sales boilerplate: a customer quote from another (fictional) college, a webinar plug, a booking link.",
    style="Salesy follow-up. 'Just circling back on next steps for Saltmarren! Our compliance team will send the accessibility "
          "conformance report (ACR) by Friday. Hannah is finishing the LMS integration API documentation. I've also sent you a "
          "calendar invite for Friday 11:00 to walk through implementation - happy to move it.' Signs 'Grig' with a "
          "calendar booking link.")

# ---------------------------------------------------------------- Saltmarren site visit 10:00-12:30
cres("interviews-done", f"{D} 12:30", "interviews", "done", "Interviewed Saltmarren transfer evaluators on the site visit")
commit("wait-data", f"{D} 12:00", "task", "Analyze Saltmarren advising appointment wait-time data", M, TILLIE,
       project=TCE, basis="reported", keywords=["wait-time", "advising appointment"],
       summary="Promised Tillie (advising) a quick look at advising appointment wait-time data")
commit("usecase", f"{D} 12:10", "ask", "Send Delphine the writing-feedback use-case list from the discovery", M, DELPH,
       project=WFT, basis="reported", keywords=["use-case list", "writing feedback"],
       summary="Delphine asked for the writing-feedback use-case list from the discovery to prioritize the bake-off")
fact("tce-ph2", f"{D} 12:40", TCE, "phase", "discovery (scope widening)", "Saltmarren discovery scope widening to advising scheduling")
fact("tce-next2", f"{D} 12:40", TCE, "next_step", "Get the data-sharing agreement signed so the baseline sample can flow",
     "Next step on the transfer discovery: get the DSA signed")
fact("tce-s2", f"{D} 12:40", TCE, "summary",
     "Site visit on 2 March: interviewed evaluators with Rufus and Delphine. A second problem surfaced from Tillie in "
     "advising: transfer students wait weeks for advising appointments, which delays their evaluations. I'm looking at "
     "advising wait-time data and owe Delphine a writing-feedback use-case list. Baseline data is still blocked on the "
     "unsigned DSA. Readout targeted for 19 March.",
     "Saltmarren site visit surfaced an advising scheduling problem")
art("T09", "meeting_notes", f"{D} 12:45", "Debrief: Saltmarren site visit", [
    TILLIE, "interviews-done", "c:wait-data", "c:usecase", "tce-ph2", "tce-next2", "tce-s2",
    ("c:baseline-sample", "direct", "sample still blocked on the DSA"),
    ("c:baseline-analysis", "direct", "'baseline analysis = still me, still blocked'")],
    frm=a(M), participants=n(M, DELPH, RUFUS, TILLIE), sent=f"{D} 12:45", length="medium",
    challenges=["new_entity", "alias", "implied_commitment"],
    must_not_say=["Tillie's surname or full first name 'Ottilie' (she is known only as 'Tillie from advising' here)"],
    noise_notes="Aside: 'their coffee is better than ours'; a note about the registrar office's new queue kiosk.",
    style="Mara's debrief, Markdown bullets. Met Delphine ('interim registrar'), Rufus, and 'Tillie from advising' (first name "
          "only). Evaluators: 3 interviewed; equivalency lookup is the time sink. 'Tillie: real bottleneck is advising appts - "
          "transfer students wait ~3 wks before anyone looks at their transcripts. → promised her a quick look at the wait "
          "data.' 'Delphine wants the writing-feedback use-case list to prioritize the bake-off.' 'baseline analysis = still "
          "me, still blocked till sample (DSA unsigned) → next: get the DSA signed.'")

cupd("specv2-due", f"{D} 12:55", "spec-v2", {"due": "2027-03-04"}, "Promised Dmitri spec v2 by Thursday 4 March")
art("T10", "chat", f"{D} 12:55", "DM Dmitri / Mara: spec churn", ["specv2-due"],
    participants=n(DIMA, M), length="short", challenges=["alias"],
    style="DM, lowercase. Dmitri 12:44: 'third rewrite of this contract. if v2 moves again after i start i'm out lol (not lol)'. "
          "Dmitri 12:45: 'when's v2 landing?' Mara 12:55: 'thu. event-based, per jack's ARB notes. won't move after that.' "
          "Dmitri: 'holding you to it'.")

commit("internal-build", f"{D} 13:15", "ask", "Add an internal-build (Kettleyard) option column to the vendor scorecard",
       M, LIONEL, project=WFT, accepted=False, basis="received", keywords=["internal-build", "build-vs-buy"],
       summary="Lionel asked for an internal-build option column in the scorecard")
cupd("internal-build-acc", f"{D} 14:02", "internal-build", {"accepted": True},
     "Agreed to add Lionel's internal-build column to the scorecard")
art("T11", "email", f"{D} 14:02", "Re: Huddlescribe recap: Pen Mark demo", [
    "c:internal-build", "internal-build-acc", ("c:support-handoff", "direct", "support model is with Bettina; will be in the requirements")],
    frm=a(M), to=a(LIONEL), cc=a(DELPH), thread=["M08"], sent=f"{D} 14:02", length="medium",
    challenges=["correction", "endorsement", "alias"],
    style="Mara's reply on top, quoting Lionel's 13:15 email in full. Lionel (quoted): 'For the record, I did not sign up to "
          "draft an internal build estimate - the recap invented that. What I do want: an internal-build option in the "
          "scorecard (a build-vs-buy column), and an answer on who supports this after the vendor's implementation team "
          "leaves.' Mara: 'fair - I'll add an internal-build column. support model: Bettina raised the same thing, it'll be "
          "in the RFQ requirements.'")

cres("proc-path-done", f"{D} 14:36", "proc-path", "done", "Clement confirmed the writing tool needs an RFQ")
commit("rfq-reqs", f"{D} 14:36", "ask", "Draft the RFQ requirements section for the writing feedback tool", M, CLEM,
       project=WFT, due="2027-03-09", basis="received", keywords=["RFQ", "requirements section"],
       summary="Clement needs my RFQ requirements section by Tue 9 March")
fact("wft-ph2", f"{D} 14:36", WFT, "phase", "demos and RFQ prep", "Writing-tool selection now needs an RFQ")
fact("u:wft-budget", f"{D} 14:30", WFT, "budget", "90000 USD not-to-exceed", "Writing-tool budget ceiling set",
     unobservable="Clement only ever says 'the ceiling we discussed'")
art("T12", "email", f"{D} 14:36", "Writing feedback tool: procurement path", ["proc-path-done", "c:rfq-reqs", "wft-ph2"],
    frm=a(CLEM), to=a(M), cc=a(DELPH), thread=["S05"], length="medium", challenges=["unobservable"],
    must_not_say=["any budget or ceiling amount"],
    style="Careful procurement voice: 'This exceeds the informal quote threshold (policy PR-4.2), so we need an RFQ; the "
          "cooperative contracts don't cover writing-feedback tools. Please send me the requirements section by Tuesday "
          "9 March so I can issue the RFQ. Pricing must stay within the budget ceiling we discussed.' Signs 'Clement'.")

cres("cb-options-done", f"{D} 15:26", "cb-options", "done", "Sent Sade the chargeback options paper ahead of the review")
fact("cb-ph2", f"{D} 15:26", CB, "phase", "options review", "Chargeback options delivered to Sade")
art("T13", "chat", f"{D} 15:31", "DM Mara / Sade: options paper", ["cb-options-done", "cb-ph2"],
    participants=n(M, SADE), length="short", challenges=["alias"],
    style="DM. Mara 15:26: 'options paper for the 4pm attached - A flat per-campus fee, B consumption-based, C hybrid. on the "
          "rebased FTEs (v2). I recommend C.' (file attached). Sade 15:31: 'Got it. Three bullets and one risk when you "
          "present, please.'")
art("T14", "document", f"{D} 15:31", "Kettleyard cost-sharing options v1", [("cb-options-done", "direct", "the options paper")],
    ext="docx", parent="T13", sent=f"{D} 15:26", length="medium",
    style="Word memo, 3 pages. Options A (flat per-campus fee), B (consumption-based on gateway tokens), C (hybrid: base fee "
          "+ consumption). Uses FTE v2 (Orrin Valley 9,400). Table of illustrative per-campus shares in percent only (no "
          "dollar totals). Recommendation: C. No savings-target figure.")

decide("cb-condition", f"{D} 16:20", "Make Tinderbox expansion beyond Kestrow conditional on campuses agreeing to Kettleyard chargeback",
       [SADE], project=CB, keywords=["expansion", "conditional", "chargeback"],
       summary="Sade decided Tinderbox expansion beyond Kestrow is conditional on campuses agreeing to chargeback")
commit("onepager-sade", f"{D} 16:25", "ask", "Send Sade a one-page chargeback summary for the Council of Campus CIOs", M,
       SADE, project=CB, due="2027-03-10", basis="reported", keywords=["one-pager", "Council of Campus CIOs"],
       summary="Sade wants a one-page chargeback summary for the Council by Wednesday next week (10 March)")
fact("u:savings-target", f"{D} 16:10", CB, "savings_target", "12% reduction in campus AI tool spend by FY28",
     "Sade's savings target for the chargeback model", unobservable="Sade only refers to 'the target I'm holding us to'")
fact("cb-next2", f"{D} 16:30", CB, "next_step", "One-page Council summary to Sade by 10 March, ahead of the 12 March Council",
     "Chargeback next step: the Council one-pager")
fact("cb-s2", f"{D} 16:30", CB, "summary",
     "Options paper delivered 2 March (A flat fee, B consumption-based, C hybrid; I recommend C). At the review Sade said "
     "she leans toward B but only decided that Tinderbox expansion beyond Kestrow is conditional on campuses agreeing to "
     "chargeback. She set a disclosure limit: nothing on the options goes to campuses in writing before the Council, and "
     "conversations with campus CFOs stay verbal. Percy says there is no FY28 money for Kettleyard unless someone owns the "
     "cost. I owe Sade a one-pager for the 12 March Council of Campus CIOs by 10 March.",
     "Chargeback: expansion made conditional on campuses agreeing")
art("T15", "transcript", f"{D} 16:40", "Chargeback options review", [
    "d:cb-condition", "c:onepager-sade", "cb-next2", "cb-s2"],
    participants=n(SADE, M, RAMONA, PERCY), sent=f"{D} 16:31", length="long",
    challenges=["unobservable", "implied_commitment"],
    must_not_say=["the numeric savings target", "any percentage presented as Sade's target"],
    noise_notes="Ramona and Percy trade a joke about the vending machine; Sade's phone buzzes twice.",
    style="WebVTT whose first cue starts mid-sentence (opening minutes missing: '...so that's why the hybrid'). Sade states a "
          "preference that is NOT a decision: 'I lean toward option B, but I'm not deciding the model today.' Then: 'Here's "
          "what I am deciding: no expansion of Tinderbox beyond Kestrow until the campuses sign up to chargeback.' Disclosure "
          "limit from Sade: 'Nothing on these options goes to the campuses in writing before the Council. Conversations with "
          "campus CFOs stay verbal.' Percy, as a fact: 'There's no FY28 money for Kettleyard unless someone owns the cost.' "
          "Ramona: 'we'll loop in the campus CFOs' (collective, no owner - not a commitment). Sade: 'you know the target I'm "
          "holding us to' (no number). Sade: 'Mara, one page for the Council - three bullets and one risk - by Wednesday next "
          "week.' Mara: 'will do.'")

commit("ramona-cover", f"{D} 17:45", "ask", "Cover the Wednesday Tinderbox standup while Mara is at the offsite", RAMONA, M,
       project=None, status="waiting", basis="reported", keywords=["cover the Tinderbox standup", "offsite"],
       summary="Ramona is my delegate on Wednesday: she'll cover the Tinderbox standup and workshop logistics")
cres("panel-scorecard-done", f"{D} 17:30", "panel-scorecard", "done", "Submitted my panel scorecard for Mateus in TarrowRecruit")
commit("refs", f"{D} 17:40", "task", "Collect two references for Mateus", SOL, M, project=HIRE, status="waiting",
       basis="reported", keywords=["two references", "reference checks"],
       summary="Marisol is starting two reference checks for Mateus")
fact("hire-ph3", f"{D} 17:40", HIRE, "phase", "references", "MLE hire moved to references after the panel")
art("T16", "note", f"{D} 17:52", "Tue eve", [
    "c:ramona-cover", "panel-scorecard-done", "c:refs", "hire-ph3",
    ("c:secpkg", "direct", "'sec pkg: draft is in my drafts, needs the sub-processor list'")],
    frm=a(M), length="short", challenges=["worker_directive"],
    style="Shorthand: 'wed = leadership offsite all day, no laptop. delegate: Ramona to cover the tinderbox standup + workshop "
          "logistics; Ilya for kettleyard questions.' 'mateus panel scorecard → TarrowRecruit ✓ - Sol says all 3 in, she "
          "starts 2 reference checks tmrw'. 'sec pkg: draft is in my drafts, needs the sub-processor list'. 'deck v2 "
          "tomorrow early'.")

art("T17", "email", f"{D} 22:47", "DRAFT: Tinderbox security review package", [],
    frm=a(M), to=a(HW), cc=a(YUSRA), length="short", challenges=["draft_vs_sent"],
    must_not_say=["anything suggesting it was sent; no attachment is present"],
    style="Header 'X-Draft: true', no Message-ID sent status. Body: 'Hyun-woo - attached is the Tinderbox security review "
          "package: architecture, data flows, retention. [TODO: attach pkg + sub-processor list]' Unfinished last sentence.")
