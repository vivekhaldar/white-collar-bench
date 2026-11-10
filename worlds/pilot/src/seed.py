"""Seed history: Mon 2027-02-15 .. Fri 2027-02-26 (plus one tiny Saturday note)."""

from dsl import art, commit, cres, decide, fact
from names import *  # noqa: F403

# ======================================================================= Mon 15 Feb
fact("u:tinderbox-budget", "2027-02-15 09:00", LAN, "budget", "212000 USD (FY27 pilot envelope)",
     "Tinderbox FY27 pilot budget set", unobservable="Tinderbox's budget is never stated in any input")
fact("u:hub-budget", "2027-02-15 09:00", HUB, "budget", "1350000 USD (FY27 operating)",
     "Kettleyard FY27 operating budget set", unobservable="Kettleyard's budget is never stated in any input")

commit("lib-concept", "2027-02-15 08:05", "task", "Write Ramona Iturbe a concept note for the library research assistant",
       M, RAMI, project=LIB, basis="reported", keywords=["concept note", "library research assistant"],
       summary="I still owe Ramona Iturbe a concept note on the library research assistant (parked since January)")
commit("niall-reqs", "2027-02-15 08:05", "ask", "Send requirements for the citation-checker idea",
       NIALL, M, project=CITE, status="waiting", basis="reported", keywords=["citation checker", "requirements"],
       summary="Waiting on Niall for requirements for his citation-checker idea")
commit("gpu-eval", "2027-02-15 08:05", "task", "Assess on-campus GPU hosting for Tinderbox",
       M, YUSRA, project=LAN, basis="reported", keywords=["GPU", "on-campus hosting"],
       summary="Yusra asked me to look at hosting Tinderbox on Kestrow's campus GPUs")

art("S01", "note", "2027-02-15 08:05", "Portfolio map, spring half", [
    "o-tarrow-system", "o-ods", "o-kestrow", "o-saltmarren", "o-orrin-valley", "o-brackwater",
    "pr-tinderbox", "pr-kettleyard", "pr-wft", "pr-transfer-eval", "pr-workshop", "pr-chargeback", "pr-mle-hire",
    "pr-library-ra", "pr-citation-helper",
    (SADE, "direct", "Sade (VC, my boss) sponsors Tinderbox, Kettleyard, workshop, chargeback, MLE hire"),
    (RAMONA, "direct", "Ramona (Director of Programs) runs the workshop and is on Tinderbox and chargeback"),
    (ILYA, "direct", "Ilya (data platform principal) owns Kettleyard"),
    (YUSRA, "direct", "Yusra Haddad (Kestrow TLT director) is the campus lead on Tinderbox"),
    (DELPH, "direct", "Delphine Arceneaux (Saltmarren interim registrar) sponsors the bake-off and the transfer discovery"),
    (NIALL, "direct", "Niall Fairbrother (Orrin Valley CIO) had the citation-checker idea"),
    (RAMI, "direct", "Ramona Iturbe (Brackwater associate dean of libraries) is the library RA contact; write 'Ramona I.'"),
    (SOL, "direct", "MLE req (REQ-2207): Sade is hiring manager, Sol (Marisol Etxeberria, talent partner) sources, I run the tech screens"),
    (PERCY, "direct", "Percy (Percival Ndiaye, budget director) has the FTE numbers for chargeback"),
    "c:lib-concept", "c:niall-reqs", "c:gpu-eval"],
    frm=a(M), length="medium", challenges=["alias", "name_collision"],
    must_not_say=["any budget figure for Tinderbox or Kettleyard"],
    style="Mara's own Markdown note, terse shorthand. One heading per project (Tinderbox = 'the Kestrow course assistant "
          "pilot', target go-live 22 Mar; Kettleyard = 'the hub'; 'WFT bake-off' for Saltmarren writing tool, rec by 26 Mar; "
          "'Saltmarren discovery' on transfer transcript evaluation, readout 19 Mar; workshop Thu 4 Mar (Ramona's); chargeback model "
          "for Council of Campus CIOs 12 Mar; MLE hire (REQ-2207, Sade's hire - I just screen); library RA idea 'parked since Jan' (dormant); citation "
          "helper placeholder 'Niall's idea, dormant, no reply from him'). People in parentheses with role phrases. A 'loose ends' list: "
          "'owe Ramona I. the concept note', 'still waiting on Niall's reqs', 'Yusra asked: can Kestrow GPUs host Tinderbox? look into it'. "
          "Use both 'Ramona' (Szabo) and 'Ramona I.' (Iturbe) so the collision is visible.")

commit("weekly-0219", "2027-02-15 09:32", "task", "Send Sade the weekly AI & Data update (week of 15 Feb)",
       M, SADE, project=None, basis="received", keywords=["weekly update", "19 Feb"],
       summary="Sade wants a Friday weekly update (three bullets and one risk); first one due 19 Feb")
commit("cb-options", "2027-02-15 09:32", "ask", "Send Sade Kettleyard chargeback options",
       M, SADE, project=CB, basis="received", keywords=["chargeback options", "Council of Campus CIOs"],
       summary="Sade asked me for Kettleyard chargeback options ahead of the 12 March Council of Campus CIOs")
art("S02", "email", "2027-02-15 09:32", "Spring priorities and how I'd like updates", [
    LUCIA, BART, "c:weekly-0219", "c:cb-options"],
    frm=a(SADE), to=a(M), cc=a(RAMONA), length="medium", challenges=["alias"],
    style="Crisp exec email. Format rule: 'Every Friday by email: three bullets and one risk. First one this Friday (19 Feb).' "
          "Chargeback: 'I need chargeback options from you well before the Council of Campus CIOs on the 12th, so we can review "
          "them together first.' Routing: "
          "'For anything at Kestrow, go through Bart Ngata's office; Lucía will get you time with him. Yusra is your day-to-day.' "
          "Signs 'Sade'. Signature: Dr. Folasade Renwick, Vice Chancellor for Digital Strategy.")

commit("onepager", "2027-02-15 11:04", "ask", "Send Yusra the Tinderbox architecture one-pager",
       M, YUSRA, project=LAN, basis="received", keywords=["one-pager", "architecture"],
       summary="Yusra asked me for the Tinderbox architecture one-pager before Thursday's ARB prep")
art("S03", "chat", "2027-02-15 11:04", "#tinderbox-core: one-pager for ARB prep", [
    JACK, DIMA, "c:onepager"],
    participants=n(YUSRA, JACK, DIMA, M), length="short", challenges=["alias"],
    style="Channel #tinderbox-core, workspace 'tarrow'. Yusra (@yusra): '@mara can you send the architecture one-pager before "
          "Thursday's ARB prep?' Mara (@mara): 'yep'. Joaquín (@jsep): 'ARB will want hosting options + data flows on it'. "
          "Dmitri (@dima): 'and the LMS interface pls, so i know what i'm building'. Reaction +1 from @yusra.")

# ======================================================================= Tue 16 Feb
fact("lib-next", "2027-02-16 08:47", LIB, "next_step", "Revisit after Brackwater midterms (mid-March)",
     "Ramona Iturbe asked to park the library idea until after midterms")
art("S04", "email", "2027-02-16 08:47", "Re: library research assistant", [
    "lib-next", (RAMI, "direct"), ("c:lib-concept", "second-hand", "'whenever you get to the concept note, no rush'")],
    frm=a(RAMI), to=a(M), length="short", thread=[], challenges=["name_collision"],
    style="Gracious academic tone. Quotes (one level, '>') a short January note from Mara. 'Let's park this until after "
          "midterms - mid-March at the earliest. Still keen.' Signs 'Ramona' with full signature Ramona Iturbe, Associate "
          "Dean of Libraries, TU Brackwater.")

commit("scrivelo-vsq", "2027-02-16 10:18", "ask", "Return Scrivelo's completed vendor security questionnaire",
       GREG, M, project=WFT, status="waiting", basis="sent", keywords=["Scrivelo", "security questionnaire"],
       summary="Sent Scrivelo the vendor security questionnaire; waiting on Gregor to return it")
commit("penmarq-vsq", "2027-02-16 10:18", "ask", "Return Penmarq's completed vendor security questionnaire",
       JUNI, M, project=WFT, status="waiting", basis="sent", keywords=["Penmarq", "security questionnaire"],
       summary="Sent Penmarq the vendor security questionnaire; waiting on Juniper to return it")
commit("proc-path", "2027-02-16 10:18", "ask", "Confirm the procurement path for the writing tool (cooperative contract or RFQ)",
       CLEM, M, project=WFT, status="waiting", basis="sent", keywords=["procurement path", "RFQ"],
       summary="Asked Clement whether the writing tool goes through a cooperative contract or an RFQ")
art("S05", "email", "2027-02-16 10:18", "Tarrow: vendor security & accessibility questionnaire (writing feedback tool)", [
    "o-scrivelo", "o-penmarq", GREG, JUNI, CLEM, "c:scrivelo-vsq", "c:penmarq-vsq", "c:proc-path"],
    frm=a(M), to=a(GREG, JUNI), cc=a(DELPH, CLEM), length="short",
    style="Mara, polite and brief. Attaching (mention only) the 'vendor security & accessibility questionnaire (VSQ)'. "
          "'Please return it by the end of next week.' Separate line: 'Clement - can you confirm whether we go through a "
          "cooperative contract or need an RFQ?' Signs '— Mara', title Principal Architect, AI & Data, ODS.")

commit("process-map", "2027-02-16 14:02", "ask", "Bring a process map of the current transfer-credit evaluation workflow",
       RUFUS, M, project=TCE, status="waiting", basis="sent", keywords=["process map", "workflow"],
       summary="Asked Rufus to bring a process map of the transfer evaluation workflow to the site visit")
commit("interviews", "2027-02-16 14:02", "task", "Interview Saltmarren transfer evaluators during the site visit",
       M, DELPH, project=TCE, basis="scheduled", keywords=["site visit", "interviews"],
       summary="Site visit on 2 March booked, with interviews of transfer evaluators")
fact("tce-next", "2027-02-16 14:02", TCE, "next_step", "Site visit at Saltmarren on 2 March",
     "Saltmarren site visit booked for 2 March")
fact("tce-mem1", "2027-02-16 14:02", TCE, "members", [M, DELPH, RUFUS], "Rufus joins the transfer evaluation discovery")
art("S06", "calendar", "2027-02-16 14:02", "Invite: Saltmarren site visit - transfer evaluation discovery", [
    RUFUS, "c:process-map", "c:interviews", "tce-next", "tce-mem1"],
    frm=a(M), to=a(DELPH, RUFUS), length="short", challenges=["privacy"],
    secrets=["https://meet.tarrow.example/j/6614402981", "882104"],
    style="Do NOT fold long iCalendar lines: keep the DESCRIPTION and the join link on one line each. METHOD:REQUEST. SUMMARY 'Saltmarren site visit - transfer evaluation discovery'. DTSTART 2027-03-02 10:00, DTEND "
          "12:30 (-08:00). LOCATION 'Registrar's Office, Saltmarren Admin Bldg, 3rd floor'. ORGANIZER Mara. DESCRIPTION: "
          "'Agenda: walk the transfer evaluation workflow; interviews with 2-3 evaluators. Rufus - could you bring a process "
          "map of the current workflow? Remote dial-in for anyone not on site: https://meet.tarrow.example/j/6614402981 "
          "Passcode: 882104'.")

# ======================================================================= Wed 17 Feb
decide("three-courses", "2027-02-17 10:30", "Limit the Tinderbox pilot to three courses: CHEM 110, HIST 214 and BIOL 205",
       [M, YUSRA], project=LAN, keywords=["three courses", "CHEM 110", "HIST 214"],
       summary="Decided with Yusra to limit the Tinderbox pilot to three courses (CHEM 110, HIST 214, BIOL 205)")
commit("spec-v1", "2027-02-17 10:34", "task", "Write the Tinderbox LMS interface spec (v1)", M, DIMA, project=LAN,
       basis="reported", keywords=["interface spec v1", "LMS interface spec"],
       summary="I said I'd write up the Tinderbox LMS interface spec this week for Dmitri")
commit("recruit", "2027-02-17 10:38", "task", "Recruit the HIST 214 and BIOL 205 instructors for the pilot", EMEKA, M,
       project=LAN, status="waiting", basis="reported", keywords=["HIST 214", "BIOL 205", "instructors"],
       summary="Emeka will recruit the HIST 214 and BIOL 205 instructors")
commit("onboarding", "2027-02-17 10:40", "task", "Schedule faculty onboarding sessions for the pilot courses", INGRID, YUSRA,
       others=[M], project=LAN, status="waiting", basis="reported", keywords=["onboarding sessions", "faculty onboarding"],
       summary="Yusra asked Ingrid to schedule faculty onboarding sessions for the pilot")
fact("lan-mem1", "2027-02-17 10:45", LAN, "members", [M, YUSRA, RAMONA, JACK, DIMA, EMEKA, INGRID],
     "Tinderbox core team now includes Joaquín, Dmitri, Emeka and Ingrid")
fact("lan-s1", "2027-02-17 10:45", LAN, "summary",
     "Pilot scoped to three courses (CHEM 110, HIST 214, BIOL 205). I am writing the LMS interface spec for Dmitri; Emeka is "
     "recruiting the HIST and BIOL instructors and Ingrid is scheduling faculty onboarding. Go-live targeted for 22 March.",
     "Tinderbox scoped to three courses")
art("S07", "transcript", "2027-02-17 10:50", "Tinderbox scope meeting", [
    EMEKA, INGRID, "d:three-courses", "c:spec-v1", "c:recruit", "c:onboarding", "lan-mem1", "lan-s1"],
    participants=n(YUSRA, EMEKA, JACK, INGRID, DIMA, M), length="long", sent="2027-02-17 10:45",
    challenges=["implied_commitment"],
    style="45-minute WebVTT transcript, NOTE header 'Tinderbox scope - 17 Feb 2027, 10:00-10:45'. Opens with small talk "
          "(Emeka's coffee, snow). Decision by assent: Mara: 'so three courses - CHEM 110, HIST 214, BIOL 205 - everyone ok?' "
          "Yusra: 'Works.' Emeka: 'Yes!' Implied commitment: Mara: 'I'll write up the interface spec this week, Dmitri.' Yusra: "
          "'Emeka, can you get the HIST and BIOL instructors on board?' Emeka: 'Leave it with me.' Yusra: 'Ingrid, can you "
          "schedule onboarding sessions?' Ingrid: 'Yes, I'll find slots.' Yusra mentions Saanvi will look at load testing later "
          "(no commitment). Go-live 22 March mentioned. Backchannel ('mm-hm', 'right'), one cross-talk overlap.")

art("S07C", "calendar", "2027-02-17 11:10", "Invite: Tinderbox daily standup (recurring)", [],
    frm=a(YUSRA), to=a(M, JACK, DIMA, INGRID, RAMONA), length="short", challenges=["privacy"],
    secrets=["https://meet.tarrow.example/j/2207519364"],
    noise_notes="Pure scheduling; no project facts beyond the cadence.",
    style="Do NOT fold long iCalendar lines. METHOD:REQUEST from Yusra (organizer). SUMMARY 'Tinderbox daily standup'. "
          "DTSTART 2027-02-22T09:15:00-08:00, DTEND 09:30, RRULE:FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;UNTIL=20270402. LOCATION "
          "'KES Huddle Room 2B / video'. DESCRIPTION 'Daily 15 min for the Tinderbox build team. Join: "
          "https://meet.tarrow.example/j/2207519364'. Attendee list may grow; no agenda.")

commit("panel-sched", "2027-02-17 16:30", "task", "Schedule a panel interview for Mateus", SOL, M, project=HIRE,
       status="waiting", basis="reported", keywords=["panel interview", "set up a panel"],
       summary="Phone-screened Mateus Okonedo; asked Marisol to set up a panel")
fact("hire-ph1", "2027-02-17 16:30", HIRE, "phase", "panel scheduling", "MLE hire moved to panel scheduling after the screen")
art("S08", "meeting_notes", "2027-02-17 16:30", "Debrief: phone screen with Mateus Okonedo", [
    MATEUS, "c:panel-sched", "hire-ph1"],
    frm=a(M), length="short", challenges=["alias"],
    style="Mara's own debrief, Markdown, terse. 'screen w/ Mateus Okonedo (goes by Mats) - 45 min. strong on eval infra + LLM "
          "serving; k8s thin. → panel. asked Sol to set up panel w/ Ilya + Ramona.' No salary discussion.")

# ======================================================================= Thu 18 Feb
cres("onepager-done", "2027-02-16 17:20", "onepager", "done", "Sent Yusra the Tinderbox architecture one-pager")
commit("sso-register", "2027-02-16 17:20", "ask", "Register Tinderbox as an SSO application in the Kestrow IdP", TEO, M,
       project=LAN, status="waiting", basis="sent", keywords=["SSO application", "IdP"],
       summary="Asked Teodor to register Tinderbox as an SSO app in the Kestrow IdP")
art("S10", "email", "2027-02-16 17:20", "Tinderbox architecture one-pager", [
    TEO, "onepager-done", "c:sso-register"],
    frm=a(M), to=a(YUSRA), cc=a(JACK, TEO), length="short", challenges=["alias"],
    style="Brief. 'One-pager attached for ARB prep. Two hosting options: (1) dedicated Kestrow deployment, (2) Kettleyard "
          "shared tenant - I lean 2 but want Jack's view.' Then: 'Teo - can you register Tinderbox as an SSO application in the "
          "Kestrow IdP? Client details in section 4.' Signs '— Mara'.")
art("S11", "document", "2027-02-16 17:20", "Tinderbox architecture one-pager v1", [
    ("onepager-done", "direct", "the delivered one-pager itself")],
    ext="pdf", parent="S10", length="short",
    style="One-page PDF: title 'Tinderbox - architecture one-pager (v1, 18 Feb)'. Sections: purpose (AI course assistant for "
          "CHEM 110, HIST 214, BIOL 205), hosting options 1 (dedicated Kestrow deployment) vs 2 (Kettleyard shared tenant), "
          "data flows (LMS -> context API -> gateway), identity (Kestrow IdP SSO), data classes (dummy vs real), open "
          "questions. Author Mara Ilves.")

commit("tenant", "2027-02-18 13:44", "ask", "Provision the Tinderbox tenant on Kettleyard", BARTOSZ, M, project=HUB,
       status="waiting", basis="sent", keywords=["Tinderbox tenant", "provision"],
       summary="Asked Bartosz to provision the Tinderbox tenant on Kettleyard")
fact("hub-mem1", "2027-02-18 13:44", HUB, "members", [ILYA, M, BARTOSZ], "Bartosz is doing Kettleyard tenant work")
art("S12", "chat", "2027-02-18 13:44", "#kettleyard: Tinderbox tenant request", [
    BARTOSZ, "c:tenant", "hub-mem1"],
    participants=n(M, BARTOSZ, ILYA), length="short", challenges=["name_collision"],
    style="Channel #kettleyard. Mara: '@bart can you provision the Tinderbox tenant? first real tenant'. Bartosz (@bart, display "
          "name 'Bartosz Zielke'): 'on it - need the IdP signing cert from kestrow first'. Ilya: '+1, tinderbox is tenant #1'. "
          "Lowercase, quick.")

fact("cb-ph1", "2027-02-18 16:30", CB, "phase", "modeling", "Chargeback model inputs received; modeling started")
commit("percy-actuals", "2027-02-18 16:30", "task", "Send the FY27 Kettleyard run-rate actuals for the cost model", PERCY, M,
       project=CB, status="waiting", basis="received", keywords=["run-rate actuals", "January close"],
       summary="Percy will send FY27 Kettleyard run-rate actuals after the January close")
art("S13", "email", "2027-02-18 16:30", "FY27 FTE inputs for the cost model", [
    ("cb-ph1", "direct", "Percy sends the FY27 FTE inputs v1 'as you asked Monday'; modeling can start"), "c:percy-actuals"],
    frm=a(PERCY), to=a(M), length="short", challenges=["alias"],
    style="Numbers-first, terse. 'Attached: FY27 campus FTE inputs (v1), as you asked Monday. Caveat: Orrin Valley figure is "
          "provisional. Run-rate actuals to follow after the January close.' Signs 'Percy', signature Percival Ndiaye, Director, System Budget & Finance.")
art("S14", "document", "2027-02-18 16:30", "FY27 campus FTE inputs v1", [("cb-ph1", "direct", "the FTE table itself")],
    ext="xlsx", parent="S13", length="short",
    style="Spreadsheet: one sheet 'FTE_v1' with columns Campus, FY27 student FTE, faculty FTE, notes. Rows: Kestrow 21,400; "
          "Saltmarren 9,850; Orrin Valley 12,300 (note 'provisional'); Brackwater 6,120. Total row.")

# ======================================================================= Fri 19 Feb
cres("weekly-0219-done", "2027-02-19 16:40", "weekly-0219", "done", "Sent Sade the weekly update for the week of 15 Feb")
art("S15", "email", "2027-02-19 16:40", "Weekly update: w/e 19 Feb", ["weekly-0219-done"],
    frm=a(M), to=a(SADE), length="short",
    style="Exactly three bullets and one risk. Bullets: Tinderbox scoped to 3 courses; VSQ out to Scrivelo and Penmarq; "
          "chargeback inputs in from Percy. Risk: SSO cert dependency for the Tinderbox tenant. Signs '— Mara'.")

commit("deck-v1", "2027-02-19 11:00", "task", "Draft the workshop deck v1", M, RAMONA, project=WS, basis="reported",
       keywords=["deck v1", "workshop deck"], summary="I own the workshop deck v1")
commit("connie-panel", "2027-02-19 11:00", "ask", "Confirm a panel slot at the workshop", CONNIE, M, project=WS,
       status="waiting", basis="reported", keywords=["workshop panel", "Wilberforce"],
       summary="Invited Prof. Wilberforce (Connie) to the workshop panel; waiting for her yes")
commit("bios", "2027-02-19 11:00", "task", "Send Ramona speaker bios for the workshop program", M, RAMONA, project=WS,
       basis="reported", keywords=["speaker bios", "workshop program"], summary="I owe Ramona speaker bios for the workshop program")
commit("ws-room", "2027-02-19 11:02", "task", "Book Pellery Hall 112 for the workshop", RAMONA, M, project=WS,
       status="waiting", basis="reported", keywords=["Pellery Hall 112", "room booking"],
       summary="Ramona is booking Pellery Hall 112 for the workshop")
fact("ws-mem1", "2027-02-19 11:00", WS, "members", [RAMONA, M, LUCIA, INES, EMEKA, CONNIE],
     "Workshop speakers lined up: Ines, Emeka, Connie (invited)")
fact("ws-s1", "2027-02-19 11:00", WS, "summary",
     "Workshop on Thu 4 March, 1-4pm, Pellery Hall 112 at Kestrow. Ines Vardakis (Eskerfield) confirmed as keynote; panel "
     "with Emeka and Prof. Wilberforce (invited). I own the deck; registration opens today.",
     "Workshop keynote confirmed and registration opening")
art("S16", "meeting_notes", "2027-02-19 11:40", "Workshop planning call - notes", [
    INES, "o-eskerfield", CONNIE, "c:deck-v1", "c:connie-panel", "c:bios", "c:ws-room", "ws-mem1", "ws-s1"],
    frm=a(RAMONA), participants=n(RAMONA, M, LUCIA), length="medium", sent="2027-02-19 11:00", challenges=["alias"],
    style="Ramona's tidy Markdown notes with emoji headers. 'Keynote: Dr. Ines Vardakis (Eskerfield) - CONFIRMED ✅'. 'Panel: "
          "Emeka + Prof. Wilberforce (History) - Mara invited her today, waiting to hear'. 'Room: Ramona to book Pellery Hall 112, 1-4pm Thu "
          "4 Mar (room booking pending)'. 'Reg link goes out today from the ODS inbox'. Actions: 'Mara - deck v1', 'Mara - speaker bios for the program'. No due date for "
          "the deck.")

cres("ws-room-done", "2027-02-19 13:00", "ws-room", "done", "Ramona booked Pellery Hall 112 for the workshop")
art("S17", "email", "2027-02-19 13:15", "Registration open: Teaching with AI workshop, Thu 4 March", [
    MBOX, ("ws-room-done", "implied", "the announcement gives the room as Pellery Hall 112 (so it is booked)")],
    frm=["ODS Team <ods-team@tarrow.example>"], to=["kestrow-faculty@kestrow.tarrow.example"], cc=a(M), length="short",
    noise_notes="Announcement; mostly logistics already known.",
    style="Announcement from the shared mailbox, signed '— ODS Team'. Thu 4 March, 1-4pm, Pellery Hall 112, Kestrow campus. Registration "
          "form https://forms.tarrow.example/twai-mar4. Footer: 'This mailbox is monitored during business hours.'")

# ======================================================================= Sat 20 Feb
cres("gpu-drop", "2027-02-20 10:20", "gpu-eval", "dropped", "Dropped the on-campus GPU hosting look: no Kestrow GPU capacity until fall")
art("S18", "note", "2027-02-20 10:20", "Sat note", ["gpu-drop"],
    frm=a(M), length="short", challenges=["worker_directive"],
    style="Three lines of shorthand: 'drop the GPU eval - Jack says no campus GPU capacity till fall.' 'chargeback: "
          "consumption vs flat vs hybrid → sketch A/B/C.' 'buy milk'.")

# ======================================================================= Mon 22 Feb
commit("weekly-0226", "2027-02-22 06:55", "task", "Send Sade the weekly AI & Data update (week of 22 Feb)", M, SADE,
       project=None, basis="received", keywords=["weekly update", "26 Feb"],
       summary="ODS mailbox reminder: weekly update to Sade due Fri 26 Feb")
art("S19", "email", "2027-02-22 06:55", "Reminder: weekly VC updates due Friday 26 Feb", ["c:weekly-0226"],
    frm=["ODS Team <ods-team@tarrow.example>"], to=["ods-staff@tarrow.example"], length="short",
    style="Monday reminder from the shared mailbox: 'Friendly reminder: weekly updates to the VC are due Friday 26 Feb "
          "(three bullets + one risk).' Signed '— ODS Team'.")

cres("spec-v1-done", "2027-02-22 10:05", "spec-v1", "done", "Sent Dmitri and Joaquín the Tinderbox interface spec v1")
art("S20", "email", "2027-02-22 10:05", "Tinderbox interface spec v1", ["spec-v1-done"],
    frm=a(M), to=a(DIMA, JACK), cc=a(YUSRA), length="short",
    style="Short: 'Spec v1 attached - request/response context API between the LMS and the assistant. Jack, it goes to ARB "
          "next week.' Signs '— Mara'.")
art("S21", "document", "2027-02-22 10:05", "Tinderbox LMS interface spec v1", [("spec-v1-done", "direct", "the spec itself")],
    ext="md", parent="S20", length="medium",
    style="Markdown spec 'Tinderbox LMS interface spec - v1 (22 Feb)': synchronous request/response context API, endpoints "
          "GET /courses/{id}/context, POST /sessions, field list, auth via Kestrow IdP tokens, dummy-data note.")

commit("refarch-review", "2027-02-22 14:30", "ask", "Review the Kettleyard reference architecture v3 and send Ilya comments",
       M, ILYA, project=HUB, basis="received", keywords=["reference architecture", "v3"],
       summary="Ilya asked me to review Kettleyard reference architecture v3 (comments by end of next week)")
fact("hub-mem2", "2027-02-22 14:30", HUB, "members", [ILYA, M, BARTOSZ, HW, BETT],
     "Kettleyard reviewers: Mara, Bettina, Hyun-woo")
fact("hub-s1", "2027-02-22 14:30", HUB, "summary",
     "Reference architecture v3 is out for peer review (me, Bettina, Hyun-woo); Bartosz is provisioning the Tinderbox tenant, "
     "the first real tenant; January run-rate costs are published in section 7 of v3.",
     "Kettleyard ref arch v3 out for review")
art("S22", "email", "2027-02-22 14:30", "Kettleyard reference architecture v3: review please", [
    HW, BETT, "c:refarch-review", "hub-mem2", "hub-s1"],
    frm=a(ILYA), to=a(M), cc=a(BETT, HW), length="medium", challenges=["alias"],
    style="Ilya, precise. 'v3 attached. Mara, could you get me comments by end of next week? Bettina and Hyun-woo, same "
          "ask, lighter touch.' 'You asked for January run-rate - it's in section 7.' Numbered list of what changed since v2.")
art("S23", "document", "2027-02-22 14:30", "Kettleyard Reference Architecture v3", [
    ("hub-s1", "direct", "architecture: tenants, identity broker, model gateway, secrets vault; section 7 run-rate")],
    ext="pdf", parent="S22", length="long",
    style="Multi-page PDF 'Kettleyard Reference Architecture - v3 (draft for review)'. Sections 1-8: tenancy model, identity "
          "broker, model gateway (connection pooling, rate limits), secrets vault, logging/redaction, onboarding, 7. January "
          "run-rate (table, no budget totals), 8. open questions. Change log v2->v3.")

cres("sso-register-done", "2027-02-22 16:00", "sso-register", "done", "Teodor registered Tinderbox as an SSO app in the IdP")
commit("context-api", "2027-02-22 16:08", "task", "Build the LMS context API against the interface spec", DIMA, M,
       project=LAN, status="waiting", due="2027-03-05", basis="received", keywords=["context API", "LMS context API"],
       summary="Dmitri committed to build the LMS context API by 5 March")
commit("opt1-pricing", "2027-02-22 16:10", "ask", "Price option 1 (dedicated Kestrow deployment) for Tinderbox hosting",
       JACK, M, project=LAN, status="waiting", basis="sent", keywords=["option 1", "dedicated"],
       summary="Asked Joaquín to price option 1 (a dedicated Kestrow deployment) for comparison")
art("S24", "chat", "2027-02-22 16:12", "#tinderbox-core: SSO app, context API date, option 1 pricing", [
    "sso-register-done", "c:context-api", "c:opt1-pricing"],
    participants=n(TEO, DIMA, M, JACK), length="short", challenges=["alias"],
    style="Teo (@teo): 'tinderbox is registered as an SSO app in the IdP. client id tinderbox-kes (secret in vault)'. Dmitri "
          "(@dima): 'got spec v1. i can have the context API by Mar 5'. Mara: 'great'. Mara: '@jsep can you price option 1 "
          "(dedicated deploy) so we can compare?' Joaquín: 'will do'.")

# ======================================================================= Tue 23 Feb
commit("scrivelo-pricing", "2027-02-23 11:30", "task", "Send Scrivelo pricing for Saltmarren", GREG, M, project=WFT,
       status="waiting", basis="reported", keywords=["Scrivelo", "pricing"], summary="Gregor will send Scrivelo pricing")
commit("scrivelo-acr", "2027-02-23 11:35", "task", "Send Scrivelo's accessibility conformance report", GREG, M,
       project=WFT, status="waiting", basis="reported", keywords=["accessibility conformance report", "ACR"],
       summary="Gregor will send Scrivelo's accessibility conformance report")
commit("scrivelo-api", "2027-02-23 11:40", "task", "Send Scrivelo's LMS integration API documentation", HANNAH, M,
       project=WFT, status="waiting", basis="reported", keywords=["API documentation", "LMS integration"],
       summary="Hannah Feld will send Scrivelo's LMS integration API docs")
commit("scrivelo-sections", "2027-02-23 11:45", "ask", "Nominate two Saltmarren sections for a Scrivelo trial", M, GREG,
       project=WFT, accepted=False, basis="reported", keywords=["two sections", "trial"],
       summary="Gregor suggested I nominate two sections for a Scrivelo trial (not agreed)")
commit("scrivelo-refs", "2027-02-23 11:42", "task", "Send two Scrivelo customer references from comparable campuses", GREG, M,
       project=WFT, status="waiting", basis="reported", keywords=["customer references", "comparable campuses"],
       summary="Gregor will send two customer references from comparable campuses")
commit("lionel-lms", "2027-02-23 11:48", "task", "Send Saltmarren's LMS integration constraints", LIONEL, M,
       project=WFT, status="waiting", basis="reported", keywords=["LMS integration constraints", "integration constraints"],
       summary="Lionel said he'd send Saltmarren's LMS integration constraints")
fact("wft-mem1", "2027-02-23 11:55", WFT, "members", [M, DELPH, CLEM, LIONEL], "Lionel joined the writing-tool evaluation")
art("S25", "transcript", "2027-02-23 11:55", "Scrivelo demo", [
    HANNAH, LIONEL, "c:scrivelo-pricing", "c:scrivelo-acr", "c:scrivelo-api", "c:scrivelo-sections", "c:lionel-lms", "c:scrivelo-refs", "wft-mem1"],
    participants=n(GREG, HANNAH, M, DELPH, LIONEL), sent="2027-02-23 11:50", length="long",
    challenges=["name_collision", "endorsement"],
    style="50-min WebVTT, NOTE 'Scrivelo demo - 23 Feb 2027'. Gregor intros, Hannah demos rubric-aligned feedback on a "
          "sample ENGL 101 essay. Delphine asks about ENGL 101/102 volume. Lionel asks about LMS integration and data residency; "
          "Hannah: 'I'll send our LMS integration API documentation.' Gregor: 'I'll get you pricing for Saltmarren and our "
          "accessibility conformance report (ACR) - and two customer references from comparable campuses.' Gregor: 'Mara, if you could nominate two sections for a trial...' Mara: "
          "'let's see after the shortlist' (non-committal, NOT accepted). Lionel: 'I'll send you our LMS integration constraints.' Some cross-talk, Lionel's audio drops once.")

commit("catering", "2027-02-23 15:20", "task", "Place the workshop catering order", RAMONA, M, project=WS,
       status="waiting", basis="received", keywords=["catering", "catering order"], summary="Ramona said she'll handle workshop catering")
cres("recruit-done", "2027-02-23 15:00", "recruit", "done", "Emeka confirmed the HIST 214 and BIOL 205 instructors")
commit("dashboard-0223", "2027-02-23 15:10", "ask", "Send Ramona three lines on Tinderbox for the program dashboard (week of 22 Feb)",
       M, RAMONA, project=LAN, basis="received", keywords=["program dashboard", "tinderbox lines"],
       summary="Ramona asked me for this week's Tinderbox lines for the program dashboard")
cres("dashboard-0223-done", "2027-02-23 15:19", "dashboard-0223", "done", "Sent Ramona the Tinderbox lines for the program dashboard")
art("S26", "chat", "2027-02-23 15:20", "DM Ramona / Mara: room, catering, instructors", [
    ("ws-room-done", "second-hand", "'room's booked'"), "c:catering", "c:dashboard-0223", "dashboard-0223-done", ("recruit-done", "second-hand", "'Emeka says both HIST + BIOL instructors are in!'")],
    participants=n(RAMONA, M), length="short", challenges=["alias"],
    style="DM. Ramona 15:08: 'room's booked - Pellery Hall 112 ✅ I'll do the catering order + AV'. Ramona 15:10: 'and 3 lines "
          "on tinderbox for the program dashboard pls? 🙏' Mara 15:19: 'sent - tinderbox lines are in the tracker'. Ramona: 'also Emeka says both HIST + BIOL "
          "instructors are in! 🎉'. Mara: 'nice. ty mona'.")

# ======================================================================= Wed 24 Feb
commit("eval-plan", "2027-02-24 13:30", "task", "Revise the Tinderbox evaluation plan to address the success-metric concern",
       M, CONNIE, others=[EMEKA], project=LAN, basis="reported", keywords=["evaluation plan", "success metric"],
       summary="Connie challenged 'student satisfaction' as the success metric; I said I'd rework the evaluation plan")
commit("chem-rubric", "2027-02-24 13:25", "task", "Send Mara the CHEM 110 assignment rubric for the evaluation", EMEKA, M,
       project=LAN, status="waiting", basis="reported", keywords=["CHEM 110", "assignment rubric"],
       summary="Emeka will send me the CHEM 110 assignment rubric for the evaluation plan")
cres("connie-panel-done", "2027-02-24 13:20", "connie-panel", "done", "Connie agreed to be on the workshop panel")
commit("rubric-share", "2027-02-24 13:35", "task", "Share the evaluation rubric with the History department", M, CONNIE,
       project=LAN, accepted=False, basis="reported", keywords=["rubric", "History department"],
       summary="Yusra suggested I share the evaluation rubric with the History department (not agreed)")
art("S28", "transcript", "2027-02-24 13:45", "Tinderbox evaluation plan review", [
    "c:eval-plan", "connie-panel-done", "c:rubric-share", "c:chem-rubric"],
    participants=n(M, CONNIE, EMEKA, YUSRA), sent="2027-02-24 13:40", length="medium",
    challenges=["implied_commitment", "endorsement"],
    style="40-min WebVTT. Connie: 'Student satisfaction is not a learning outcome. I won't sign off on a pilot that measures "
          "vibes.' Emeka defends. Mara: 'Fair - let me rework the eval plan.' (no date). "
          "Emeka: 'I'll send you the CHEM 110 assignment rubric so you can see what we grade.' Connie on the panel: 'Yes, I'll do "
          "your panel. Someone has to be the resident skeptic.' Yusra: 'Mara, maybe share the rubric with the History "
          "department?' Mara: 'hm, maybe - let me think.' (NOT a commitment). Speaker turns with backchannel.")

cres("scrivelo-vsq-done", "2027-02-24 11:40", "scrivelo-vsq", "done", "Scrivelo returned its completed security questionnaire")
cres("scrivelo-pricing-done", "2027-02-24 11:40", "scrivelo-pricing", "done", "Gregor sent Scrivelo pricing")
art("S30", "email", "2027-02-24 11:40", "Scrivelo: completed questionnaire + pricing", [
    "scrivelo-vsq-done", "scrivelo-pricing-done"],
    frm=a(GREG), to=a(M), cc=a(DELPH), length="short", challenges=["alias"],
    style="Salesy but brief: 'Attached our completed security questionnaire and pricing for Saltmarren. ACR coming separately "
          "from our compliance team.' Signs 'Grig', signature Gregor Lindahl, Account Executive, Scrivelo Learning, with a "
          "calendar booking link.", must_not_say=["specific price figures"])

decide("shortlist", "2027-02-24 15:45", "Shortlist Scrivelo and Penmarq for the Saltmarren writing feedback tool",
       [M, DELPH], project=WFT, keywords=["shortlist", "Scrivelo", "Penmarq"],
       summary="Decided with Delphine to shortlist Scrivelo and Penmarq")
commit("essay-volumes", "2027-02-24 15:50", "task", "Send last year's ENGL 101/102 essay volumes", DELPH, M, project=WFT,
       status="waiting", basis="reported", keywords=["essay volumes", "ENGL 101/102"],
       summary="Delphine will pull last year's ENGL 101/102 essay volumes for sizing")
commit("scorecard-tpl", "2027-02-24 16:00", "task", "Build the vendor scorecard template", M, DELPH, project=WFT,
       basis="reported", keywords=["scorecard template", "vendor scorecard template"], summary="I'll build the vendor scorecard template")
fact("wft-ph1", "2027-02-24 16:15", WFT, "phase", "demos", "Writing-tool evaluation moved to demos")
fact("wft-s1", "2027-02-24 16:15", WFT, "summary",
     "Scrivelo and Penmarq shortlisted (24 Feb). Scrivelo demoed on 23 Feb and returned its questionnaire and pricing; "
     "Penmarq demo is on 1 March and its questionnaire is outstanding. I am building the scorecard; Clement has not yet "
     "confirmed the procurement path. Recommendation targeted for 26 March.",
     "Writing-tool shortlist set")
art("S31", "meeting_notes", "2027-02-24 16:15", "Notes: shortlist call with Delphine", [
    "d:shortlist", "c:scorecard-tpl", "c:essay-volumes", "wft-ph1", "wft-s1"],
    frm=a(M), participants=n(M, DELPH), length="short",
    style="Mara's debrief, terse bullets: 'shortlist = Scrivelo + Penmarq (agreed w/ Delphine)'; 'Penmarq demo Mon 1 Mar'; "
          "'me: scorecard template'; 'D. to pull last yr's ENGL 101/102 essay volumes'; 'still no word from Clement on procurement path'; 'rec by 26 Mar'.")

# ======================================================================= Thu 25 Feb
decide("dummy-data", "2027-02-25 08:45", "Pause real student data for Tinderbox; run in dummy-data mode until the security review is approved",
       [HW], project=LAN, keywords=["dummy-data mode", "real student data"],
       summary="Hyun-woo paused real student data for Tinderbox; dummy-data mode until the security review is approved")
fact("lan-ph1", "2027-02-25 10:02", LAN, "phase", "build (dummy-data mode)", "Tinderbox now building in dummy-data mode")
fact("lan-td1", "2027-02-25 10:02", LAN, "target_date", "2027-03-29", "Tinderbox go-live moved to 29 March")
fact("lan-bl1", "2027-02-25 10:02", LAN, "blocker", "Real student data paused pending security review",
     "Tinderbox blocked on the security review for real data")
fact("lan-s2", "2027-02-25 10:02", LAN, "summary",
     "Hyun-woo paused real student data on 25 Feb: Tinderbox runs in dummy-data mode until a security review package "
     "(sub-processors, data flows, retention) is approved. Go-live moved to 29 March. Spec v1 is with Dmitri (context API "
     "due 5 March); the tenant and SSO setup are in progress.",
     "Tinderbox paused on real data; go-live 29 March")
art("S33", "email", "2027-02-25 10:02", "Re: Tinderbox - pausing real student data", [
    "d:dummy-data", "lan-ph1", "lan-td1", "lan-bl1", "lan-s2"],
    frm=a(YUSRA), to=a(HW, M), cc=a(BART), sent="2027-02-25 10:02", thread=[], length="medium",
    challenges=["alias"],
    style="Yusra's reply-all quoting (one level) Hyun-woo's 08:50 email. Quoted Hyun-woo (formal): 'Per policy, production "
          "student data may not be used in non-production environments. Effective today Tinderbox runs in dummy-data mode. "
          "Before I can lift this I will need a security review package: sub-processor list, data flows, retention.' (No "
          "owner named.) Yusra's reply: 'Understood, Hugo. That realistically moves go-live to 29 March.' Bart Ngata cc'd.")

cres("panel-sched-done", "2027-02-18 10:30", "panel-sched", "done", "Marisol scheduled Mateus's panel for 1 March")
commit("panel-scorecard", "2027-02-18 10:30", "ask", "Submit my panel scorecard for Mateus", M, SOL, project=HIRE,
       basis="received", keywords=["panel scorecard", "TarrowRecruit"],
       summary="Panelists must submit scorecards for Mateus in TarrowRecruit after the panel")
fact("hire-ph2", "2027-02-18 10:30", HIRE, "phase", "panel", "Mateus panel scheduled for 1 March")
fact("hire-mem", "2027-02-18 10:30", HIRE, "members", [M, SOL, ILYA, RAMONA], "Hiring panel: Mara, Ilya, Ramona")
art("S34", "email", "2027-02-18 10:30", "Panel for Mateus Okonedo: Mon 1 Mar 14:00-15:30", [
    "panel-sched-done", "c:panel-scorecard", "hire-ph2", "hire-mem"],
    frm=a(SOL), to=a(M, ILYA, RAMONA), length="short", challenges=["privacy"],
    secrets=["https://meet.tarrow.example/j/4407718820"],
    style="Upbeat HR email. Panel Mon 1 Mar 14:00-15:30, Ops Conference Room B or video https://meet.tarrow.example/j/4407718820. "
          "'Please submit your panel scorecard in TarrowRecruit as soon as you can after the panel.' Signs 'Sol', signature Marisol Etxeberria, "
          "Talent Partner.")

cres("deck-v1-done", "2027-02-25 15:45", "deck-v1", "done", "Sent Ramona the workshop deck v1")
cres("bios-done", "2027-02-25 15:45", "bios", "done", "Sent Ramona the speaker bios with deck v1")
art("S35", "email", "2027-02-25 15:45", "Workshop deck v1", ["deck-v1-done", "bios-done"],
    frm=a(M), to=a(RAMONA), length="short",
    style="'v1 attached. rough on the panel section. will tighten for v2. speaker bios for the program are in the notes of "
          "slide 2.' Signs '— M'.")
art("S36", "document", "2027-02-25 15:45", "Teaching with AI - deck v1", [("deck-v1-done", "direct", "deck v1 itself")],
    ext="pdf", parent="S35", length="medium",
    style="Slide-deck PDF, 14 slides: title 'Teaching with AI - Kestrow faculty workshop, 4 March'; agenda; keynote "
          "placeholder (Dr. Vardakis); Tinderbox pilot overview; panel (Emeka, Prof. Wilberforce); Q&A. Footer 'v1 draft'.")

commit("support-handoff", "2027-02-25 16:40", "ask", "Define who owns tier-2 support after the writing-tool vendor hands off",
       M, BETT, project=WFT, basis="received", keywords=["tier-2 support", "handoff"],
       summary="Bettina asked who owns tier-2 support after the writing-tool vendor hands off; I'll put it in the requirements")
commit("svc-catalog", "2027-02-25 16:44", "task", "Draft the Kettleyard service catalog entry", BETT, M, project=HUB,
       status="waiting", basis="sent", keywords=["service catalog", "catalog entry"],
       summary="Waiting on Bettina for the Kettleyard service catalog entry")
art("S37", "chat", "2027-02-25 16:44", "DM Bettina / Mara: support handoff", [BETT, "c:support-handoff", "c:svc-catalog"],
    participants=n(BETT, M), length="short", challenges=["alias"],
    style="DM. Bettina (@bettina): 're writing tool: who owns tier-2 support once the vendor's implementation team hands off? "
          "i don't want ODS holding it by default'. Mara: 'good q - i'll put it in the requirements'. Mara: 'also any ETA on "
          "the kettleyard service catalog entry?' Bettina: 'next week-ish 🙃'.")

commit("dpa", "2027-02-25 17:10", "ask", "Review Scrivelo's data processing agreement", AGA, M, project=WFT,
       status="waiting", basis="sent", keywords=["DPA", "data processing agreement"],
       summary="Asked Agnieszka to review Scrivelo's data processing agreement")
commit("dsa", "2027-02-25 17:10", "ask", "Finalize the Saltmarren data-sharing agreement for baseline data", AGA, M,
       project=TCE, status="waiting", basis="sent", keywords=["data-sharing agreement", "DSA"],
       summary="Asked Agnieszka to finalize the Saltmarren data-sharing agreement")
art("S38", "email", "2027-02-25 17:10", "Scrivelo DPA review + Saltmarren DSA", [AGA, "c:dpa", "c:dsa"],
    frm=a(M), to=a(AGA), cc=a(DELPH), length="short", challenges=["alias"],
    style="Two asks: 'could you review Scrivelo's data processing agreement (attached)?' and 'where are we on the "
          "data-sharing agreement (DSA) for Saltmarren's baseline data?' Signs '— Mara'.")

# ======================================================================= Fri 26 Feb
commit("group-claims", "2027-02-26 09:20", "task", "Fix group-claim release for the Tinderbox SSO app", TEO, M, project=LAN,
       status="waiting", basis="received", keywords=["group claims", "KSD-20931"],
       summary="Teodor found group claims aren't released for Tinderbox SSO; waiting on an IdP patch (KSD-20931)")
commit("load-test", "2027-02-26 09:24", "task", "Run the Tinderbox load test (500 concurrent sessions)", SAANVI, M,
       project=LAN, status="waiting", basis="received", keywords=["load test", "500 concurrent"],
       summary="Saanvi's load-test plan is done; she'll run it once the tenant exists")
commit("runbook", "2027-02-26 09:28", "task", "Draft the Tinderbox tier-1 service desk runbook", GRETA, M, project=LAN,
       status="waiting", basis="received", keywords=["runbook", "tier-1"], summary="Greta is drafting the Tinderbox tier-1 runbook")
fact("lan-mem2", "2027-02-26 09:30", LAN, "members", [M, YUSRA, RAMONA, JACK, DIMA, EMEKA, INGRID, TEO, SAANVI, GRETA, HW],
     "Tinderbox team list now includes Teodor, Saanvi, Greta and Hyun-woo")
fact("lan-bl2", "2027-02-26 09:30", LAN, "blocker",
     "Real student data paused pending security review; SSO group claims not released (KSD-20931)",
     "Tinderbox also blocked on SSO group claims")
art("S39", "chat", "2027-02-26 09:30", "#tinderbox-core: SSO claims, load test plan, runbook", [
    SAANVI, GRETA, "c:group-claims", "c:load-test", "c:runbook", "lan-mem2", "lan-bl2"],
    participants=n(TEO, SAANVI, GRETA, YUSRA, M), length="short", challenges=["alias"],
    style="Teo: 'bad news: group claims aren't being released to tinderbox. IdP needs a vendor patch. ticket KSD-20931'. "
          "Saanvi (@saanvi): 'load test plan is done - 500 concurrent sessions, p95 < 2s target. i'll run it once the tenant "
          "exists'. Greta (@greta) joins: 'hi all - working on the tier-1 runbook for tinderbox'. Yusra: 'thanks all'.")

cres("process-map-done", "2027-02-26 11:15", "process-map", "done", "Rufus sent the transfer evaluation process map")
art("S40", "email", "2027-02-26 11:15", "Transfer evaluation: current process map", ["process-map-done"],
    frm=a(RUFUS), to=a(DELPH, M), length="short", challenges=["alias"],
    style="Methodical, short: 'Process map is in the shared drive (Transfer Eval > process-map-v1). 11 steps; the bottleneck "
          "is step 6, course-by-course equivalency lookup.' Signs 'Rufus Adekunle, Transfer Credit Coordinator'.")

commit("baseline-sample", "2027-02-26 13:05", "ask", "Send an anonymized sample of transfer transcripts for the baseline",
       DELPH, M, project=TCE, status="blocked", basis="reported", keywords=["anonymized sample", "transcript sample"],
       summary="Delphine's anonymized transcript sample is blocked until the DSA is signed")
fact("tce-bl1", "2027-02-26 13:05", TCE, "blocker", "Data-sharing agreement unsigned", "Saltmarren discovery blocked on the unsigned DSA")
fact("tce-s1", "2027-02-26 13:05", TCE, "summary",
     "Rufus delivered the process map (bottleneck: course-by-course equivalency lookup). Baseline data is blocked: no student "
     "records leave Saltmarren until the data-sharing agreement is signed, and Agnieszka is still finalizing it. Site visit "
     "on 2 March; readout targeted for 19 March.",
     "Saltmarren discovery waiting on the DSA")
art("S42", "email", "2027-02-26 13:05", "Re: Scrivelo DPA review + Saltmarren DSA", [
    "c:baseline-sample", "tce-bl1", "tce-s1", ("c:dsa", "direct", "template drafted; finalizing once Saltmarren counsel confirms the retention clause")],
    frm=a(AGA), to=a(M), cc=a(DELPH), thread=["S38"], length="medium",
    style="Numbered points. '1. DSA: template drafted; I will finalize once Saltmarren's counsel confirms the retention clause. "
          "Until it is signed, no student records - including Delphine's anonymized sample - leave Saltmarren. 2. DPA: on my "
          "list for next week.' Quotes Mara's email.")

cres("weekly-0226-done", "2027-02-26 16:50", "weekly-0226", "done", "Sent Sade the weekly update for the week of 22 Feb")
art("S43", "email", "2027-02-26 16:50", "Weekly update: w/e 26 Feb", ["weekly-0226-done"],
    frm=a(M), to=a(SADE), length="short",
    style="Three bullets + one risk. Bullets: Scrivelo/Penmarq shortlist; Tinderbox dummy-data mode, go-live 29 Mar; chargeback "
          "options on track for the review with Sade. Risk: SSO group claims need an IdP vendor patch.")

commit("risk-register", "2027-02-26 17:18", "ask", "Add the Tinderbox and Kettleyard risks to the program risk register",
       RAMONA, M, project=LAN, status="waiting", basis="reported", keywords=["risk register", "program risk register"],
       summary="Asked Ramona to add Tinderbox and Kettleyard risks to the program risk register")
commit("book-sade", "2027-02-26 17:20", "ask", "Book 30 minutes with Sade to review the chargeback options", LUCIA, M,
       project=CB, status="waiting", basis="reported", keywords=["30 minutes", "chargeback"],
       summary="Asked Lucía to book 30 minutes with Sade to review chargeback options")
cres("scorecard-tpl-done", "2027-02-26 17:22", "scorecard-tpl", "done", "Built the vendor scorecard template")
commit("penmarq-pricing", "2027-02-26 17:24", "ask", "Send Penmarq's three-campus pricing", JUNI, M, project=WFT,
       status="waiting", basis="reported", keywords=["three-campus pricing", "Penmarq"],
       summary="Asked Juniper for Penmarq's three-campus pricing before Monday's demo")
commit("no-training", "2027-02-26 17:25", "ask", "Answer whether Penmarq will commit to not training on student essays", JUNI,
       M, project=WFT, status="waiting", basis="reported", keywords=["no training", "student essays"],
       summary="Asked Juniper whether Penmarq will commit in writing to no training on student essays (Delphine's question)")
commit("baseline-analysis", "2027-02-26 17:28", "task", "Run the baseline accuracy analysis on the transfer transcript sample",
       M, DELPH, project=TCE, status="blocked", basis="reported", keywords=["baseline accuracy analysis", "accuracy analysis"],
       summary="Baseline accuracy analysis is mine but blocked until the transcript sample arrives (DSA)")
commit("sandbox-trial", "2027-02-26 17:26", "task", "Run a two-week Penmarq sandbox trial with Saltmarren writing-center staff",
       M, DELPH, project=WFT, basis="reported", keywords=["sandbox trial", "writing center"],
       summary="Plan: a two-week Penmarq sandbox trial with Saltmarren's writing center after the demo")
art("S44", "note", "2027-02-26 17:30", "Fri wrap", [
    "c:book-sade", "scorecard-tpl-done", "c:penmarq-pricing", "c:no-training", "c:sandbox-trial", "c:risk-register",
    "c:baseline-analysis"],
    frm=a(M), length="short", challenges=["alias"],
    style="Shorthand list: 'asked Lulu to book 30 min w/ Sade to review chargeback options'; 'scorecard template ✓'; "
          "'asked Juni for 3-campus pricing before Mon demo + whether they'll commit to no training on student essays (D. asked)'; "
          "'after Penmarq demo → 2-wk sandbox trial w/ writing center'; 'baseline accuracy analysis = me, blocked till the sample (DSA)'; "
          "'asked Mona to put tinderbox + kettleyard risks in the program risk register'; "
          "'next wk: v3 comments → Ilya, chargeback options, deck v2'.")
