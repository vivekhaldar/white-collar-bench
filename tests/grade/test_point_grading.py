"""Point grading of answers with context: issues #3 (text) and #4 (dates).

Agents often put context next to a correct value ("Privacy Officer at Dorcliff State College",
"2027-12-31 (moved from 22 Dec on 9 Nov)"). These tests pin down that such answers score 1
and that the rejections around them still hold: hedges, another entity of the same kind, a
rival value stated as current, negation, a stale value as current, and ambiguous dates.

The cases copy the essentials of real answers from a Qwen3.8-27B + Pi run
(results/2026-11-11-qwen3.8-27b-pi). Dev worlds are regenerated from time to time, so their
cases are rebuilt here as small hand-made gold states; pilot cases (hand-authored, stable)
use the pilot itself.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wcb.grade.answers import ScoreContext, point_support, score_question, text_matches
from wcb.grade.judge import HeuristicJudge
from wcb.questions.build import build_question, load_specs
from wcb.util.dates import leading_date, normalize_date_text
from wcb.util.text import normalize
from wcb.world.model import World
from wcb.world.state import state_at

J = HeuristicJudge()
PILOT = Path(__file__).parents[2] / "worlds" / "pilot"


# ---------------------------------------------------------------- hand-built gold states
def person(name, forms=(), *, history=None, **attrs):
    return {"kind": "person", "name": name, "surface_forms": list(forms), "attrs": attrs,
            "attr_history": history or {}}


def org(name, forms=(), *, domain):
    return {"kind": "org", "name": name, "surface_forms": list(forms),
            "attrs": {"kind": "internal", "domain": domain}}


def project(name, forms=(), *, phases=(), **attrs):
    history = {"phase": [{"value": p, "t": "2027-01-01T09:00:00"} for p in phases]}
    return {"kind": "project", "name": name, "surface_forms": list(forms), "attrs": attrs,
            "attr_history": history}


def context(entities: dict, *, worker: str, date: str = "2027-11-13") -> ScoreContext:
    """A ScoreContext over hand-made entities, with the alias table `World` would build."""
    table: dict[str, set[str]] = {}
    for eid, e in entities.items():
        for form in [e["name"], *e["surface_forms"]]:
            table.setdefault(normalize(form).lstrip("@"), set()).add(eid)
    return ScoreContext(
        alias_table=table, entities=entities, worker=worker, date=date, delivered=set()
    )


def attr_question(subject: str, attribute: str, text: str, value: str) -> dict:
    template = "project_attr" if subject.startswith("pr-") else "person_attr"
    key = "project" if template == "project_attr" else "person"
    return {
        "id": "q-x",
        "type": "point",
        "template": template,
        "params": {key: subject, "attribute": attribute},
        "text": text,
        "answerable": True,
        "challenges": [],
        "support": ["em-0001"],
        "gold": {"kind": "text", "value": value, "entity": None, "accept": [value]},
    }


def date_question(text: str, value: str) -> dict:
    return {
        "id": "q-x",
        "type": "point",
        "template": "loop_due",
        "params": {"commitment": "c-001"},
        "text": text,
        "answerable": True,
        "challenges": [],
        "support": ["em-0001"],
        "gold": {"kind": "date", "value": value, "entity": None, "accept": [value]},
    }


def base(q: dict, value: str, ctx: ScoreContext, **extra) -> float:
    answer = {"type": "point", "abstain": False, "value": value, "cites": ["em-0001"], **extra}
    return score_question(q, answer, J, ctx).base


# Systemwide office of a university system (gen-s4-w2, cp2 q-022).
SLIO = {
    "p-me": person("Ines Adeyemi", ["Ines"], org="o-slio", role="Program Lead"),
    "o-slio": org("Systemwide Learning Innovation Office", ["SLIO", "the SLIO team"],
                  domain="drayhurst.example"),
    "o-dus": org("Drayhurst University System", ["Drayhurst", "DUS"], domain="drayhurst.example"),
    "o-holfield": org("Holfield State College", ["Holfield"], domain="holfield.drayhurst.example"),
    "p-nomvula": person("Nomvula Ndlovu", ["Nomvula"], org="o-slio",
                        role="Information Security Manager", relationship="peer"),
    "p-meera": person("Meera Bondarenko", ["Meera"], org="o-slio",
                      role="Head of Learning Services", relationship="peer"),
}

# A project that moved from logistics into delivery (gen-s7-w2, cp2 q-027).
WORKSHOP = {
    "p-me": person("Hiba Rahman", ["Hiba"], org="o-aldervale", role="Program Lead"),
    "o-aldervale": org("Aldervale University", ["Aldervale"], domain="aldervale.example"),
    "p-bolat": person("Bolat Oyelami", ["Bolat"], org="o-aldervale", role="Head of Learning"),
    "p-anastasia": person("Anastasia Mizrahi", ["Anastasia"], org="o-aldervale", role="Provost"),
    "pr-adw": project("Assessment Design Workshop", ["the assessment workshop"],
                      phases=["planning", "logistics", "delivery"], status="active",
                      phase="delivery", target_date="2027-08-16", owner="p-bolat",
                      sponsor="p-anastasia", orgs=["o-aldervale"]),
    "pr-garnet": project("Garnet", ["the Garnet pilot"], phases=["build", "security review"],
                         status="active", phase="security review", owner="p-bolat"),
}

# Relationship questions (gen-s3-w1 cp1 q-009, gen-s5-small cp1 q-009, gen-s9-large cp1 q-016).
RELATIONS = {
    "p-alasdair": person("Alasdair Kaya", ["Alasdair"], org="o-ndo", role="Program Lead"),
    "o-ndo": org("Network Digital Office", ["NDO", "the NDO team"], domain="kirkmarsh.example"),
    "o-ketford": org("Ketford General Hospital", ["Ketford"], domain="ketford.example"),
    "o-falbury": org("Falbury Community Clinics", ["Falbury"], domain="falbury.example"),
    "p-eleni": person("Eleni Fontaine", ["Lena", "Eleni"], org="o-ketford",
                      role="Revenue Cycle Analyst", relationship="stakeholder"),
    "p-rodrigo": person("Rodrigo Okada", ["Rodrigo"], org="o-falbury",
                        role="Chief Medical Information Officer", relationship="executive"),
    "p-mathieu": person("Mathieu Wijaya", ["Mathieu", "the platform lead"], org="o-ndo",
                        role="Principal, Integration Platform", relationship="peer"),
    "p-yasmin": person("Yasmin Guo", ["Yasmin"], org="o-ndo", role="Data Engineer (contract)",
                       relationship="stakeholder"),
    "pr-kittiwake": project("Kittiwake", ["the platform", "Kittiwake platform"],
                            status="active", phase="steady state", owner="p-mathieu",
                            members=["p-alasdair", "p-mathieu"]),
}

# New privacy officers, whose role is also part of another person's alias
# (gen-s6-w1 cp2 q-022, gen-s9-large cp2 q-025).
PRIVACY = {
    "p-me": person("Despina Pereira", ["Despina"], org="o-oat", role="Program Lead"),
    "o-oat": org("Office of Academic Technology", ["OAT"], domain="lanhurst.example"),
    "o-dorcliff": org("Dorcliff State College", ["Dorcliff", "DSC"],
                      domain="dorcliff.lanhurst.example"),
    "o-redridge": org("Redridge Children's Hospital", ["Redridge", "RCH"],
                      domain="redridge.kirkmarsh.example"),
    "p-ebun": person("Ebun Petrovic", ["Ebun", "the new privacy officer"], org="o-dorcliff",
                     role="Privacy Officer", relationship="stakeholder"),
    "p-cass": person("Cassandra Pham", ["Cassandra", "Cass"], org="o-redridge",
                     role="Privacy Officer", relationship="stakeholder"),
    "p-old": person("Ruth Lindqvist", ["Ruth", "the privacy officer"], org="o-oat",
                    role="Records Manager", relationship="peer"),
}


# ---------------------------------------------------------------- issue #3: text with context
@pytest.mark.parametrize(
    "value, score",
    [
        ("Information Security Manager at the Systemwide Learning Innovation Office", 1.0),
        ("Information Security Manager, SLIO (Drayhurst University System)", 1.0),  # same domain
        ("Information Security Manager at Holfield State College", 0.0),  # another org
        ("Information Security Manager / Head of Learning Services", 0.0),  # Meera's role
        ("Information Security Manager or Head of Learning Services", 0.0),
        ("Not the Information Security Manager", 0.0),
    ],
)
def test_role_with_the_subjects_org(value, score):
    q = attr_question("p-nomvula", "role", "What is Nomvula Ndlovu's role?",
                      "Information Security Manager")
    assert base(q, value, context(SLIO, worker="p-me")) == score


@pytest.mark.parametrize(
    "who, value, score",
    [
        ("p-ebun", "Privacy Officer at Dorcliff State College", 1.0),
        ("p-cass", "Privacy Officer at Redridge Children's Hospital", 1.0),
        ("p-ebun", "Privacy Officer at Redridge Children's Hospital", 0.0),  # Cass's org
        ("p-cass", "Privacy Officer at the Office of Academic Technology", 0.0),  # the worker's
        ("p-ebun", "Privacy Officer, previously at Redridge", 1.0),  # another org as history
        ("p-ebun", "Not the privacy officer; a records manager", 0.0),
    ],
)
def test_role_that_is_also_part_of_an_alias(who, value, score):
    """"Privacy Officer" is inside "the privacy officer", another person's alias."""
    name = PRIVACY[who]["surface_forms"][0]
    q = attr_question(who, "role", f"What is {name}'s role?", "Privacy Officer")
    assert base(q, value, context(PRIVACY, worker="p-me")) == score


@pytest.mark.parametrize(
    "value, score",
    [
        ("Delivery (it moved into delivery on 2027-07-07; target date 16 August)", 1.0),
        ("Delivery (moved from logistics on 2027-07-07)", 1.0),
        ("Delivery, owned by Bolat Oyelami and sponsored by Anastasia Mizrahi", 1.0),
        ("Logistics, moving to delivery next week", 0.0),  # the earlier phase as current
        ("Delivery or logistics", 0.0),
        ("Delivery (now back in security review)", 0.0),  # Garnet's phase as current
        ("Not delivery", 0.0),
        ("Delivery: workshops are being run across campuses with external facilitators", 0.0),
    ],
)
def test_phase_with_its_own_dates_and_people(value, score):
    q = attr_question("pr-adw", "phase", "What phase is Assessment Design Workshop in?",
                      "delivery")
    assert base(q, value, context(WORKSHOP, worker="p-me")) == score


@pytest.mark.parametrize(
    "subject, question, value, score",
    [
        ("p-eleni", "What is my working relationship with Lena?",
         "Stakeholder. Lena is an alias of Eleni Fontaine, Revenue Cycle Analyst at Ketford "
         "General Hospital; her recorded relationship to me is 'stakeholder'.", 1.0),
        ("p-rodrigo", "What is my working relationship with Rodrigo Okada?",
         "Executive - Rodrigo Okada is the Chief Medical Information Officer at Falbury "
         "Community Clinics, and the store records my working relationship with him as "
         "'executive'.", 1.0),
        ("p-mathieu", "What is my working relationship with Mathieu Wijaya?",
         "Peer — Mathieu Wijaya is Principal, Integration Platform at Network Digital Office, "
         "the same organization as me", 1.0),
        # A different relationship, with or without the right one (gen-s8-w4 cp7 q-099).
        ("p-yasmin", "What is my working relationship with Yasmin?",
         "Peer — Yasmin Guo is a Data Engineer (contract) in the Network Digital Office", 0.0),
        ("p-yasmin", "What is my working relationship with Yasmin?",
         "Stakeholder, though she works with me as a peer", 0.0),
        ("p-eleni", "What is my working relationship with Lena?",
         "Stakeholder or peer", 0.0),
        ("p-eleni", "What is my working relationship with Lena?",
         "Stakeholder at Falbury Community Clinics", 0.0),  # not her org
    ],
)
def test_relationship_with_the_subjects_record(subject, question, value, score):
    q = attr_question(subject, "relationship", question,
                      RELATIONS[subject]["attrs"]["relationship"])
    assert base(q, value, context(RELATIONS, worker="p-alasdair")) == score


def test_unsupported_context_still_counts_as_extra():
    """Words that are not in the subject's record still have a budget (gen-s7-w2 cp2 q-021)."""
    entities = {
        "p-me": person("Mere Hidayat", ["Mere"], org="o-elmwick", role="Lead"),
        "o-elmwick": org("University of Elmwick", ["Elmwick"], domain="elmwick.example"),
        "pr-eaod": project("Elmwick Alumni Outreach Discovery", ["the alumni discovery"],
                           status="active", phase="site visit", owner="p-me",
                           orgs=["o-elmwick"],
                           blocker="unsigned data-sharing agreement with Elmwick"),
    }
    ctx = context(entities, worker="p-me")
    q = attr_question("pr-eaod", "blocker",
                      "What is currently blocking Elmwick Alumni Outreach Discovery?",
                      "unsigned data-sharing agreement with Elmwick")
    assert base(q, "The unsigned data-sharing agreement with Elmwick", ctx) == 1.0
    causal = (
        "Unsigned data-sharing agreement with Elmwick, which is what is holding up "
        "access to the baseline data"
    )
    assert base(q, causal, ctx) == 0.0


def test_a_different_value_first_with_the_gold_one_later_fails():
    """gen-s7-w2 cp6 q-088: a task-level blocker first, the project's blocker as an extra."""
    q = attr_question("pr-garnet", "blocker", "What is currently blocking Garnet?",
                      "real student data paused pending the security review")
    entities = {**WORKSHOP, "pr-garnet": {**WORKSHOP["pr-garnet"]}}
    entities["pr-garnet"]["attrs"] = {**entities["pr-garnet"]["attrs"],
                                      "blocker": q["gold"]["value"]}
    value = (
        "The Garnet rollout checklist — blocked, waiting on a vendor fix (Garnet review "
        "2027-07-14); additionally, real student data is paused pending the security review, "
        "with the Garnet timeout errors 'still not right' as of the 2027-07-13 security review."
    )
    assert base(q, value, context(entities, worker="p-me")) == 0.0


@pytest.mark.parametrize(
    "attribute, gold, value",
    [
        # gen-s8-w4 cp4 q-056: a different next step.
        ("next_step", "Decide whether tooling wear becomes its own effort",
         "Finish the safety reporting baseline analysis - Tane Haugen asked Amira to finish it "
         "(20 Sep); the project is 'now in analysis' (14 Sep)."),
        # gen-s8-w4 cp6 q-088: the merged status, not the phase.
        ("phase", "placeholder", "Merged — folded into the Iselmoor Responsible AI Use "
         "Framework on 24 Sep; its open items move across."),
    ],
)
def test_a_different_answer_fails(attribute, gold, value):
    text = {"next_step": "What is the next step on Assessment Design Workshop?",
            "phase": "What phase is Assessment Design Workshop in?"}[attribute]
    q = attr_question("pr-adw", attribute, text, gold)
    assert base(q, value, context(WORKSHOP, worker="p-me")) == 0.0


@pytest.mark.parametrize(
    "status, value, score",
    [
        ("done", "Complete", 1.0),
        ("done", "complete (since 3 September 2027)", 1.0),  # gen-s4-w2 cp6 q-088
        ("done", "Done", 1.0),
        ("done", "Delivery", 0.0),
        ("done", "Complete or still in delivery", 0.0),
        ("active", "Complete", 0.0),  # only a finished project's phase
    ],
)
def test_terminal_phase_accepts_done_synonyms(status, value, score):
    """gen-s1-w1 cp3 q-036: the sources say "complete"; the phase label is "closed"."""
    entities = {**WORKSHOP, "pr-adw": {**WORKSHOP["pr-adw"]}}
    entities["pr-adw"]["attrs"] = {**entities["pr-adw"]["attrs"], "status": status,
                                   "phase": "closed"}
    q = attr_question("pr-adw", "phase", "What phase is the workshop in?", "closed")
    assert base(q, value, context(entities, worker="p-me")) == score


def test_note_is_not_graded():
    q = attr_question("p-nomvula", "role", "What is Nomvula Ndlovu's role?",
                      "Information Security Manager")
    ctx = context(SLIO, worker="p-me")
    note = "Possibly Head of Learning Services, or maybe at Holfield State College."
    assert base(q, "Information Security Manager", ctx, note=note) == 1.0
    assert base(q, "Head of Learning Services", ctx, note="Information Security Manager") == 0.0


@pytest.mark.parametrize("vote", [False, True])
def test_relationship_description_uses_point_judge_with_enum_definitions(vote):
    from wcb.grade.answers import grade_point
    from wcb.world.check import RELATIONSHIPS

    class Judge:
        def point(self, question, gold, answer, facts):
            assert gold == "peer" and question == "How do we work together?"
            assert answer == "cross-portfolio colleague and collaborator"
            assert set(facts["relationship_definitions"]) == set(RELATIONSHIPS)
            return vote

    q = attr_question("p-mathieu", "relationship", "How do we work together?", "peer")
    answer = {"value": "cross-portfolio colleague and collaborator"}
    result, details = grade_point(q, answer, Judge(), context(RELATIONS, worker="p-alasdair"))
    assert details["judge"] is vote
    assert result == float(vote)


def test_support_comes_from_the_subjects_record():
    ctx = context(RELATIONS, worker="p-alasdair")
    q = attr_question("p-mathieu", "relationship", "What is my working relationship with "
                      "Mathieu Wijaya?", "peer")
    support = point_support(q, ctx)
    assert {"p-mathieu", "o-ndo", "p-alasdair", "pr-kittiwake"} <= support.ids
    assert {"principal", "integration", "platform", "he", "organization"} <= support.tokens
    assert support.org_bound
    assert "o-ketford" not in support.ids
    # Questions without a subject get no support; the old budget applies.
    loose = {**q, "template": "loop_owner", "params": {}}
    assert point_support(loose, ctx).ids == frozenset()
    assert not text_matches("Peer, same organization, close colleague", "peer", loose, ctx)


# ---------------------------------------------------------------- pilot
@pytest.fixture(scope="module")
def pilot():
    world = World.load(PILOT)
    specs = {s["id"]: s for s in load_specs(world)}
    dates = {cp["id"]: cp["date"] for cp in world.checkpoints()}

    def get(qid: str) -> tuple[dict, ScoreContext]:
        spec = specs[qid]
        state = state_at(world, dates[spec["checkpoint"]])
        return build_question(spec, world, state), ScoreContext.from_state(world, state)

    return get


@pytest.mark.parametrize(
    "qid, value, score",
    [
        ("q-012", "Privacy Officer at Tarrow University Kestrow (Office of Privacy and Records)",
         1.0),
        ("q-012", "Privacy Officer at TU Saltmarren", 0.0),
        ("q-012", "Privacy Officer at Tarrow University System Office", 0.0),
        ("q-012", "Privacy Officer or Registrar", 0.0),
        ("q-048", "Advising Operations Lead at Tarrow University Saltmarren; she leads "
         "Saltmarren's side of the advising scheduling project.", 1.0),
        ("q-048", "Advising Operations Lead at TU Kestrow", 0.0),
    ],
)
def test_pilot_roles(pilot, qid, value, score):
    q, ctx = pilot(qid)
    assert base(q, value, ctx) == score


@pytest.mark.parametrize(
    "qid, value, score",
    [
        ("q-027", "Tue 9 Mar 2027 — Delphine to get the countersigned DSA copy back by next "
         "Tuesday (9 Mar); it's with the VP's office as of 4 Mar.", 1.0),
        ("q-034", "2027-04-05 (Monday) - moved from 29 Mar at the 5 Mar standup; assumes "
         "context API 12 Mar and load test 9 Mar.", 1.0),
        ("q-034", "2027-03-29 (moved to 2027-04-05 at the 5 Mar standup)", 0.0),
        ("q-034", "2027-04-05 (now 2027-04-12)", 0.0),
        ("q-035", "2027-03-12 (Friday) - moved from 10 Mar at the 5 Mar standup; skeleton up "
         "in dummy-data mode as of 6 Mar.", 1.0),
    ],
)
def test_pilot_dates(pilot, qid, value, score):
    q, ctx = pilot(qid)
    assert base(q, value, ctx) == score


# ---------------------------------------------------------------- issue #4: dates
MARTEN = context({"p-me": person("Camila Abernathy", ["Camila"])}, worker="p-me",
                 date="2027-11-13")


@pytest.mark.parametrize(
    "gold, value, score",
    [
        # gen-s1-w1 cp3 q-040 and q-041, verbatim.
        ("2027-11-18", "2027-11-18 (Thu 18 Nov — the deadline Camila set when she picked the "
         "retention schedule up on 12 Nov; she sent it to Jalen on 12 Nov, ahead of that "
         "deadline).", 1.0),
        ("2027-12-31", "2027-12-31 (Fri 31 Dec; moved from 22 Dec on 9 Nov, which had "
         "replaced 15 Dec on 8 Nov).", 1.0),
        # Other leading forms (gen-s9-large cp3 q-047, gen-s5-small cp1 q-007).
        ("2027-11-09", "By Tue 9 November (2027-11-09) per Aroha's 5 Nov note; it was "
         "actually demoed 5 Nov.", 1.0),
        ("2027-11-18", "Thursday 18 November: set on 12 Nov", 1.0),
        ("2027-11-18", "Due 18 Nov - picked up 12 Nov", 1.0),
        # A wrong leading date, with the gold date only in the explanation.
        ("2027-11-18", "2027-11-12 (Camila picked it up then; the deadline is 2027-11-18)",
         0.0),
        ("2027-11-18", "12 Nov - moved to 18 Nov", 0.0),
        # Two competing current dates without a leading one.
        ("2027-11-18", "The deadline is 18 Nov; Jalen expects it 25 Nov", 0.0),
        ("2027-11-18", "Camila set 18 Nov, Jalen asked for 25 Nov", 0.0),
        # Negated gold date.
        ("2027-11-18", "Not 18 Nov; no deadline was set", 0.0),
        # Ambiguity: hedges and lists, even when they lead.
        ("2027-11-18", "2027-11-18 or 2027-11-25", 0.0),
        ("2027-11-18", "18 Nov (or maybe 25 Nov)", 0.0),
        ("2027-11-18", "2027-11-18, 2027-11-25", 0.0),
        ("2027-11-18", "18 Nov / 25 Nov", 0.0),
        # A leading date the rest replaces with "now": the rest decides.
        ("2027-11-18", "18 Nov (now 25 Nov)", 0.0),
        ("2027-11-25", "18 Nov (now 25 Nov)", 1.0),
        # Without a leading date, the old rules still apply.
        ("2027-11-18", "Camila moved it on 12 Nov to 18 Nov", 1.0),
        ("2027-11-18", "The deadline Camila set is 18 Nov", 1.0),
    ],
)
def test_dates_value_first(gold, value, score):
    q = date_question('When is "Send Jalen the Marten retention schedule" due?', gold)
    assert base(q, value, MARTEN) == score


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2027-02-05", "2027-02-05"),
        ("Fri 5 Feb", "2027-02-05"),
        ("Friday, 5 February 2027 (moved from 29 Jan)", "2027-02-05"),
        ("by Feb 5 — confirmed", "2027-02-05"),
        ("5 Feb; was 29 Jan", "2027-02-05"),
        ("Feb 5, not Jan 29", "2027-02-05"),
        ("Feb 5 2027.", "2027-02-05"),
        ("29 Jan -> 5 Feb", None),  # an arrow is not a separator
        ("Jan 29 → Feb 5", None),
        ("Moved on 1/11 to Feb 5", None),  # does not start with a date
        ("Feb 5 was the old date", None),  # not set off from the rest
        ("Feb 30 (as agreed)", None),  # impossible
        ("Jan 29, Feb 5", None),  # a list
        ("29 Jan (now 5 Feb)", None),
        ("5 Feb (5 Feb confirmed by Cora)", "2027-02-05"),
        ("", None),
        (None, None),
    ],
)
def test_leading_date(value, expected):
    assert leading_date(value, today="2027-01-12") == expected


def test_normalize_date_text_is_unchanged():
    """The store-reader baseline relies on the whole-text reading of `normalize_date_text`."""
    assert normalize_date_text("since Monday 1 March", default_year=2027) == "2027-03-01"
    assert normalize_date_text("2027-02-05 (assigned 2027-01-12)", today="2027-01-12") is None
    assert normalize_date_text("Feb 5 (moved from Jan 29)", today="2027-01-12") == "2027-02-05"
