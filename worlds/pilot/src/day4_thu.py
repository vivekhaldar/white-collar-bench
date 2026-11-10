"""Episode day 4: Thursday 2027-03-04 (checkpoint cp2). Mara is back; the Wednesday batch (day3_wed.py) arrives 07:41-07:43.

Mara's schedule: DMs 08:25-09:58, incident standup 10:00-10:28, Delphine check-in 11:00-11:30, chat posts before the
workshop (12:20-12:50), workshop 13:00-16:00, evening debrief 21:30.
"""

from dsl import art, commit, cres, cupd, decide, fact, project, split
from names import *  # noqa: F403

D = "2027-03-04"
NOFOLD = "Do NOT fold long iCalendar lines: keep DESCRIPTION and any join link on one line each. "

art("H00", "calendar", f"{D} 07:50", "Declined: Scrivelo - next steps (Fri 5 Mar 11:00)", [],
    frm=a(M), to=a(GREG), length="short", challenges=["noise"], noise=True,
    noise_notes="A decline of a vendor's sales call; no project facts.",
    style=NOFOLD + "METHOD:REPLY. ORGANIZER Gregor Lindahl, ATTENDEE Mara PARTSTAT=DECLINED. SUMMARY 'Scrivelo - next steps "
          "(implementation walkthrough)'. DTSTART 2027-03-05T11:00, DTEND 11:30. COMMENT 'Thanks Gregor - we'll come back to "
          "you once the RFQ is out.'")

cres("badges-done", f"{D} 08:25", "badges", "done", "Sent Ramona the speaker list for badges")
cres("deck-v3-done", f"{D} 08:25", "deck-v3", "done", "Sent Ramona workshop deck v3 (room change, Connie's panel question)")
commit("tinderbox-2min", f"{D} 08:33", "ask", "Give a two-minute Tinderbox update at the workshop opening", M, RAMONA,
       project=WS, basis="received", keywords=["two-minute", "Tinderbox update"],
       summary="Ramona asked me to open the workshop with a two-minute Tinderbox update")
art("H02", "chat", f"{D} 08:52", "DM Ramona / Mara: back from offsite", [
    "badges-done", "deck-v3-done", "c:tinderbox-2min",
    ("c:risk-register", "direct", "Mara chases; Ramona: 'oops not yet, will do it today' (no confirmation follows)"),
    ("catering-done", "correction", "'the catering order actually went in Monday the 1st'"),
    ("ramona-cover-done", "direct", "standup notes are in the folder")],
    participants=n(M, RAMONA), length="short", challenges=["correction", "alias", "scattered_evidence"],
    noise_notes="Ramona asks how the offsite food was; Mara: 'beige'.",
    style="Mara 08:25: 'back. thanks for covering yesterday 🙏 speaker list for name badges + deck v3 attached (new room on "
          "the title slide, Connie's reworded panel question)'. Ramona 08:28: 'np! standup notes are in the folder'. Ramona "
          "08:30: 'oh - correction on catering: I said \"confirmed\" yesterday but the order actually went in Monday the 1st, "
          "so we've been fine all week'. Ramona 08:33: 'can you do a 2-min Tinderbox update at the opening?' Mara: 'sure'. Mara "
          "08:36: 'also - did the tinderbox + kettleyard risks make the program risk register? add the gateway outage pls'. "
          "Ramona 08:40: 'oops not yet 🙈 will do it today - tinderbox, kettleyard + the outage'. Ramona 08:52: 'ok running to "
          "Pellery to check the room'. (Nothing confirms the risk register was updated.)")
art("H02D", "document", f"{D} 08:52", "Teaching with AI - deck v3", [("deck-v3-done", "direct", "deck v3 itself")],
    ext="pdf", parent="H02", sent=f"{D} 08:25", length="medium", challenges=["supersession"],
    style="Same deck as v2, 16 slides, footer 'v3 - final'. Title slide now says Pellery Hall 204. Panel slide carries "
          "Connie's reworded question: 'What would count as evidence that students learned more?'. Tinderbox slide unchanged.")

commit("emeka-two-part", f"{D} 09:41", "task", "Send Emeka the faculty onboarding guide and set up a Tinderbox sandbox login for his TA",
       M, EMEKA, project=LAN, basis="sent", keywords=["onboarding guide", "sandbox login"],
       summary="Told Emeka I'd send the onboarding guide and set up his TA's sandbox login; only the guide went out")
cres("chem-rubric-done", f"{D} 09:58", "chem-rubric", "done", "After my nudge Emeka sent the CHEM 110 assignment rubric")
art("H03", "chat", f"{D} 09:58", "DM Emeka / Mara: guide, TA login, rubric", ["c:emeka-two-part", "chem-rubric-done"],
    participants=n(EMEKA, M), length="short", challenges=["implied_commitment", "scattered_evidence"],
    must_not_say=["that the TA login has been set up", "a date by which the TA login is needed"],
    style="DM. Emeka (Wed 3 Mar 16:10): 'before things get busy - could you send me the faculty onboarding guide and set up a "
          "Tinderbox sandbox login for my TA? 🙏'. Mara (Thu 09:41): 'onboarding guide attached. I'll set up your TA's sandbox "
          "login after the workshop - send me their name? also still need that CHEM 110 assignment rubric for the eval plan'. "
          "Emeka 09:58: 'attached!! sorry, it's been sitting in my drafts since last week. TA name to follow!' Only part one "
          "of Mara's promise (the guide) is delivered.")

# ---------------------------------------------------------------- incident standup 10:00
cupd("gw-reopen", f"{D} 10:05", "gw-fix", {"status": "open", "debtor": ILYA},
     "Gateway fix turned out to be staging-only; reopened and Ilya now owns it")
commit("rotate-key", f"{D} 10:12", "ask", "Rotate the Kettleyard API key pasted in #kettleyard on Tuesday", BARTOSZ, HW,
       others=[M], project=HUB, status="waiting", basis="reported", keywords=["API key", "rotated"],
       summary="Hyun-woo found Tuesday's pasted API key still active and asked Bartosz to rotate it")
cres("rotate-done", f"{D} 10:25", "rotate-key", "done", "Bartosz rotated and revoked the leaked Kettleyard API key")
commit("impact", f"{D} 10:22", "task", "Write the Tinderbox impact section for the gateway postmortem", M, SADE, project=HUB,
       due="2027-03-08", basis="reported", keywords=["impact section", "postmortem"],
       summary="Answering Sade's ask, I'll write the Tinderbox impact section of Ilya's outage postmortem by Monday 8 March")
commit("ilya-quota", f"{D} 10:24", "ask", "Confirm the Tinderbox tenant quota before the load test rerun", ILYA, M,
       project=HUB, status="waiting", basis="reported", keywords=["tenant quota", "load test rerun"],
       summary="Asked Ilya to confirm the Tinderbox tenant quota before Saanvi reruns the load test")
cres("svc-catalog-drop", f"{D} 10:27", "svc-catalog", "dropped",
     "Chased Bettina on the service catalog entry; she dropped it (to be rewritten against v5)")
fact("hub-s5", f"{D} 10:28", HUB, "summary",
     "The connection-pool fix reported on 3 March only reached staging; production is still on the old gateway config. Ilya "
     "took over as incident owner on 4 March. Sade wants a postmortem by 10 March and I am writing the Tinderbox impact "
     "section. The leaked API key was rotated; Bettina dropped the service catalog entry until v5.",
     "Gateway fix was staging-only; Ilya now owns the incident")
art("H04", "transcript", f"{D} 10:35", "Kettleyard incident standup (Thu)", [
    "gw-reopen", "c:rotate-key", "rotate-done", "c:impact", "c:ilya-quota", "svc-catalog-drop", "hub-s5"],
    participants=n(ILYA, BARTOSZ, BETT, HW, SAANVI, M), sent=f"{D} 10:28", length="long",
    challenges=["correction", "transfer", "privacy", "implied_commitment", "name_collision"],
    must_not_say=["the API key string itself"],
    noise_notes="Opens with two minutes of 'can you hear me' and Bettina's dog; Ilya and Bettina argue status-page wording.",
    style="WebVTT, 28 min. Ilya: 'Bart's fix yesterday only went to staging - prod is still on the old pool config. I'm taking "
          "the incident from here.' Bartosz, sheepish: 'yeah, my bad.' Hyun-woo: 'separately - the key pasted in #kettleyard "
          "on Tuesday is still active in the audit log. Rotate it now.' Bartosz (minutes later): 'rotated, old one revoked.' "
          "Mara: 'Sade wants Tinderbox's impact in the postmortem - I'll write that section by Monday.' Mara: 'Ilya, can you "
          "confirm our tenant quota before Saanvi reruns?' Ilya: 'will check.' At the end Mara: 'Tina, unrelated - the "
          "service catalog entry?' Bettina: 'Honestly, let's drop it. The catalog template changes with v4 - I'll write it "
          "fresh against v5.' Speaker drift: Ilya's label changes from 'Ilya Marchetti' to 'iPhone (3)' after a reconnect.")

# ---------------------------------------------------------------- Delphine check-in 11:00-11:30 (recap only, no recording kept)
cres("usecase-done", f"{D} 10:40", "usecase", "done", "Sent Delphine the writing-feedback use-case list before our check-in")
fact("delph-role", f"{D} 11:05", DELPH, "role", "Registrar", "Delphine confirmed as Registrar (no longer interim)")
commit("dsa-countersign", f"{D} 11:20", "task", "Get the DSA countersigned by Saltmarren's VP", DELPH, M, project=TCE,
       status="waiting", due="2027-03-09", basis="received", keywords=["countersign", "DSA"],
       summary="Delphine will get the DSA countersigned by next Tuesday (9 March)")
decide("data-terms", f"{D} 11:25", "Weight data terms at 30% in the writing-tool scorecard", [M, DELPH], project=WFT,
       keywords=["data terms", "30%"], summary="Agreed with Delphine to weight data terms at 30% in the scorecard")
art("H04B", "meeting_notes", f"{D} 11:35", "Huddlescribe recap: Delphine / Mara check-in", [
    "usecase-done", "delph-role", "d:data-terms",
    ("c:dsa-countersign", "second-hand", "recap says only 'Delphine to get the DSA countersigned by Tuesday' (no 'next')"),
    ("c:essay-volumes", "direct", "'Delphine to email last year's ENGL 101/102 essay volumes after the call'")],
    frm=["Huddlescribe Recaps <recaps@huddlescribe.example>"], participants=n(DELPH, M), length="medium",
    challenges=["alias", "duplicate_signal", "supersession"],
    noise_notes="Summary opens with 'Delphine and Mara discussed weekend plans and the Saltmarren parking situation'.",
    style="AI recap (the only record of this 30-minute call). Summary: Mara walked Delphine through the writing-feedback "
          "use-case list she emailed at 10:40; Delphine shared that she has been confirmed as Registrar (no longer interim); "
          "they agreed to weight data terms at 30% in the scorecard because of legal's data-term preview; Delphine floated "
          "treating the advising scheduling problem separately from the transfer work (no decision yet). Action items: "
          "'Delphine to get the DSA countersigned by Tuesday'; 'Delphine to email last year's ENGL 101/102 essay volumes "
          "after the call'; 'Mara to send the scorecard summary today'. Disclaimer 'AI-generated, may contain errors'.")

project(ADV, f"{D} 11:52", "Saltmarren Advising Scheduling Discovery",
        ["the advising scheduling work", "advising scheduling discovery", "the advising bottleneck", "the advising thing"],
        summary="Advising scheduling discovery at Saltmarren (split from the transfer discovery)",
        state="Split out of the Saltmarren transfer discovery on 4 March: transfer students wait weeks for advising "
              "appointments. I am analyzing the advising wait-time data and scoping a two-week discovery sprint with Tillie, "
              "who leads the campus side.",
        status="active", owner=M, phase="scoping", sponsor=DELPH, members=[M, TILLIE, DELPH], orgs=["o-saltmarren"],
        _archetype="split_from_pivoting_discovery")
split("tce-split", f"{D} 11:55", TCE, [ADV], {"wait-data": ADV},
      "Advising scheduling split out of the Saltmarren transfer discovery into its own project")
commit("advising-sprint", f"{D} 11:56", "task", "Scope a two-week advising scheduling discovery sprint with Tillie", M, DELPH,
       others=[TILLIE], project=ADV, basis="received", keywords=["two-week", "discovery sprint"],
       summary="Delphine asked me to scope a two-week advising scheduling sprint with Tillie")
fact("tce-ph3", f"{D} 11:57", TCE, "phase", "discovery (waiting on the DSA)", "Transfer discovery back to its original scope, waiting on the DSA")
fact("tce-next3", f"{D} 11:57", TCE, "next_step", "VP countersignature on the DSA (expected 9 March), then the baseline sample",
     "Transfer discovery next step: the DSA countersignature")
fact("tce-s3", f"{D} 11:57", TCE, "summary",
     "Advising scheduling has been split into its own project (4 March). This project stays on transfer transcript "
     "evaluation: the DSA is out for signature and Delphine expects the VP's countersignature by 9 March; baseline data and "
     "my baseline analysis stay blocked until then. Readout targeted for 19 March.",
     "Transfer discovery refocused after the split")
art("H05", "email", f"{D} 11:58", "Following up from our call: weights, DSA, advising", [
    "d:data-terms", "delph-role", "c:dsa-countersign", EZINNE, ADV, "tce-split", "c:advising-sprint", "tce-ph3",
    "tce-next3", "tce-s3", ("c:essay-volumes", "direct", "'Rufus is pulling last year's ENGL 101/102 essay volumes - Monday'")],
    frm=a(DELPH), to=a(M), cc=a(LIONEL, EZINNE), length="medium",
    challenges=["restructuring", "new_entity", "alias", "supersession"],
    style="Warm and direct, sent Thursday 4 March. '1) As agreed on the call, let's weight data terms at 30% given Agnieszka's "
          "note. 2) News: I've been confirmed as Registrar as of this week - no more \"interim\"! 3) DSA: Ezinne (Dr. "
          "Marlowe-Abara, our VP for Academic Affairs, cc'd) will countersign - I'll get it back to you by next Tuesday. 4) "
          "Let's treat advising scheduling as its own project, separate from the transfer work - Tillie leads our side. Can you "
          "scope a two-week sprint with her? 5) Essay volumes: Rufus is pulling last year's ENGL 101/102 numbers - you'll have them "
          "Monday.' Signature now reads "
          "'Delphine Arceneaux, Registrar'. Uses 'next Tuesday' (= 9 March) rather than a date.")

cres("scorecard-done", f"{D} 12:20", "scorecard", "done", "Sent Delphine the vendor scorecard summary")
art("H06", "email", f"{D} 12:20", "Vendor scorecard: summary", ["scorecard-done"],
    frm=a(M), to=a(DELPH, LIONEL), cc=a(CLEM), length="medium", challenges=["version_mismatch", "scattered_evidence"],
    must_not_say=["the v2 totals (Penmarq 76 / Scrivelo 71) in the body"],
    style="Body summarizes totals from the OLD v1 weights: 'Scrivelo 78, Penmarq 74 - Scrivelo ahead on feedback quality.' "
          "'Sheet attached.' Lionel's internal-build column is not in it yet ('internal-build column coming'). Signs '— Mara'. "
          "Clement is on Cc.")
art("H07", "document", f"{D} 12:20", "WFT vendor scorecard v2", [
    ("scorecard-done", "direct", "the scorecard"), ("d:data-terms", "direct", "weights tab: data terms 30%")],
    ext="xlsx", parent="H06", length="medium", challenges=["version_mismatch"],
    style="Spreadsheet 'WFT vendor scorecard v2'. Tab 'weights': feedback quality 30%, data terms 30% (raised from the v1 "
          "weight, note 'per Delphine 4 Mar'), LMS integration 20%, accessibility 10%, cost 10%. Tab 'scores': weighted "
          "totals Penmarq 76, Scrivelo 71. Tab 'v1 (archived)': Scrivelo 78, Penmarq 74. No internal-build column. Do not "
          "print the old v1 data-terms weight as a number.")

# ---------------------------------------------------------------- Tinderbox channel (before the workshop)
cres("claims-done", f"{D} 12:31", "group-claims", "done", "Group claims now released for Tinderbox SSO (Saanvi confirmed)")
cres("specv2-done", f"{D} 12:40", "spec-v2", "done", "Posted Tinderbox interface spec v2 (event-based context API)")
cres("secpkg-done", f"{D} 12:44", "secpkg", "done", "Posted the Tinderbox security review package (with sub-processor list) for Hyun-woo")
fact("lan-bl5", f"{D} 12:50", LAN, "blocker",
     "Real student data paused pending security review; load test blocked until the gateway is fixed and the tenant quota confirmed",
     "SSO no longer blocks Tinderbox")
fact("lan-s6", f"{D} 12:50", LAN, "summary",
     "SSO group claims now come through (confirmed 4 March). I posted interface spec v2 (event-based context API) and the "
     "security review package with the sub-processor list on 4 March; real data stays paused until Hyun-woo reviews it. "
     "The load test waits on the gateway fix and Ilya's quota check. Context "
     "API due 10 March; go-live 29 March.",
     "Tinderbox: spec v2 and security package delivered; SSO fixed")
art("H08", "chat", f"{D} 12:50", "#tinderbox-core: SSO works, spec v2, security package", [
    ("claims-done", "implied", "Saanvi: SSO login works with her test account and group claims come through now"),
    "specv2-done", "secpkg-done", "lan-bl5", "lan-s6"],
    participants=n(SAANVI, M, DIMA, HW, TEO), length="short",
    challenges=["silent_closure", "scattered_evidence", "alias"],
    noise_notes="Saanvi also asks who left a laptop charger in Huddle 2B.",
    style="Saanvi 12:31: 'SSO login works with my test account - group claims come through now 🎉' (nobody says the ticket "
          "is closed; Teo only reacts with a thumbs-up). Mara 12:40: 'spec v2 is up - event-based context API, field list in "
          "§3' (file attached). Mara 12:44: '@hpark security package is in the Tinderbox folder, incl. the sub-processor list. "
          "off to the workshop'. Dmitri 12:50: 'reading v2. if this changes again...'. Saanvi: 'load test still parked till "
          "the gateway's really fixed + ilya confirms quota'.")
art("H09", "document", f"{D} 12:50", "Tinderbox LMS interface spec v2", [("specv2-done", "direct", "spec v2 itself")],
    ext="md", parent="H08", length="medium", challenges=["supersession"],
    style="Markdown 'Tinderbox LMS interface spec - v2 (4 Mar), supersedes v1 (22 Feb)'. Event-based context API: LMS publishes "
          "course.updated / enrollment.changed events; assistant subscribes; §3 field list; auth via Kestrow IdP group claims; "
          "dummy-data note. Change log vs v1.")

cres("tinderbox-2min-done", f"{D} 13:10", "tinderbox-2min", "done", "Gave the two-minute Tinderbox update at the workshop opening")
cres("sadebart-done", f"{D} 15:18", "sadebart", "done", "Lucía booked Sade, Bart Ngata and me for Fri 5 March 10:30")
art("H10", "calendar", f"{D} 15:18", "Invite: Tinderbox: operating model & ownership", ["sadebart-done"],
    frm=a(LUCIA), to=a(SADE, BART, M, YUSRA, RAMONA), length="short", challenges=["silent_closure", "privacy", "name_collision"],
    secrets=["https://meet.tarrow.example/j/8150463327?pwd=Lt4nW9"],
    style=NOFOLD + "METHOD:REQUEST from Lucía. SUMMARY 'Tinderbox: operating model & ownership'. DTSTART 2027-03-05T10:30, DTEND "
          "11:15. ATTENDEES Sade, Bart Ngata (Kestrow CIO), Mara; Yusra and Ramona optional. DESCRIPTION 'Join: "
          "https://meet.tarrow.example/j/8150463327?pwd=Lt4nW9'.")

cres("offer-done", f"{D} 16:15", "offer", "done", "Mateus accepted the offer")
fact("mateus-role", f"{D} 16:21", MATEUS, "role", "Incoming Staff ML Engineer (start 29 March)",
     "Mateus accepted; he is now the incoming staff ML engineer")
fact("hire-ph5", f"{D} 16:21", HIRE, "phase", "offer accepted", "MLE hire: offer accepted")
fact("hire-td1", f"{D} 16:21", HIRE, "target_date", "2027-03-29", "Mateus's start date set for 29 March")
fact("hire-s2", f"{D} 16:21", HIRE, "summary", "Mateus Okonedo accepted the offer on 4 March; start date 29 March.",
     "MLE hire: offer accepted")
art("H11", "chat", f"{D} 16:24", "DM Marisol / Mara: Mateus accepted", [
    "offer-done", "mateus-role", "hire-ph5", "hire-td1", "hire-s2"],
    participants=n(SOL, M), length="short", challenges=["alias"],
    must_not_say=["salary or offer amount"],
    style="DM. Marisol 16:21: 'Mats accepted the offer 🎉 start date Monday 29 March - he'll be our incoming staff ML "
          "engineer. kicking off onboarding paperwork'. Mara 16:24 (out of the workshop): 'excellent. tell Sade?' Marisol: "
          "'already did'.")

fact("lib-status", f"{D} 16:55", LIB, "status", "active", "Library research assistant revived by Ines's booking")
fact("lib-ph2", f"{D} 16:55", LIB, "phase", "exploration", "Library RA back in exploration")
fact("lib-mem2", f"{D} 16:55", LIB, "members", [M, RAMI, INES], "Ines joins the library RA thread")
fact("lib-next2", f"{D} 16:55", LIB, "next_step", "Call with Ines and Ramona Iturbe on 9 March",
     "Library RA next step: the 9 March call")
fact("lib-s2", f"{D} 16:55", LIB, "summary",
     "Revived on 4 March: Ines Vardakis (Eskerfield) booked a call for 9 March with me and Ramona Iturbe to explore an "
     "evaluation partnership on the library research assistant. I still owe Ramona Iturbe the concept note; Ines asked for "
     "background notes, which I have not agreed to yet.",
     "Library research assistant revived")
commit("ines-notes", f"{D} 16:55", "ask", "Send Ines background notes on the library research assistant", M, INES,
       project=LIB, accepted=False, basis="received", keywords=["background notes", "library research assistant"],
       summary="Ines asked for background notes on the library idea; I hedged (not yet agreed)")
art("H12", "calendar", f"{D} 16:55", "Invite: Library research assistant - evaluation partnership?", [
    "lib-ph2", "lib-mem2", "lib-next2", ("c:ines-notes", "direct", "Ines's ask for background notes")],
    frm=a(INES), to=a(M), cc=a(RAMI), length="short", challenges=["privacy", "name_collision", "endorsement"],
    secrets=["https://eskerfield.example/meet/ivardakis-0309"],
    style=NOFOLD + "METHOD:REQUEST from Ines Vardakis (external organizer). SUMMARY 'Library research assistant - evaluation "
          "partnership?' DTSTART 2027-03-09T11:00 DTEND 11:45. ATTENDEES Mara, Ramona Iturbe (Brackwater). DESCRIPTION: 'After "
          "our chat at the workshop - Eskerfield could evaluate a library research assistant with Brackwater. If you have any "
          "background notes, send them over whenever. Join: https://eskerfield.example/meet/ivardakis-0309'. This single "
          "booking is the first activity on the library idea in weeks.")

cres("gw-done", f"{D} 17:20", "gw-fix", "done", "Ilya deployed the gateway fix to production and verified it")
fact("hub-bl2", f"{D} 17:24", HUB, "blocker", None, "Gateway outage resolved")
fact("hub-s6", f"{D} 17:24", HUB, "summary",
     "Ilya deployed the connection-pool fix to production on 4 March and closed the gateway incident after 30 clean minutes. "
     "Postmortem due to Sade 10 March (Ilya owns it; I write the Tinderbox impact section). Reference architecture v4 is out "
     "with a follow-up sync planned for 5 March.",
     "Gateway incident closed; postmortem due 10 March")
art("H13", "chat", f"{D} 17:24", "#kettleyard: prod fix deployed", ["gw-done", "hub-bl2", "hub-s6"],
    participants=n(ILYA, BARTOSZ, SAANVI, M), length="short", challenges=["correction"],
    must_not_say=["that the load test has been rebooked or rescheduled"],
    style="Ilya 17:20: 'pool fix deployed to prod for real this time - 30 min clean, closing the incident. postmortem to Sade "
          "by wed. v4 sync still on for tomorrow.' Bartosz: '🙏'. Saanvi reacts 🎉 (no message). Mara: 'ty'.")

fact("ws-ph2", f"{D} 16:00", WS, "phase", "delivered", "Workshop delivered")
fact("ws-s3", f"{D} 21:30", WS, "summary",
     "Workshop held 4 March in Pellery Hall 204: 38 of 61 registrants attended. Connie's panel point - satisfaction is not "
     "learning - landed; nine faculty asked for a community of practice and Emeka volunteered to co-lead. Survey results "
     "and wrap-up pending from Ramona.",
     "Workshop delivered: 38 attended")
commit("ines-paper", f"{D} 21:30", "task", "Co-author a short paper with Ines on the Tinderbox evaluation", M, INES,
       project=LAN, accepted=False, basis="reported", keywords=["short paper", "co-author"],
       summary="Ines suggested we co-author a short paper on the Tinderbox evaluation (not agreed)")
art("H14", "meeting_notes", f"{D} 21:30", "Debrief: Teaching with AI workshop", [
    "ws-ph2", "ws-s3", "c:ines-paper", "tinderbox-2min-done", "lib-status", "lib-s2",
    ("c:eval-plan", "direct", "'eval plan → switch to matched-assignment learning gains, per Connie'"),
    ("c:ines-notes", "hedged", "'Ines would like background notes - maybe, if the concept note gets written; not promising'")],
    frm=a(M), participants=n(M, RAMONA, INES, EMEKA, CONNIE), sent=f"{D} 21:30", length="medium",
    challenges=["endorsement", "alias"],
    noise_notes="Aside about the projector dying for five minutes and the cookies running out by 14:30.",
    style="Mara's late-evening debrief, Markdown. '38 came (61 reg'd). did the 2-min tinderbox update at the opening. Ines "
          "keynote solid. Connie's panel: \"satisfaction ≠ learning\" - she's right → eval plan: switch to "
          "matched-assignment learning gains.' '9 faculty want a CoP; Emeka volunteered to co-lead.' 'Ines: maybe co-author a "
          "short paper on the Tinderbox eval? - not now.' 'Ines also grabbed me re the library RA - so the library RA is "
          "active again: call Tue 9th w/ her + Ramona I. She'd like background notes - maybe, if I finally write "
          "the concept note; not promising.'")
