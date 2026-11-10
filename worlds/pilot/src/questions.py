"""Question specs for the pilot world (docs/formats.md 3.1). Symbols are resolved to IDs by build.py."""

from dsl import q
from names import *  # noqa: F403

# ======================================================================= cp1: end of Tuesday 2 March
q("cp1", "project_status", {"project": LAN}, text="What's the status of the Kestrow course assistant pilot?",
  name_form="the Kestrow course assistant pilot", challenges=["alias", "supersession", "worker_directive"])
q("cp1", "project_attr", {"project": LAN, "attribute": "budget"}, text="What is Tinderbox's budget?",
  challenges=["unobservable"])
q("cp1", "loop_due", {"commitment": "context-api"}, text="When is Dmitri's LMS context API due now?",
  name_form="Dmitri", challenges=["supersession"])
q("cp1", "i_owe", {"person": HW}, text="What do I currently owe Hugo?", name_form="Hugo",
  challenges=["alias", "implied_commitment", "draft_vs_sent"])
q("cp1", "decision_date", {"decision": "option2"}, text="When did we decide to host Tinderbox on the shared Kettleyard tenant?",
  challenges=["worker_directive"])
q("cp1", "i_owe", {"person": RAMI}, text="What do I owe Ramona at Brackwater?", name_form="Ramona",
  challenges=["name_collision"])
q("cp1", "owed_to_me", {"person": SOL}, text="What does Sol owe me?", name_form="Sol", challenges=["alias"])
q("cp1", "person_brief", {"person": DELPH}, text="I'm meeting Delphine on Thursday. What am I working on with her?",
  challenges=["scattered_evidence", "new_entity"])
q("cp1", "project_loops", {"project": WFT}, text="What loops are open on the writing tool bake-off?",
  name_form="the writing tool bake-off", challenges=["alias", "endorsement", "correction"])
q("cp1", "loop_owner", {"commitment": "sadebart"}, text="Who is setting up the Tinderbox ownership meeting with Sade and Bart Ngata?",
  challenges=["transfer", "name_collision"])
q("cp1", "focus_tomorrow", {}, challenges=["supersession"])
q("cp1", "person_attr", {"person": HANA, "attribute": "role"}, text="What is Hana's role?", name_form="Hana",
  challenges=["new_entity", "name_collision"])
q("cp1", "i_owe", {"person": SADE}, text="What do I owe Sade?", name_form="Sade",
  challenges=["alias", "implied_commitment"])
q("cp1", "project_changes", {"project": LAN, "since": "2027-02-25"}, text="What changed on Tinderbox since last Friday?",
  challenges=["supersession", "worker_directive", "transfer"])

# ======================================================================= cp2: end of Thursday 4 March
q("cp2", "project_status", {"project": HUB}, text="Where are we on the hub?", name_form="the hub",
  challenges=["alias", "batch_catchup", "correction", "transfer"])
q("cp2", "loop_owner", {"commitment": "gw-fix"}, text="Who is responsible for getting the gateway connection-pool fix into production?",
  challenges=["transfer", "correction", "batch_catchup"])
q("cp2", "loop_owner", {"commitment": "penmarq-pricing"}, text="Who at Pen Mark owes us the three-campus pricing?",
  name_form="Pen Mark", challenges=["transfer", "alias"])
q("cp2", "i_owe", {"person": ILYA}, challenges=["scattered_evidence", "batch_catchup"])
q("cp2", "owed_to_me", {"person": TEO}, text="What does Teo Lisofsky still owe me?", name_form="Teo Lisofsky",
  challenges=["alias", "silent_closure"])
q("cp2", "event_date", {"event": "refarch-done"}, text="When did I send Ilya my comments on the v3 reference architecture?",
  challenges=["correction"])
q("cp2", "event_date", {"event": "catering-done"}, text="When was the workshop catering order placed?",
  challenges=["correction", "silent_closure"])
q("cp2", "project_attr", {"project": LIB, "attribute": "status"},
  text="What is the current status of the library RA idea: active, paused, dormant, done or cancelled?",
  name_form="the library RA idea", challenges=["alias", "new_entity"])
q("cp2", "person_attr", {"person": MATEUS, "attribute": "salary_band"}, text="What salary band did we offer Mats?",
  name_form="Mats", challenges=["unobservable", "alias"])
q("cp2", "project_attr", {"project": CB, "attribute": "savings_target"},
  text="What savings target is Sade holding the chargeback model to?", name_form="the chargeback model",
  challenges=["unobservable"])
q("cp2", "project_changes", {"project": TCE, "since": "2027-02-28"}, text="What changed on the Saltmarren discovery this week?",
  name_form="the Saltmarren discovery", challenges=["restructuring", "alias"])
q("cp2", "i_owe", {"person": DELPH}, challenges=["scattered_evidence", "version_mismatch"])
q("cp2", "loop_due", {"commitment": "dsa-countersign"}, text="When is Delphine getting the DSA countersigned by?",
  challenges=["duplicate_signal"])
q("cp2", "focus_tomorrow", {}, challenges=["batch_catchup"])
q("cp2", "person_brief", {"person": EMEKA}, text="What am I working on with Emeka?", challenges=["implied_commitment", "scattered_evidence"])
q("cp2", "project_loops", {"project": LAN}, challenges=["silent_closure", "scattered_evidence", "endorsement"])
q("cp2", "owed_to_me", {"person": HW}, text="What is Hugo on the hook for?", name_form="Hugo",
  challenges=["alias", "scattered_evidence"])

# ======================================================================= cp3: end of week (Saturday 6 March)
q("cp3", "project_status", {"project": LAN}, challenges=["transfer", "reversal", "supersession"])
q("cp3", "project_attr", {"project": LAN, "attribute": "owner"}, text="Who owns Tinderbox now?",
  challenges=["transfer"])
q("cp3", "project_attr", {"project": LAN, "attribute": "target_date"}, text="What's the go-live date for Tinderbox?",
  challenges=["supersession"])
q("cp3", "loop_due", {"commitment": "context-api"}, text="When is the context API due?", challenges=["supersession"])
q("cp3", "project_status", {"project": WFT}, text="What's the status of the bake-off?", name_form="the bake-off",
  challenges=["version_mismatch", "transfer", "worker_directive", "alias"],
  extra_rubric=[{"text": "Scorecard v2 totals: Penmarq 76, Scrivelo 71 (the 78/74 in the 4 March email were v1 totals)",
                 "keywords": [["76"], ["71"]], "stale": [["78"], ["74"]], "critical": True,
                 "support": ["F05", "H07"]}])
q("cp3", "project_changes", {"project": CB, "since": "2027-02-28"}, text="What changed on the chargeback model this week?",
  name_form="the chargeback model", challenges=["reversal", "alias"])
q("cp3", "decision_date", {"decision": "three-courses"}, text="When did we decide to limit Tinderbox to three courses?",
  challenges=["reversal"])
q("cp3", "i_owe", {"person": HW}, text="What do I owe Hyun-woo?", challenges=["correction", "scattered_evidence"])
q("cp3", "i_owe", {"person": RAMONA}, text="What do I owe Mona?", name_form="Mona",
  challenges=["endorsement", "alias", "name_collision"])
q("cp3", "project_attr", {"project": WFT, "attribute": "budget"}, text="What's the budget ceiling for the writing feedback tool?",
  challenges=["unobservable"])
q("cp3", "event_date", {"event": "sync-done"}, text="When did I hold the v4 follow-up sync with Ilya?",
  challenges=["weak_evidence", "acceptance_vs_occurrence"])
q("cp3", "focus_tomorrow", {}, challenges=["implied_commitment"])
q("cp3", "person_brief", {"person": RAMONA}, challenges=["name_collision", "correction"])
q("cp3", "project_loops", {"project": ADV}, challenges=["restructuring", "new_entity"])
q("cp3", "project_loops", {"project": LIB}, challenges=["restructuring", "endorsement"])
q("cp3", "owed_to_me", {"person": SOL}, text="What is Marisol on the hook for?")
q("cp3", "person_attr", {"person": TILLIE, "attribute": "role"}, text="What does Tillie do at Saltmarren?",
  name_form="Tillie", challenges=["alias", "new_entity"])
q("cp3", "owed_to_me", {"person": XIM}, challenges=["transfer", "noise"])
q("cp3", "project_changes", {"project": WS, "since": "2027-03-02"}, text="What changed on the faculty workshop since Wednesday?",
  name_form="the faculty workshop", challenges=["new_entity", "correction"])
q("cp3", "i_owe", {"person": BART}, text="What do I owe Bart Ngata?", name_form="Bart Ngata",
  challenges=["name_collision", "correction", "endorsement"])
q("cp3", "i_owe", {"person": HANA}, text="What do I owe Hana?", name_form="Hana",
  challenges=["name_collision", "weak_evidence", "acceptance_vs_occurrence"])
