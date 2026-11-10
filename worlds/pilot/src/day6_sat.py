"""Episode day 6: Saturday 2027-03-06 (checkpoint cp3)."""

from dsl import art, commit, cres, cupd, fact
from names import *  # noqa: F403

D = "2027-03-06"

art("X01", "email", f"{D} 07:00", "Campus Futures Forum: early-bird closes Monday", ["p-beatriz-solano"],
    frm=["Beatriz Solano <beatriz@campusfutures.example>"], to=a(M), noise=True, length="short", challenges=["noise"],
    noise_notes="Conference marketing: early-bird registration, call for lightning talks. No Tarrow content.",
    style="Conference promo email with registration link and unsubscribe footer.")

cres("wait-data-done", f"{D} 09:30", "wait-data", "done", "Analyzed Tillie's advising export: median 19-day wait for transfer students")
cupd("faq-acc", f"{D} 09:35", "faq", {"accepted": True}, "Agreed to write the faculty FAQ Ramona asked for")
fact("adv-next2", f"{D} 09:40", ADV, "next_step", "Scope the two-week discovery sprint with Tillie; no-show rates due from Tillie",
     "Advising next step: scope the sprint")
fact("adv-s2", f"{D} 09:40", ADV, "summary",
     "Tillie's Jan-Feb export shows transfer students wait a median 19 days for an advising appointment, versus 6 days for "
     "continuing students. Next: no-show rates from Tillie and scoping the two-week discovery sprint with her for Delphine.",
     "Advising data analyzed: 19-day median wait for transfer students")
art("X02", "note", f"{D} 09:40", "Voice memo: weekend brain dump", [
    "wait-data-done", "faq-acc", "adv-next2", "adv-s2",
    ("c:eval-plan", "direct", "eval plan v2 (matched-assignment learning gains) to Connie and Emeka next week"),
    ("c:pia", "direct", "transcribed as 'need to get Hannah the PIA by the twelfth' (means Hana Kobayashi-Reyes)"),
    ("c:onepager-sade", "direct", "'never sent Sade the early look; one-pager due Wednesday'"),
    ("c:impact", "direct", "'impact section for the postmortem by Monday'")],
    frm=a(M), length="medium", challenges=["endorsement", "worker_directive", "name_collision", "alias"],
    must_not_say=["that the one-pager was sent", "anything about the PIA walkthrough with Hana (whether it happened or not)"],
    noise_notes="Filler and asides: 'um', 'okay so', a reminder to call the plumber, 'did I leave the charger at Pellery'.",
    style="Auto-transcribed voice memo, Markdown with a header 'Voice memo - Sat 6 Mar 09:40 (auto-transcript)'. Run-on, "
          "filler words ('um', 'okay so'). Contents: 'ran Tillie's export - median nineteen days for transfer students versus "
          "six for continuing, that's the story; next is scoping the sprint with her once the no-show rates come in'; 'yes "
          "I'll do the faculty FAQ Ramona asked for'; 'eval plan v2 - matched-assignment learning gains - to Connie and Emeka "
          "next week'; 'need to get Hannah the PIA by the twelfth' (the transcriber spells the privacy officer Hana as "
          "'Hannah'); 'I never sent Sade the early look - one-pager due Wednesday'; 'impact section for the postmortem by "
          "Monday'; 'tell Dmitri the twelfth is fine'.")

cres("hw-approve-drop", f"{D} 11:12", "hw-approve", "dropped",
     "Hyun-woo corrected Ramona's notes: he never promised to approve the package on Monday")
commit("hw-comments", f"{D} 11:12", "task", "Send review comments on the Tinderbox security package", HW, M, project=LAN,
       status="waiting", basis="received", keywords=["review comments", "start the review"],
       summary="Hyun-woo will start reviewing the security package Monday and send comments when done")
commit("dataflow", f"{D} 11:12", "ask", "Add the data-flow diagram to the Tinderbox security package", M, HW, project=LAN,
       basis="received", keywords=["data-flow diagram", "add it to the package"],
       summary="Hyun-woo says the security package is missing the data-flow diagram")
art("X03", "email", f"{D} 11:12", "Re: Tinderbox security package", [
    "hw-approve-drop", "c:hw-comments", "c:dataflow",
    ("secpkg-done", "direct", "'I have the package you posted Thursday'")],
    frm=a(HW), to=a(M), cc=a(RAMONA, YUSRA), length="short",
    challenges=["correction", "scattered_evidence", "alias"],
    must_not_say=["any date by which the review comments will arrive"],
    style="Formal, sent Saturday late morning. 'I have the package you posted on Thursday. A correction to Ramona's notes from "
          "Wednesday: I did not say I would approve it on Monday, and I cannot commit to an approval date. I will start the "
          "review on Monday and send you review comments once I have been through it. One gap: the data-flow diagram is "
          "missing - please add it to the package.' Signs 'Hyun-woo Park'.")

commit("field-list", f"{D} 20:31", "ask", "Sign off the spec v2 field list for Dmitri", M, DIMA, project=LAN,
       due="2027-03-08", basis="received", keywords=["field list", "sign off"],
       summary="Dmitri asked me to sign off the spec v2 field list by Monday")
art("X04", "chat", f"{D} 20:31", "DM Dmitri / Mara: field list sign-off", [
    "c:field-list", ("c:context-api", "direct", "'still targeting the 12th'")],
    participants=n(DIMA, M), length="short", challenges=["alias"],
    style="Dmitri 20:14: 'context API skeleton is up in dummy-data mode. can you sign off the v2 field list by mon so i don't "
          "build the wrong thing? still targeting the 12th'. Mara 20:31: 'yes, mon'.")
