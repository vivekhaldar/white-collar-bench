"""Episode day 1: Monday 2027-03-01."""

from dsl import art, commit, cres, decide, fact
from names import *  # noqa: F403

D = "2027-03-01"
NOFOLD = "Do NOT fold long iCalendar lines: keep DESCRIPTION and any join link on one line each. "

# ---------------------------------------------------------------- early morning
commit("weekly-0305", f"{D} 06:58", "task", "Send Sade the weekly AI & Data update (week of 1 March)", M, SADE,
       project=None, due="2027-03-05", basis="received", keywords=["weekly update", "5 March"],
       summary="ODS mailbox reminder: this week's update to Sade is due Fri 5 March")
art("M01", "email", f"{D} 06:58", "Reminder: weekly VC updates due Friday 5 March", ["c:weekly-0305"],
    frm=["ODS Team <ods-team@tarrow.example>"], to=["ods-staff@tarrow.example"], low_value=True, length="short",
    challenges=["alias"],
    noise_notes="Boilerplate reminder; also plugs the staff coffee rota and a lost-umbrella notice.",
    style="Same Monday-reminder template as the 22 Feb one: 'Friendly reminder: weekly updates to the VC are due Friday "
          "5 March (three bullets + one risk).' Signed '— ODS Team'. Footer 'This mailbox is monitored during business hours.'")

art("M02", "email", f"{D} 07:12", "The Lattice Ledger: campus AI procurement, week of 1 March", ["p-lorne-castellan"],
    frm=["Lorne Castellan <lorne@latticeledger.example>"], to=a(M), noise=True, length="medium", challenges=["noise"],
    noise_notes="Higher-ed tech newsletter. Generic items: AI procurement trends, a fictional consortium survey, an op-ed on "
                "chargeback models in general (no Tarrow content). Must not mention any Tarrow person or project.",
    style="Newsletter with three short stories and an unsubscribe footer.")

decide("option2", f"{D} 07:40", "Host Tinderbox in the shared Kettleyard tenant (option 2) instead of a dedicated Kestrow deployment (option 1)",
       [M], project=LAN, keywords=["option 2", "shared tenant", "Kettleyard"],
       summary="Decided: Tinderbox goes on the shared Kettleyard tenant (option 2), not a dedicated Kestrow deployment")
cres("opt1-drop", f"{D} 07:40", "opt1-pricing", "dropped", "Joaquín's option 1 pricing no longer needed after choosing option 2")
art("M03", "note", f"{D} 07:40", "Mon notes", [
    "d:option2", "opt1-drop",
    ("c:refarch-review", "direct", "'v3 comments → Ilya today'"),
    ("c:cb-options", "direct", "'chargeback options before the sade review'")],
    frm=a(M), length="short", challenges=["worker_directive", "alias"],
    noise_notes="One stray line: 'dentist moved to the 17th'.",
    style="Shorthand, lowercase: 'tinderbox hosting: go with option 2 (kettleyard shared tenant). tell jack to stop pricing "
          "option 1.' Then 'this wk:' list: 'v3 comments → ilya (today)', 'sec pkg??', 'chargeback options before the sade review', "
          "'deck v2', 'penmarq demo 11'. No reasons given beyond 'cheaper + one less thing to run'.")

commit("deck-v2", f"{D} 08:55", "task", "Send Ramona the workshop deck v2", M, RAMONA, project=WS, due="2027-03-03",
       basis="received", keywords=["deck v2", "Wednesday noon"],
       summary="Ramona needs workshop deck v2 by Wednesday noon (the '5am tomorrow' was a joke)")
commit("dashboard", f"{D} 08:56", "ask", "Send Ramona three lines on Tinderbox for the program dashboard (week of 1 March)", M, RAMONA,
       project=LAN, basis="received", keywords=["program dashboard", "three lines"],
       summary="Ramona asked me for three lines on Tinderbox for the program dashboard")
cres("dashboard-done", f"{D} 17:30", "dashboard", "done", "Sent Ramona the Tinderbox lines for the program dashboard")
art("M04", "chat", f"{D} 17:35", "DM Ramona / Mara: deck v2, dashboard", ["c:deck-v2", "c:dashboard", "dashboard-done"],
    participants=n(RAMONA, M), length="short", challenges=["supersession", "alias"],
    noise_notes="Opens with Ramona asking whether Mara got snowed in over the weekend; Mara: 'nope, just cold'.",
    style="DM thread exported at end of day. Ramona 08:52: 'quick one: need deck v2 by 5am tomorrow 😇'. Ramona 08:53: "
          "'kidding!! realistically wednesday noon? need it before I print handouts'. Mara 08:55: 'wed noon works'. (The joke "
          "deadline is corrected within the same exchange.) Ramona 08:56: 'also 3 lines on Tinderbox for the program dashboard "
          "by EOD?' Mara 08:57: 'yep'. Mara 17:30: 'dashboard lines: hosting = kettleyard shared tenant; ARB wants spec v2; "
          "real data still paused.' Ramona 17:35: 'perfect ty'.")

# ---------------------------------------------------------------- Tinderbox standup 09:15
commit("spec-v2", f"{D} 09:25", "task", "Rewrite the Tinderbox interface spec as v2 (event-based context API)", M, JACK,
       project=LAN, basis="reported", keywords=["spec v2", "event-based"],
       summary="ARB rejected spec v1; I said I'd turn around an event-based v2")
commit("secpkg", f"{D} 09:32", "task", "Send Hyun-woo the Tinderbox security review package", M, HW, project=LAN,
       basis="reported", keywords=["security review package", "security package"],
       summary="I said I'd pull the Tinderbox security review package together for Hyun-woo, probably this week")
fact("lan-bl3", f"{D} 09:38", LAN, "blocker",
     "Real student data paused pending security review; interface spec v1 rejected by the Kestrow ARB; SSO group claims not released (KSD-20931)",
     "Tinderbox blockers now include the ARB's rejection of spec v1")
fact("lan-s3", f"{D} 09:38", LAN, "summary",
     "Still in dummy-data mode pending the security review; I am assembling the security review package for Hyun-woo. "
     "Kestrow's architecture review board rejected interface spec v1 (it wants an event-based context API), so I am "
     "rewriting it as v2 and Dmitri's 5 March date for the context API no longer holds. Hosting is decided: option 2, "
     "the shared Kettleyard tenant, which Bartosz is still provisioning. SSO group claims still wait on an IdP vendor patch. "
     "Go-live 29 March.",
     "Tinderbox: spec v1 rejected, hosting on Kettleyard, security package in progress")
art("M05", "transcript", f"{D} 09:45", "Tinderbox standup (Mon)", [
    "c:spec-v2", "c:secpkg", "lan-bl3", "lan-s3",
    ("d:option2", "implied", "Yusra: 'you said option 2 this morning?' Mara: 'yes, shared tenant'"),
    ("c:group-claims", "direct", "Teo: still waiting on the IdP vendor patch for group claims"),
    ("c:load-test", "direct", "Saanvi: load test waits on the tenant"),
    ("c:runbook", "direct", "Greta: runbook in progress")],
    participants=n(YUSRA, JACK, DIMA, SAANVI, TEO, M, GRETA), sent=f"{D} 09:38", length="medium",
    challenges=["implied_commitment", "duplicate_signal", "alias"],
    noise_notes="First minute is small talk about the parking garage closure and Dmitri's new standing desk.",
    style="WebVTT, NOTE 'Tinderbox standup - Mon 1 Mar 2027' with auto-generated attendee list. Mostly first names in speech. "
          "Joaquín: 'ARB came back on the interface spec - they won't approve v1, they want an event-based context API.' "
          "Dmitri (frustrated): 'so the fifth is dead. third time the contract's changed.' Mara: 'I'll turn a v2 around.' "
          "(no date). Yusra: 'who's doing the security package for Hugo?' Mara: 'I'll pull it together, probably this week.' "
          "Teo mentions ticket KSD-20931 is still waiting on the IdP vendor. "
          "Speaker drift: Saanvi's label switches mid-file from 'Saanvi Raghunathan' to 'Speaker 4'. Greta joins at 00:06 "
          "under the device label 'KES-HUDDLE-2B' and is only identified when she says 'it's Greta'. Backchannel, one "
          "cross-talk. Ends early: Yusra 'I have to drop - let's take the rest offline.'")

# ---------------------------------------------------------------- ref arch feedback
cres("refarch-done", f"{D} 10:12", "refarch-review", "done", "Sent Ilya my 11 comments on Kettleyard reference architecture v3")
commit("ilya-v4", f"{D} 10:12", "task", "Send the revised Kettleyard reference architecture (v4)", ILYA, M, project=HUB,
       status="waiting", basis="sent", keywords=["reference architecture v4", "send me v4"],
       summary="Waiting on Ilya for v4 of the reference architecture")
art("M06", "email", f"{D} 10:12", "Re: Kettleyard reference architecture v3: review please", [
    "refarch-done", "c:ilya-v4"],
    frm=a(M), to=a(ILYA), cc=a(BETT, HW), thread=["S22"], length="long", challenges=["scattered_evidence"],
    must_not_say=["a concrete promise by Mara to schedule the follow-up sync (it is only a 'let's')"],
    style="Mara's review: 11 numbered comments on v3 (e.g. 3: gateway connection pooling has no back-pressure; 7: run-rate "
          "excludes egress; 9: secrets rotation cadence unspecified). Closes: 'Send me v4 when it's ready - and let's sync "
          "with Bettina once you've revised.' (collective 'let's', no owner, no date.) Quotes Ilya's 22 Feb ask below. Dated "
          "Monday 1 March.")

# ---------------------------------------------------------------- Penmarq demo 11:00
commit("scorecard", f"{D} 11:40", "ask", "Send Delphine the vendor scorecard summary", M, DELPH, project=WFT,
       basis="reported", keywords=["scorecard summary", "vendor scorecard"],
       summary="Delphine asked me for a vendor scorecard summary this week")
fact("wft-mem2", f"{D} 11:48", WFT, "members", [M, DELPH, CLEM, LIONEL, CORWIN],
     "Corwin (Saltmarren writing center) joins the writing-tool evaluation")
art("M07", "transcript", f"{D} 11:50", "Penmarq demo", [
    CALLUM, CORWIN, "c:scorecard", "wft-mem2",
    ("c:no-training", "direct", "Delphine presses: 'will you commit contractually to no training on student essays?' "
                                "Juniper: 'I'll check with our legal team.'"),
    ("c:penmarq-pricing", "direct", "Juniper: 'three-campus pricing is coming this week'"),
    ("c:sandbox-trial", "direct", "Mara: 'we'll get a couple of writing-center staff into the sandbox for two weeks'")],
    participants=n(JUNI, CALLUM, M, DELPH, LIONEL, CORWIN), sent=f"{D} 11:48", length="long",
    challenges=["alias", "duplicate_signal", "new_entity"],
    noise_notes="Two minutes of Juniper's slides on Penmarq's company history; a dog barks on Callum's line.",
    style="48-min auto transcript (WebVTT). The ASR consistently writes the vendor as 'Pen Mark' (e.g. 'welcome to Pen "
          "Mark'); NOTE header title says 'Penmarq demo'. Callum demos inline feedback. Corwin introduces himself as "
          "director of the Saltmarren writing center and says, hedging, 'honestly my tutors are slammed until after "
          "midterms' (no commitment). Delphine: 'will you commit contractually to no training on student essays?' Juniper: "
          "'I'll check with our legal team.' Lionel, as a preference only: 'honestly we could build this on Kettleyard "
          "ourselves' (no commitment). Delphine: 'Mara, can you get us a scorecard summary this week?' Mara: 'yes'. Callum: "
          "'I'll send sandbox access after the call.' Cut-off at the end (recording stops mid-sentence).")

commit("demo-notes", f"{D} 12:02", "task", "Circulate the Penmarq demo notes to the evaluation team", M, DELPH,
       project=WFT, accepted=False, basis="inferred", keywords=["demo notes", "circulate"],
       summary="Notetaker recap suggested I circulate the Penmarq demo notes (not agreed)")
art("M08", "meeting_notes", f"{D} 12:02", "Huddlescribe recap: Pen Mark demo", [
    "c:demo-notes", ("c:scorecard", "second-hand", "scorecard summary to Delphine this week"),
    ("c:no-training", "second-hand")],
    frm=["Huddlescribe Recaps <recaps@huddlescribe.example>"], participants=n(JUNI, CALLUM, M, DELPH, LIONEL, CORWIN),
    length="medium", challenges=["alias", "endorsement", "duplicate_signal"],
    must_not_say=["that Lionel actually agreed to anything - the invented item must read as a confident AI claim, not a quote",
                  "a specific weekday or date for the scorecard"],
    style="AI-generated recap (Markdown) from the notetaker 'Huddlescribe'. Repeats the ASR mangling 'Pen Mark' throughout. "
          "Sections Summary / Decisions (none) / Action items. Action items: 'Mara to send scorecard summary to Delphine this "
          "week'; 'Juniper to confirm no-training clause with legal'; 'Lionel to draft an internal build estimate' (INVENTED - "
          "nobody said this); 'Suggested: Mara to circulate demo notes to the evaluation team'. Disclaimer 'AI-generated, may "
          "contain errors'.")

cres("penmarq-vsq-done", f"{D} 13:24", "penmarq-vsq", "done", "Penmarq returned its security questionnaire (late)")
art("M09", "email", f"{D} 13:24", "Penmarq sandbox access + completed questionnaire", [
    "penmarq-vsq-done", ("c:sandbox-trial", "implied", "'for your writing-center trial'")],
    frm=a(CALLUM), to=a(M, DELPH), length="short", challenges=["privacy"], secrets=["Pm-Sbx!7731-qk"],
    style="Terse technical email. 'Sandbox: https://sandbox.penmarq.example/tarrow  user: tarrow.eval  temporary password: "
          "Pm-Sbx!7731-qk (change on first login). Also attached: our completed security questionnaire (sorry it's late - "
          "Juniper asked me to send it).' Signs 'Callum Ferris, Solutions Engineer, Penmarq'.")

cres("book-sade-done", f"{D} 13:41", "book-sade", "done", "Lucía booked the chargeback review with Sade (Tue 2 Mar 16:00)")
fact("cb-next1", f"{D} 13:41", CB, "next_step", "Review options with Sade on 2 March at 16:00",
     "Chargeback options review with Sade booked for 2 March 16:00")
art("M10", "calendar", f"{D} 13:41", "Invite: Chargeback options review (Sade / Mara)", ["book-sade-done", "cb-next1"],
    frm=a(LUCIA), to=a(SADE, M, RAMONA, PERCY), length="short", challenges=["silent_closure", "privacy"],
    secrets=["https://meet.tarrow.example/j/5528091734?pwd=Qx7rT2bK"],
    style=NOFOLD + "METHOD:REQUEST from Lucía. SUMMARY 'Chargeback options review (Sade / Mara)', DTSTART 2027-03-02T16:00, DTEND "
          "16:30, LOCATION 'VC conference room / video', DESCRIPTION 'Join: https://meet.tarrow.example/j/5528091734?pwd=Qx7rT2bK'. "
          "No message text - the invite itself is the only sign the booking was done.")

art("M17", "calendar", f"{D} 14:20", "Updated: Delphine / Mara check-in moved to Thu 4 Mar 11:00", [
    ("c:scorecard", "indirect", "agenda line 'scorecard summary'")],
    frm=a(DELPH), to=a(M), length="short", challenges=["privacy", "duplicate_signal"],
    secrets=["https://meet.tarrow.example/j/6120847753"],
    style=NOFOLD + "METHOD:REQUEST with SEQUENCE:1 (an UPDATE of an existing invite, same UID). Organizer Delphine. SUMMARY "
          "'Delphine / Mara check-in'. Was Wed 3 Mar 11:00-11:30; now DTSTART 2027-03-04T11:00, DTEND 11:30. DESCRIPTION "
          "'Moved - you're at the leadership offsite Wednesday. Agenda: scorecard summary, DSA, what you saw on the site "
          "visit. Join: https://meet.tarrow.example/j/6120847753'.")

# ---------------------------------------------------------------- MLE panel 14:00-15:30
fact("hire-s1", f"{D} 15:40", HIRE, "summary",
     "Panel with Mateus Okonedo held on 1 March (me, Ilya, Ramona); the panel leans yes. Scorecards are due in TarrowRecruit "
     "after the panel; references come next. Sade is the hiring manager.",
     "Mateus panel held")
art("M11", "meeting_notes", f"{D} 15:40", "Debrief: Mateus panel", ["hire-s1"],
    frm=a(M), participants=n(M, ILYA, RAMONA, MATEUS), sent=f"{D} 15:40", length="short", challenges=["alias"],
    must_not_say=["salary, band or offer amount", "that anyone has been asked to collect references yet"],
    style="Mara's own debrief. 'panel w/ Mats Okonedo, 14:00-15:30. Ilya: strong yes (eval infra). Ramona: yes, wants more "
          "on stakeholder mgmt. me: lean yes. my scorecard → TarrowRecruit asap, then refs (Sol). Sade decides.'")

fact("hub-next1", f"{D} 15:32", HUB, "next_step", "Finish the Tinderbox tenant (blocked on the Kestrow IdP signing cert)",
     "Tinderbox tenant ~80% done, blocked on the IdP signing cert")
art("M12", "chat", f"{D} 15:32", "#kettleyard: Tinderbox tenant status", [
    "hub-next1", ("c:tenant", "direct", "Bartosz: tenant ~80%, blocked on the cert from Teo")],
    participants=n(BARTOSZ, ILYA, M), length="short", challenges=["name_collision", "duplicate_signal"],
    noise_notes="Earlier in the export: a bot post about a dependency update and Ilya asking who broke the staging dashboard.",
    style="Bartosz (@bart): 'tinderbox tenant ~80%, blocked on the IdP signing cert from teo'. Ilya: '@bart can you chase teo "
          "directly'. Mara: 'teo's on it per standup'. Display name for Bartosz shows as 'Bart W.' The word 'Bart' here means "
          "Bartosz, not the Kestrow CIO.")

art("M18", "calendar", f"{D} 16:05", "Canceled: Sade / Mara 1:1 (Thu 4 Mar)", [],
    frm=a(LUCIA), to=a(M, SADE), length="short", challenges=["noise"], noise=True,
    noise_notes="Cancellation only; no project content.",
    style=NOFOLD + "METHOD:CANCEL from Lucía for one instance of the recurring 'Sade / Mara 1:1' (RECURRENCE-ID "
          "2027-03-04T15:00:00-08:00). DESCRIPTION 'Sade is in Board of Regents prep Thursday afternoon - I'll find a slot "
          "next week. - Lulu'. STATUS:CANCELLED.")

art("M13", "email", f"{D} 16:48", "[KSD-20931] Tinderbox SSO group claims: status changed to Pending Vendor", [
    "p-ksd-bot", ("c:group-claims", "direct", "ticket KSD-20931, group claims, Pending Vendor (IdP patch)")],
    frm=["Kestrow Service Desk <noreply-servicedesk@kestrow.tarrow.example>"], to=a(M), low_value=True, length="short",
    challenges=["duplicate_signal"],
    style="Automated ticket notification. Fields: Ticket KSD-20931, Summary 'Tinderbox SSO - group claims not released', "
          "Assignee T. Lisowski, Status Pending Vendor, Last update 'Awaiting IdP vendor patch'. Boilerplate footer.")

commit("sadebart", f"{D} 18:24", "task", "Get Sade and Bart Ngata together to settle Tinderbox ownership", M, YUSRA,
       project=LAN, basis="sent", keywords=["Tinderbox ownership", "Bart Ngata"],
       summary="Promised Yusra I'd get Sade and Bart Ngata in a room about who owns Tinderbox after go-live")
art("M14", "chat", f"{D} 18:24", "DM Yusra / Mara: ownership heads-up", ["c:sadebart"],
    participants=n(YUSRA, M), length="short", challenges=["name_collision", "implied_commitment"],
    style="DM. Yusra: 'heads up - Bart wants to talk about who owns Tinderbox after go-live. he thinks Kestrow should run it.' "
          "(Bart = Bart Ngata, the Kestrow CIO.) Mara: 'fair. i'll get sade + bart ngata in a room.' Yusra: '👍'.")

fact("cb-s1", f"{D} 19:06", CB, "summary",
     "Percy rebased the FTE inputs on 1 March (v2: Orrin Valley had been double-counted), so the options are being "
     "re-run. The options paper goes to Sade before the review Lucía is booking; the Council of Campus CIOs meets "
     "12 March.",
     "Chargeback inputs rebased (FTE v2)")
art("M15", "email", f"{D} 19:06", "Rebased FTE inputs (v2): Orrin Valley double-counted", ["cb-s1"],
    frm=a(PERCY), to=a(M), cc=a(RAMONA), length="short", challenges=["supersession"],
    style="Terse: 'Use v2 attached, not v1. Orrin Valley was double-counted (graduate FTE included twice). Total drops "
          "about 2,900 FTE.' Signs 'Percy'.")
art("M16", "document", f"{D} 19:06", "FY27 campus FTE inputs v2", [("cb-s1", "direct", "rebased FTE table")],
    ext="xlsx", parent="M15", length="short", challenges=["supersession"],
    style="Same layout as v1 but sheet 'FTE_v2'. Orrin Valley 9,400 (was 12,300) with note 'grad FTE double-counted in v1'; "
          "others unchanged; second sheet 'changes' listing the delta.")
