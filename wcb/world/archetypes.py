"""Project archetypes: phase state machines with beats (docs/generator.md, "Archetypes").

An **archetype** is a small state machine over project **phases**. Each phase defines

- the probability per business day of moving to each next phase (`next`);
- **beats**: event templates fired on entry (`on_enter`) or at random while in the phase
  (`beats`). A beat creates a commitment, makes a decision or sets a project fact;
- the ad hoc meetings typical of the phase and its project status.

Beat text uses slot templates that the simulator fills from a context:

| Slot | Meaning |
|---|---|
| `{worker.first}`, `{cp.first}`, `{debtor.first}`, `{creditor.first}`, `{other.first}` | people |
| `{owner.first}`, `{sponsor.first}`, `{cand.first}` | the project's owner, sponsor, candidate |
| `{proj.short}`, `{proj.kw}`, `{hub.short}`, `{topic}` | project names and topic |
| `{unit.short}`, `{vendor.short}`, `{vendor2.short}` | organizations |
| `{v.sites}`, `{v.site}`, `{v.users}`, `{v.end_users}`, `{v.council}`, `{v.data}`, `{v.agreement}`, `{v.platform}` | setting vocabulary |
| `{noun}`, `{n}`, `{n2}`, `{ver}` | generic artifact noun, small numbers, a version label |
| `{n_plus}` | one more than `{n}` |
| `{hosting}`, `{bidders}`, `{approach}` | description slots of one archetype (`Archetype.slots`) |

**Description state.** An archetype's `desc` is the first sentence of a project's summary, and
the simulator rewrites the summary whenever the project changes. Every value in `desc` that a
decision can change is project state, not a constant: `{n}` (the scope count) and the
archetype's `slots`. A decision beat's `effect` says what its replacement (the `counter`
decision that a reversal makes) does to that state: `("n", "+1")` widens the scope by one,
`("hosting", template)` replaces a slot. The simulator applies the effect when the replacement
is made and rewrites the summary then (docs/generator.md, "Summaries track current state");
`check_library` verifies that every effect names `n` or a slot that `desc` uses.

Every keyword template of a loop or decision beat is a substring of its `what` template, so a
renderer that states the `what` always carries the keywords (`check_library` verifies this).

Roles for `debtor`, `creditor`, `others` and `by`: `worker`, `cp` (a project collaborator),
`owner`, `sponsor`, `lead` (the unit's lead), `unit` (someone at the unit), `ae` and `se`
(vendor account executive and solutions engineer), `eng`, `sec`, `privacy`, `legal`, `proc`,
`fin`, `hr`, `ea`, `collab` (the worker's main collaborator), `partner`, `cand`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ROLES = (
    "worker", "cp", "owner", "sponsor", "lead", "unit", "ae", "se", "eng", "sec", "privacy",
    "legal", "proc", "fin", "hr", "ea", "collab", "partner", "cand",
)


@dataclass(frozen=True)
class Beat:
    """An event template. `type` is `loop`, `decision` or `fact`."""

    key: str
    type: str
    what: str = ""
    summary: str = ""
    keywords: tuple[str, ...] = ()
    debtor: str = "worker"
    creditor: str = "cp"
    others: str | None = None
    kind: str = "task"  # task | ask
    status: str | None = None  # open | waiting | blocked; None: derived from the owner
    due: tuple[int, int] | None = None  # business days after creation
    channel: str | None = None  # preferred medium: email, chat, meeting, note, calendar
    weight: float = 1.0
    max_uses: int = 1  # per project, or per vendor when the text names a vendor
    attr: str | None = None  # fact beats
    value: str | None = None  # fact beats: text template, "+lo..hi" for a date slip, "" clears
    by: tuple[str, ...] = ("worker",)  # decision beats
    subject: str = ""  # email subject or meeting title hint
    # Decision beats: the decision that replaces this one if it is reversed (what, summary,
    # keywords) and the reasons that fit such a reversal.
    counter: tuple[str, str, tuple[str, ...]] | None = None
    reasons: tuple[str, ...] = ()
    # Decision beats: what the replacement (`counter`) decision does to the project's
    # description state, as (slot, value) pairs: ("n", "+k") or (slot name, template).
    effect: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Phase:
    name: str
    beats: tuple[Beat, ...] = ()
    on_enter: tuple[Beat, ...] = ()
    next: tuple[tuple[str, float], ...] = ()  # (phase, probability per business day)
    status: str = "active"
    activity: float = 1.0
    meetings: tuple[str, ...] = ()  # ad hoc meeting title templates


@dataclass(frozen=True)
class Archetype:
    name: str
    label: str
    desc: str  # template for the first sentence of the project summary
    phases: tuple[Phase, ...]
    start: tuple[str, ...]  # phases a project can start the seed in
    reversal_reasons: tuple[str, ...] = ()
    decisions: tuple[Beat, ...] = field(default=())  # archetype-wide decision beats
    # Description slots that a decision can change: (name, initial template). The template is
    # filled from the same context as `desc`; a decision's `effect` replaces it.
    slots: tuple[tuple[str, str], ...] = ()

    def phase(self, name: str) -> Phase:
        for p in self.phases:
            if p.name == name:
                return p
        raise KeyError(f"{self.name} has no phase {name!r}")

    def beats(self) -> list[Beat]:
        out = list(self.decisions)
        for p in self.phases:
            out += list(p.on_enter) + list(p.beats)
        return out


# ---------------------------------------------------------------- beat constructors
def L(key, what, summary, kw, *, debtor="worker", creditor="cp", others=None, kind=None,
      status=None, due=None, ch=None, w=1.0, n=1, subject=""):  # noqa: E741 - short DSL name
    """A loop beat. `kind` defaults to `ask` when the creditor asked, i.e. the debtor is not
    the one offering (heuristic: worker-to-other requests and other-to-worker requests)."""
    if kind is None:
        kind = "task" if debtor in ("worker",) and creditor in ("cp", "owner", "sponsor", "collab") else "ask"
    return Beat(key, "loop", what, summary, tuple(kw), debtor, creditor, others, kind, status,
                due, ch, w, n, subject=subject)


def D(key, what, summary, kw, *, by=("worker", "sponsor"), w=1.0, counter=None, reasons=(), effect=None):
    """A decision beat. `counter` is (what, summary, keywords) of the decision that replaces it
    when it is reversed; `reasons` are reversal reasons that fit it; `effect` (slot -> value) is
    what that replacement does to the project's description state (see the module docstring)."""
    c = (counter[0], counter[1], tuple(counter[2])) if counter else None
    return Beat(key, "decision", what, summary, tuple(kw), weight=w, by=tuple(by), counter=c, reasons=tuple(reasons),
                effect=tuple((effect or {}).items()))


def F(key, attr, value, summary, *, w=1.0):
    return Beat(key, "fact", summary=summary, attr=attr, value=value, weight=w)


def P(name, beats=(), *, enter=(), nxt=(), status="active", activity=1.0, meetings=()):
    return Phase(name, tuple(beats), tuple(enter), tuple(nxt), status, activity, tuple(meetings))


SLIP = F("slip", "target_date", "+5..15", "{proj.short} target date moved to {date}", w=0.4)


# ---------------------------------------------------------------- generic beats
# Used for any project once its phase beats are spent. `{noun}` is drawn from the setting's
# artifact nouns, unused on the project so far.
GENERIC: tuple[Beat, ...] = (
    L("g_send", "Send {cp.first} the {proj.short} {noun}", "I promised {cp.first} the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], w=3.0, n=99),
    L("g_review", "Review {cp.first}'s {proj.short} {noun}", "{cp.first} asked me to review the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], kind="ask", w=2.0, n=99),
    L("g_askfor", "Send {creditor.first} the {proj.short} {noun}", "I asked {debtor.first} for the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], debtor="cp", creditor="worker", kind="ask", w=3.0, n=99),
    L("g_offer", "Share the {proj.short} {noun} with {creditor.first}", "{debtor.first} offered to share the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], debtor="cp", creditor="worker", kind="task", w=2.0, n=99),
    L("g_joint", "Pull together the {proj.short} {noun} with {other.first}",
      "{other.first} and I will pull together the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], others="cp", w=0.8, n=99),
    L("g_relay", "Send {creditor.first} the {proj.short} {noun}", "{debtor.first} owes {creditor.first} the {proj.short} {noun}",
      ["{noun}", "{proj.kw}"], debtor="cp", creditor="unit", kind="ask", w=0.6, n=99),
    L("g_confirm", "Confirm the {proj.short} {noun} with {cp.first}", "I said I'd confirm the {proj.short} {noun} with {cp.first}",
      ["{noun}", "{proj.kw}"], w=1.2, n=99),
    L("g_update", "Update the {proj.short} {noun} after {cp.first}'s comments",
      "I'll update the {proj.short} {noun} after {cp.first}'s comments", ["{noun}", "{proj.kw}"], w=1.0, n=99),
)

# Loops that belong to no project: relationships, admin and favours.
UNATTACHED: tuple[Beat, ...] = (
    L("u_intro", "Introduce {cp.first} to {other.first} for the {topic} work", "I offered to introduce {cp.first} to {other.first}",
      ["introduce", "{topic} work"], others=None, w=1.0, n=99),
    L("u_coffee", "Set up a coffee with {cp.first} about {topic}", "I said I'd set up a coffee with {cp.first} about {topic}",
      ["coffee", "{topic}"], w=1.0, n=99),
    L("u_reading", "Send {cp.first} the reading list on {topic}", "I promised {cp.first} my reading list on {topic}",
      ["reading list", "{topic}"], w=1.0, n=99),
    L("u_ask_notes", "Send {creditor.first} the notes from the {topic} session", "I asked {debtor.first} for the notes from the {topic} session",
      ["notes from the {topic} session", "{topic}"], debtor="cp", creditor="worker", w=1.0, n=99),
    L("u_reference", "Write a reference note for {cp.first}'s {topic} fellowship application",
      "{cp.first} asked me for a reference note", ["reference note", "{topic} fellowship"], kind="ask", w=0.5, n=99),
    L("u_panel", "Join {cp.first}'s panel on {topic}", "{cp.first} asked me to join a panel on {topic}",
      ["panel on {topic}", "{topic}"], kind="ask", w=0.6, n=99),
)


# ---------------------------------------------------------------- the library
FLAGSHIP = Archetype(
    "flagship_pilot", "flagship pilot build with gates",
    "Pilot of {topic_a} for {n} {v.sites} at {unit.short}, {hosting}.",
    phases=(
        P("scoping", [
            L("brief", "Send {cp.first} the {proj.short} solution brief", "I promised {cp.first} the {proj.short} solution brief",
              ["solution brief", "{proj.kw}"], w=2),
            L("pilot_list", "Send {creditor.first} the list of pilot {v.sites} for {proj.short}", "I asked {debtor.first} for the list of pilot {v.sites}",
              ["pilot {v.sites}", "{proj.kw}"], debtor="lead", creditor="worker"),
            L("contract1", "Write the {proj.short} API contract v1", "I took on the {proj.short} API contract v1",
              ["api contract", "{proj.kw}"], creditor="lead", kind="task", w=1.5),
            L("tenant", "Provision the {proj.short} tenant on {hub.short}", "I asked {debtor.first} to provision the {proj.short} tenant on {hub.short}",
              ["tenant on {hub.short}", "{proj.kw}"], debtor="eng", creditor="worker", ch="chat"),
            SLIP,
        ], enter=[F("ns_scope", "next_step", "Agree the pilot {v.sites} with {unit.short}", "Next step on {proj.short}: agree the pilot {v.sites}")],
           nxt=[("build", 0.10)], meetings=["{proj.short} scoping call"]),
        P("build", [
            L("rolemap", "Set up the {proj.short} single sign-on role mapping", "{debtor.first} will set up the {proj.short} single sign-on role mapping",
              ["role mapping", "{proj.kw}"], debtor="unit", creditor="worker", kind="task", ch="chat"),
            L("endpoint", "Deliver the {proj.short} integration endpoint", "{debtor.first} committed to the {proj.short} integration endpoint",
              ["integration endpoint", "{proj.kw}"], debtor="unit", creditor="worker", kind="task", due=(5, 10)),
            L("loadplan", "Draft the {proj.short} load test plan", "{debtor.first} will draft the {proj.short} load test plan",
              ["load test plan", "{proj.kw}"], debtor="unit", creditor="worker", kind="task"),
            L("playbook", "Write the {proj.short} support playbook", "{debtor.first} is writing the {proj.short} support playbook",
              ["support playbook", "{proj.kw}"], debtor="unit", creditor="worker", kind="task"),
            L("contract2", "Turn around the {proj.short} API contract v2", "I owe {cp.first} the {proj.short} API contract v2",
              ["api contract v2", "{proj.kw}"], kind="task", w=1.2),
            L("onboard", "Book {v.users} onboarding sessions for {proj.short}", "{debtor.first} is booking {v.users} onboarding sessions",
              ["onboarding sessions", "{proj.kw}"], debtor="unit", creditor="worker", kind="task"),
            F("block_roles", "blocker", "single sign-on role mapping still pending for {proj.short}", "{proj.short} blocked: single sign-on role mapping still pending", w=0.6),
            SLIP,
        ], nxt=[("security review", 0.09)], meetings=["{proj.short} build sync"]),
        P("security review", [
            L("secpkg", "Assemble the {proj.short} security review package", "I took on the {proj.short} security review package",
              ["security review package", "{proj.kw}"], creditor="sec", kind="task", due=(3, 6), w=2),
            L("pia", "Complete the {proj.short} privacy impact assessment", "{creditor.first} asked me for the {proj.short} privacy impact assessment",
              ["privacy impact assessment", "{proj.kw}"], creditor="privacy", kind="ask", due=(5, 10)),
            L("dataflow", "Send {creditor.first} the {proj.short} data-flow diagram", "{creditor.first} asked for the {proj.short} data-flow diagram",
              ["data-flow diagram", "{proj.kw}"], creditor="sec", kind="ask"),
            L("synth", "Generate a synthetic {v.data} set for {proj.short}", "{debtor.first} will generate a synthetic {v.data} set for {proj.short}",
              ["synthetic {v.data}", "{proj.kw}"], debtor="eng", creditor="worker", kind="task"),
            F("unblock", "blocker", "", "{proj.short} blocker cleared", w=0.5),
            SLIP,
        ], enter=[F("block_data", "blocker", "real {v.data} paused pending the security review", "{proj.short} paused real {v.data} pending the security review")],
           nxt=[("readiness", 0.08)], meetings=["{proj.short} security review"]),
        P("readiness", [
            L("evalplan", "Revise the {proj.short} evaluation plan", "I agreed to revise the {proj.short} evaluation plan",
              ["evaluation plan", "{proj.kw}"], creditor="unit", kind="task", w=1.5),
            L("faq", "Draft the {v.users} FAQ for {proj.short}", "I said I'd draft the {v.users} FAQ for {proj.short}",
              ["{v.users} faq", "{proj.kw}"]),
            L("golive", "Run the {proj.short} go-live checklist with {cp.first}", "I'll run the {proj.short} go-live checklist with {cp.first}",
              ["go-live checklist", "{proj.kw}"]),
            L("costest", "Send {creditor.first} the {proj.short} run-cost estimate", "{creditor.first} asked for a {proj.short} run-cost estimate",
              ["run-cost estimate", "{proj.kw}"], creditor="fin", kind="ask"),
            F("unblock2", "blocker", "", "{proj.short} blocker cleared", w=0.6),
            SLIP,
        ], enter=[F("ns_ready", "next_step", "Run the go-live checklist with {unit.short}", "Next step on {proj.short}: go-live checklist")],
           nxt=[("pilot live", 0.06)], meetings=["{proj.short} readiness review"]),
        P("pilot live", [
            L("usage", "Send {creditor.first} the first {proj.short} usage report", "{debtor.first} will send the first {proj.short} usage report",
              ["usage report", "{proj.kw}"], debtor="eng", creditor="worker", kind="task"),
            L("survey", "Send the {proj.short} {v.users} feedback survey", "I'll send the {proj.short} {v.users} feedback survey",
              ["feedback survey", "{proj.kw}"]),
            L("expand_ask", "Scope adding {n2} more {v.sites} to {proj.short}", "{creditor.first} asked me to scope {n2} more {v.sites} for {proj.short}",
              ["more {v.sites}", "{proj.kw}"], creditor="sponsor", kind="ask"),
        ], meetings=["{proj.short} pilot check-in"]),
    ),
    start=("scoping", "build", "build"),
    reversal_reasons=("{sponsor.first} wants a wider trial", "{unit.short} asked for another {v.site}", "the security review requires it"),
    decisions=(
        D("d_scope", "Limit the {proj.short} pilot to {n} {v.sites}", "Decided to limit the {proj.short} pilot to {n} {v.sites}",
          ["{n} {v.sites}", "{proj.kw}"],
          counter=("Widen the {proj.short} pilot to {n_plus} {v.sites}", "Decided to widen the {proj.short} pilot to {n_plus} {v.sites}",
                   ["{n_plus} {v.sites}", "{proj.kw}"]),
          reasons=("{sponsor.first} wants a wider trial", "{unit.short} asked for another {v.site}"),
          effect={"n": "+1"}),
        D("d_host", "Host {proj.short} on the shared {hub.short} tenant", "Decided to host {proj.short} on the shared {hub.short} tenant",
          ["shared {hub.short} tenant", "{proj.kw}"], by=("worker",),
          counter=("Give {proj.short} a dedicated tenant outside {hub.short}", "Decided to give {proj.short} a dedicated tenant outside {hub.short}",
                   ["dedicated tenant", "{proj.kw}"]),
          reasons=("the security review requires a separate tenant", "{unit.short} wants its {v.data} kept apart"),
          effect={"hosting": "hosted on a dedicated tenant outside {hub.short}"}),
        D("d_synth", "Use synthetic {v.data} in {proj.short} until the security review closes",
          "Decided to use synthetic {v.data} in {proj.short} until the security review closes",
          ["synthetic {v.data}", "security review"], by=("sec", "worker"),
          counter=("Test {proj.short} with de-identified {v.data} from the next test cycle",
                   "Decided to test {proj.short} with de-identified {v.data} from the next test cycle",
                   ["de-identified {v.data}", "{proj.kw}"]),
          reasons=("synthetic records were not realistic enough to test with", "the security review signed off on de-identified extracts")),
    ),
    slots=(("hosting", "hosted on {hub.short}"),),
)

HUB = Archetype(
    "platform_hub", "shared-platform blocker hub",
    "{owner.first}'s team runs {hub.short}, the {v.platform} that {v.unit_word} projects build on.",
    phases=(
        P("onboarding tenants", [
            L("tenant_guide", "Publish the {proj.short} tenant onboarding guide", "{debtor.first} will publish the {proj.short} tenant onboarding guide",
              ["tenant onboarding guide", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
            L("ratelimits", "Set gateway rate limits for {proj.short} tenants", "{debtor.first} is setting {proj.short} gateway rate limits",
              ["gateway rate limits", "{proj.kw}"], debtor="eng", creditor="worker", kind="task", ch="chat"),
            L("allowlist", "Review the {proj.short} model allow-list", "{creditor.first} asked me to review the {proj.short} model allow-list",
              ["model allow-list", "{proj.kw}"], creditor="owner", kind="ask"),
            L("broker", "Configure the {proj.short} SSO broker for {unit.short}", "{debtor.first} will configure the {proj.short} SSO broker for {unit.short}",
              ["sso broker", "{proj.kw}"], debtor="eng", creditor="worker", kind="task"),
            F("block_cap", "blocker", "gateway capacity limits on {proj.short}", "{proj.short} blocked on gateway capacity", w=0.4),
        ], nxt=[("hardening", 0.06)], meetings=["{proj.short} platform sync"]),
        P("hardening", [
            L("rotation", "Rotate the {proj.short} vault secrets", "{debtor.first} will rotate the {proj.short} vault secrets",
              ["vault secrets", "{proj.kw}"], debtor="eng", creditor="sec", kind="task"),
            L("oncall", "Draft the {proj.short} on-call rota", "{debtor.first} is drafting the {proj.short} on-call rota",
              ["on-call rota", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
            L("capplan", "Send {creditor.first} the {proj.short} capacity plan", "I asked {debtor.first} for the {proj.short} capacity plan",
              ["capacity plan", "{proj.kw}"], debtor="owner", creditor="worker"),
            F("unblock_cap", "blocker", "", "{proj.short} capacity blocker cleared", w=0.5),
        ], nxt=[("steady state", 0.04)], meetings=["{proj.short} hardening review"]),
        P("steady state", [
            L("costs", "Send {creditor.first} the monthly {proj.short} cost report", "{debtor.first} will send the monthly {proj.short} cost report",
              ["monthly {proj.short} cost report", "cost report"], debtor="eng", creditor="worker", kind="task"),
        ], activity=0.6),
    ),
    start=("onboarding tenants",),
    decisions=(D("d_gw", "Route all {proj.short} tenants through one model gateway", "Decided to route all {proj.short} tenants through one model gateway",
                 ["one model gateway", "{proj.kw}"], by=("owner", "worker"),
                 counter=("Let {proj.short} tenants keep their own model gateways", "Decided to let {proj.short} tenants keep their own model gateways",
                          ["own model gateways", "{proj.kw}"]),
                 reasons=("one gateway cannot carry every tenant's load yet", "two tenants have contractual reasons to stay separate")),),
)

VENDOR_PAIR = Archetype(
    "vendor_pair_evaluation", "vendor-pair evaluation",
    "Selecting a tool for {topic} at {unit.short}; {bidders}.",
    phases=(
        P("intake", [
            L("reqs", "Send {cp.first} the {proj.short} requirements list", "I promised {cp.first} the {proj.short} requirements list",
              ["requirements list", "{proj.kw}"], w=1.5),
            L("usecases", "Send {creditor.first} the {unit.short} use-case list", "I asked {debtor.first} for the {unit.short} use-case list",
              ["use-case list", "{unit.short}"], debtor="lead", creditor="worker"),
        ], nxt=[("questionnaires", 0.15)]),
        P("questionnaires", [
            L("vsq", "Return the {vendor.short} security questionnaire", "I asked {debtor.first} to return the {vendor.short} security questionnaire",
              ["security questionnaire", "{vendor.short}"], debtor="ae", creditor="worker", status="waiting", due=(5, 10), ch="email", w=3, n=2),
            L("acr", "Send the {vendor.short} accessibility conformance report", "I asked {debtor.first} for the {vendor.short} accessibility conformance report",
              ["accessibility conformance report", "{vendor.short}"], debtor="ae", creditor="worker", ch="email", n=2),
        ], nxt=[("demos", 0.12)], meetings=["{vendor.short} intro call"]),
        P("demos", [
            L("demo", "Book the {vendor.short} demo for {unit.short}", "I said I'd book the {vendor.short} demo for {unit.short}",
              ["{vendor.short} demo", "{unit.short}"], creditor="lead", kind="task", n=2, w=2),
            L("pricing", "Send {creditor.first} {vendor.short} volume pricing", "{debtor.first} will send {vendor.short} volume pricing",
              ["volume pricing", "{vendor.short}"], debtor="ae", creditor="worker", kind="task", n=2, w=2),
            L("sandbox", "Set up {vendor.short} sandbox access for {creditor.first}", "{debtor.first} is setting up {vendor.short} sandbox access",
              ["sandbox access", "{vendor.short}"], debtor="se", creditor="worker", kind="task", n=2),
            L("demonotes", "Write up the {vendor.short} demo notes", "I'll write up the {vendor.short} demo notes",
              ["{vendor.short} demo notes", "demo notes"], creditor="lead", kind="task", n=2),
        ], nxt=[("scoring", 0.10)], meetings=["{vendor.short} demo", "{vendor2.short} demo"]),
        P("scoring", [
            L("scorecard", "Circulate the {proj.short} scorecard", "I promised to circulate the {proj.short} scorecard",
              ["scorecard", "{proj.kw}"], creditor="lead", kind="task", w=2),
            L("afterhours", "Answer {creditor.first}'s after-hours support question on {proj.short}", "{creditor.first} asked who covers {proj.short} support after hours",
              ["after-hours support", "{proj.kw}"], creditor="cp", kind="ask"),
            L("inhouse", "Add a build-in-house option to the {proj.short} comparison", "{creditor.first} asked for a build-in-house option in the {proj.short} comparison",
              ["build-in-house option", "{proj.kw}"], creditor="unit", kind="ask"),
            L("refs", "Collect two customer references from {vendor.short}", "I asked {debtor.first} for two {vendor.short} customer references",
              ["customer references", "{vendor.short}"], debtor="ae", creditor="worker", n=2),
        ], nxt=[("procurement", 0.08)], meetings=["{proj.short} scoring session"]),
        P("procurement", [
            L("sourcing", "Send {creditor.first} the {proj.short} sourcing requirements", "{creditor.first} needs the {proj.short} sourcing requirements",
              ["sourcing requirements", "{proj.kw}"], creditor="proc", kind="ask", due=(4, 8), w=2),
            L("dpa", "Review the {vendor.short} data processing agreement", "{debtor.first} is reviewing the {vendor.short} data processing agreement",
              ["data processing agreement", "{vendor.short}"], debtor="legal", creditor="worker", kind="task", n=2),
        ], nxt=[("contracting", 0.05)], meetings=["{proj.short} procurement check-in"]),
        P("contracting", [
            L("orderform", "Countersign the {vendor.short} order form", "{debtor.first} will countersign the {vendor.short} order form",
              ["order form", "{vendor.short}"], debtor="sponsor", creditor="worker", kind="task"),
        ], activity=0.6),
    ),
    start=("intake", "questionnaires", "demos"),
    reversal_reasons=("{vendor.short} could not meet the data terms", "procurement requires a third bidder"),
    decisions=(
        D("d_short", "Shortlist {vendor.short} and {vendor2.short} for {proj.short}", "Decided to shortlist {vendor.short} and {vendor2.short}",
          ["shortlist", "{vendor2.short}"], by=("worker", "lead"),
          counter=("Add a third bidder to the {proj.short} shortlist", "Decided to add a third bidder to the {proj.short} shortlist",
                   ["third bidder", "{proj.kw}"]),
          reasons=("procurement requires a third bidder", "{vendor.short} could not meet the data terms"),
          effect={"bidders": "{vendor.short} and {vendor2.short} are shortlisted and a third bidder is being added"}),
        D("d_weight", "Weight integration effort at 25% in the {proj.short} scoring", "Decided to weight integration effort at 25% in the {proj.short} scoring",
          ["integration effort", "25%"], by=("lead", "worker"),
          counter=("Weight integration effort at 15% in the {proj.short} scoring", "Decided to weight integration effort at 15% in the {proj.short} scoring",
                   ["integration effort", "15%"]),
          reasons=("{unit.short} thinks integration effort is over-weighted", "the scoring should favour usability")),
    ),
    slots=(("bidders", "{vendor.short} and {vendor2.short} are in the running"),),
)

UNIT_DISCOVERY = Archetype(
    "unit_discovery", "unit discovery",
    "Discovery with {unit.short} on {topic}; looking for where AI could help before anything is built.",
    phases=(
        P("planning", [
            L("procmap", "Send {creditor.first} the current {topic} process map", "I asked {debtor.first} for the current {topic} process map",
              ["process map", "{topic}"], debtor="unit", creditor="worker", w=1.5),
            L("agenda", "Send {cp.first} the {proj.short} site visit agenda", "I promised {cp.first} the {proj.short} site visit agenda",
              ["site visit agenda", "{proj.kw}"]),
            L("interviews", "Line up {v.users} interviews for {proj.short}", "{debtor.first} will line up {v.users} interviews for {proj.short}",
              ["{v.users} interviews", "{proj.kw}"], debtor="lead", creditor="worker", kind="task"),
        ], nxt=[("site visit", 0.12)]),
        P("site visit", [
            L("baseline", "Pull the {topic} baseline data from {unit.short}", "I asked {debtor.first} to pull the {topic} baseline data",
              ["baseline data", "{topic}"], debtor="unit", creditor="worker"),
            L("dsa", "Countersign the {unit.short} {v.agreement}", "{debtor.first} will countersign the {unit.short} {v.agreement}",
              ["{v.agreement}", "{unit.short}"], debtor="lead", creditor="worker", kind="task", due=(3, 8)),
            F("block_dsa", "blocker", "unsigned {v.agreement} with {unit.short}", "{proj.short} baseline data blocked by the unsigned {v.agreement}", w=0.8),
        ], nxt=[("analysis", 0.10)], meetings=["{unit.short} site visit"]),
        P("analysis", [
            L("analysis", "Finish the {topic} baseline analysis", "I'll finish the {topic} baseline analysis",
              ["baseline analysis", "{topic}"], creditor="lead", kind="task"),
            L("ucl", "Send {cp.first} the ranked {proj.short} use cases", "I promised {cp.first} the ranked {proj.short} use cases",
              ["ranked {proj.short} use cases", "use cases"]),
            F("unblock_dsa", "blocker", "", "{proj.short} blocker cleared", w=0.6),
        ], nxt=[("readout", 0.08)], meetings=["{proj.short} working session"]),
        P("readout", [
            L("readout", "Present the {proj.short} readout to {unit.short}", "I'll present the {proj.short} readout to {unit.short}",
              ["{proj.short} readout", "{unit.short}"], creditor="lead", kind="task", due=(3, 7)),
        ], nxt=[("closed", 0.06)]),
        P("closed", status="done", activity=0.0),
    ),
    start=("planning", "site visit"),
)

PIVOTING = Archetype(
    "pivoting_discovery", "pivoting discovery that splits",
    "Discovery with {unit.short} on {topic}; the problem framing is still moving.",
    phases=(
        P("planning", UNIT_DISCOVERY.phase("planning").beats, nxt=(("site visit", 0.12),)),
        P("site visit", UNIT_DISCOVERY.phase("site visit").beats, nxt=(("pivot", 0.10),), meetings=("{unit.short} site visit",)),
        P("pivot", [
            L("sprint", "Scope a two-week sprint on {pivot}", "I offered to scope a two-week sprint on {pivot}",
              ["two-week sprint", "{pivot}"], creditor="lead", kind="task"),
            L("waitdata", "Send {creditor.first} the {pivot} wait-time export", "I asked {debtor.first} for the {pivot} wait-time export",
              ["wait-time export", "{pivot}"], debtor="unit", creditor="worker"),
        ], enter=[F("ns_pivot", "next_step", "Decide whether {pivot} becomes its own effort", "Next step on {proj.short}: decide on {pivot}")],
           nxt=[("analysis", 0.06)], meetings=["{proj.short} reframing session"]),
        P("analysis", UNIT_DISCOVERY.phase("analysis").beats, nxt=(("readout", 0.08),)),
        P("readout", UNIT_DISCOVERY.phase("readout").beats),
    ),
    start=("planning", "site visit"),
)

ADVISORY = Archetype(
    "background_advisory", "background advisory that fades",
    "Light-touch advice to {unit.short} on {topic}; no deliverables of our own.",
    phases=(
        P("advising", [
            L("comment", "Comment on {creditor.first}'s {topic} guidance draft", "{creditor.first} asked me to comment on the {topic} guidance draft",
              ["{topic} guidance draft", "guidance draft"], creditor="unit", kind="ask"),
            L("hours", "Hold {topic} office hours for {unit.short}", "I offered {topic} office hours for {unit.short}",
              ["office hours", "{topic}"], creditor="lead", kind="task"),
        ], nxt=[("fading", 0.05)], activity=0.5),
        P("fading", status="dormant", activity=0.1),
    ),
    start=("advising",),
)

SUPPLIER = Archetype(
    "supplier_negotiation", "portfolio-wide supplier negotiation",
    "Negotiating one {vendor.short} agreement that covers every {v.unit_word} instead of separate deals.",
    phases=(
        P("needs gathering", [
            L("seats", "Confirm {unit.short} seat counts for the {vendor.short} agreement", "I asked {debtor.first} to confirm {unit.short} seat counts",
              ["seat counts", "{vendor.short} agreement"], debtor="lead", creditor="worker", w=2),
            L("usage", "Send {creditor.first} last year's {vendor.short} usage by {v.unit_word}", "I asked {debtor.first} for {vendor.short} usage by {v.unit_word}",
              ["{vendor.short} usage", "{v.unit_word}"], debtor="ae", creditor="worker"),
        ], nxt=[("negotiation", 0.10)]),
        P("negotiation", [
            L("tiers", "Send {creditor.first} the {vendor.short} volume tiers", "{debtor.first} will send the {vendor.short} volume tiers",
              ["volume tiers", "{vendor.short}"], debtor="ae", creditor="worker", kind="task"),
            L("counter", "Draft our counter-proposal to {vendor.short}", "I'll draft our counter-proposal to {vendor.short}",
              ["counter-proposal", "{vendor.short}"], creditor="proc", kind="task"),
        ], nxt=[("contract review", 0.08)], meetings=["{vendor.short} commercial call"]),
        P("contract review", [
            L("redlines", "Return redlines on the {vendor.short} master agreement", "{debtor.first} will return redlines on the {vendor.short} master agreement",
              ["redlines", "{vendor.short} master agreement"], debtor="legal", creditor="worker", kind="task"),
        ], nxt=[("signed", 0.05)]),
        P("signed", status="done", activity=0.0),
    ),
    start=("needs gathering", "negotiation"),
    decisions=(D("d_term", "Sign a three-year {vendor.short} agreement", "Decided to go for a three-year {vendor.short} agreement",
                 ["three-year", "{vendor.short} agreement"], by=("sponsor", "worker"),
                 counter=("Sign a one-year {vendor.short} agreement with a renewal option",
                          "Decided to go for a one-year {vendor.short} agreement with a renewal option",
                          ["one-year", "{vendor.short} agreement"]),
                 reasons=("finance will not commit beyond one year", "{vendor.short} would not cap price rises")),),
)

EVENT = Archetype(
    "event_preparation", "event preparation that spawns a successor",
    "{owner.first} is organizing the {proj.short} for {v.users} at {unit.short}; I own the slides.",
    phases=(
        P("planning", [
            L("slides1", "Send {cp.first} the {proj.short} slides v1", "I promised {cp.first} the {proj.short} slides v1",
              ["slides v1", "{proj.kw}"], creditor="owner", kind="task", w=2),
            L("speakers", "Confirm two {v.users} speakers for the {proj.short}", "{debtor.first} is lining up two {v.users} speakers",
              ["speakers", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
            L("venue", "Book the venue for the {proj.short}", "{debtor.first} will book the venue for the {proj.short}",
              ["venue", "{proj.kw}"], debtor="collab", creditor="worker", kind="task"),
        ], nxt=[("logistics", 0.12)]),
        P("logistics", [
            L("slides2", "Send {cp.first} the {proj.short} slides v2", "I owe {cp.first} the {proj.short} slides v2",
              ["slides v2", "{proj.kw}"], creditor="owner", kind="task", due=(2, 5), w=2),
            L("refresh", "Arrange refreshments for the {proj.short}", "{debtor.first} is arranging refreshments for the {proj.short}",
              ["refreshments", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
            L("attendees", "Send {creditor.first} the {proj.short} attendee list", "{creditor.first} asked me for the {proj.short} attendee list",
              ["attendee list", "{proj.kw}"], creditor="owner", kind="ask"),
            L("reminder", "Send the {proj.short} registration reminder", "{debtor.first} will send the {proj.short} registration reminder",
              ["registration reminder", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
        ], nxt=[("delivery", 0.12)], meetings=["{proj.short} run-through"]),
        P("delivery", [
            L("survey", "Send the {proj.short} post-event survey", "{debtor.first} will send the {proj.short} post-event survey",
              ["post-event survey", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
            L("faq", "Turn the {proj.short} questions into an FAQ", "I agreed to turn the {proj.short} questions into an FAQ",
              ["faq", "{proj.kw}"], creditor="owner", kind="task"),
        ], nxt=[("closed", 0.15)]),
        P("closed", status="done", activity=0.0),
    ),
    start=("planning", "logistics"),
)

INCUBATION = Archetype(
    "internal_incubation", "internal product incubation",
    "{approach} before any {v.unit_word} adopts it.",
    phases=(
        P("concept", [
            L("brief", "Write the {proj.short} product brief", "I'm writing the {proj.short} product brief",
              ["product brief", "{proj.kw}"], creditor="sponsor", kind="task"),
            L("naming", "Propose a final name for {proj.short}", "{creditor.first} asked me to propose a final name for {proj.short}",
              ["final name", "{proj.kw}"], creditor="sponsor", kind="ask"),
        ], nxt=[("prototype", 0.10)]),
        P("prototype", [
            L("demo", "Demo the {proj.short} prototype to {cp.first}", "I said I'd demo the {proj.short} prototype to {cp.first}",
              ["prototype", "{proj.kw}"], w=1.5),
            L("backlog", "Groom the {proj.short} backlog with {cp.first}", "I'll groom the {proj.short} backlog with {cp.first}",
              ["backlog", "{proj.kw}"]),
        ], nxt=[("user testing", 0.08)], meetings=["{proj.short} prototype demo"]),
        P("user testing", [
            L("recruit", "Recruit five {v.users} for {proj.short} usability tests", "{debtor.first} will recruit five {v.users} for {proj.short} usability tests",
              ["usability tests", "{proj.kw}"], debtor="unit", creditor="worker", kind="task"),
            L("findings", "Write up the {proj.short} usability findings", "I'll write up the {proj.short} usability findings",
              ["usability findings", "{proj.kw}"], creditor="sponsor", kind="task"),
        ], nxt=[("handover", 0.05)]),
        P("handover", [
            L("handover", "Hand {proj.short} over to {unit.short}", "I'm handing {proj.short} over to {unit.short}",
              ["hand {proj.short} over", "{unit.short}"], creditor="lead", kind="task"),
        ], activity=0.5),
    ),
    start=("concept", "prototype"),
    decisions=(D("d_inhouse", "Build {proj.short} in-house rather than buy", "Decided to build {proj.short} in-house rather than buy",
                 ["in-house", "{proj.kw}"], by=("sponsor", "worker"),
                 counter=("Buy an off-the-shelf tool instead of building {proj.short}",
                          "Decided to buy an off-the-shelf tool instead of building {proj.short}",
                          ["off-the-shelf tool", "{proj.kw}"]),
                 reasons=("{sponsor.first} does not want to staff a build", "the team has no capacity for a build this year"),
                 effect={"approach": "An off-the-shelf tool for {topic}, to be bought by the central team rather than built in-house,"}),),
    slots=(("approach", "An in-house prototype for {topic}, incubated by the central team"),),
)

ECONOMICS = Archetype(
    "economics_model", "economics model",
    "Funding options for {hub.short} across {v.unit_word}s, ahead of the {v.council}.",
    phases=(
        P("inputs", [
            L("forecast", "Send {creditor.first} the usage forecast for the {proj.short}", "I asked {debtor.first} for the usage forecast for the {proj.short}",
              ["usage forecast", "{proj.kw}"], debtor="fin", creditor="worker", w=1.5),
            L("usage", "Send {creditor.first} {hub.short} usage by {v.unit_word}", "I asked {debtor.first} for {hub.short} usage by {v.unit_word}",
              ["usage by {v.unit_word}", "{hub.short}"], debtor="eng", creditor="worker"),
        ], nxt=[("options", 0.12)]),
        P("options", [
            L("options", "Send {creditor.first} the {proj.short} funding options memo", "I owe {creditor.first} the {proj.short} funding options memo",
              ["funding options memo", "{proj.kw}"], creditor="sponsor", kind="ask", due=(3, 6), w=2),
            L("rebase", "Rebase the {proj.short} usage forecast", "{debtor.first} will rebase the {proj.short} usage forecast",
              ["rebase", "{proj.kw}"], debtor="fin", creditor="worker", kind="task"),
        ], nxt=[("review", 0.10)], meetings=["{proj.short} options review"]),
        P("review", [
            L("sens", "Run a sensitivity analysis on the {proj.short}", "{creditor.first} asked for a sensitivity analysis on the {proj.short}",
              ["sensitivity analysis", "{proj.kw}"], creditor="fin", kind="ask"),
        ], nxt=[("council", 0.08)], meetings=["{proj.short} review"]),
        P("council", [
            L("briefing", "Draft the {v.council} briefing note on the {proj.short}", "I owe {creditor.first} the {v.council} briefing note on the {proj.short}",
              ["briefing note", "{proj.kw}"], creditor="sponsor", kind="ask", due=(4, 8)),
        ]),
    ),
    start=("inputs", "options"),
    reversal_reasons=("the {v.council} asked for usage-based pricing", "finance could not find central funds"),
    decisions=(D("d_tier", "Charge {v.unit_word}s a flat platform fee under the {proj.short}", "Decided to charge a flat platform fee under the {proj.short}",
                 ["flat platform fee", "{proj.kw}"], by=("sponsor",),
                 counter=("Charge {v.unit_word}s by usage under the {proj.short}", "Decided to charge by usage under the {proj.short}",
                          ["by usage", "{proj.kw}"]),
                 reasons=("the {v.council} asked for usage-based pricing", "small {v.unit_word}s said a flat fee was unfair")),),
)

FRAMEWORK = Archetype(
    "strategic_framework", "strategic framework that carves out sub-efforts",
    "A {v.unit_word}-wide framework for responsible use of AI, drafted centrally and consulted widely.",
    phases=(
        P("drafting", [
            L("draft", "Circulate the {proj.short} framework draft v1", "I'll circulate the {proj.short} framework draft v1",
              ["framework draft", "{proj.kw}"], creditor="sponsor", kind="task", w=1.5),
            L("principles", "Rewrite the {proj.short} guiding principles", "{creditor.first} asked me to rewrite the {proj.short} guiding principles",
              ["guiding principles", "{proj.kw}"], creditor="sponsor", kind="ask"),
        ], nxt=[("consultation", 0.10)]),
        P("consultation", [
            L("sessions", "Schedule {proj.short} consultation sessions with {unit.short}", "{debtor.first} will schedule {proj.short} consultation sessions",
              ["consultation sessions", "{proj.kw}"], debtor="collab", creditor="worker", kind="task"),
            L("feedback", "Send {creditor.first} {unit.short}'s comments on the {proj.short} framework", "I asked {debtor.first} for {unit.short}'s comments on the {proj.short} framework",
              ["{unit.short}'s comments", "{proj.kw}"], debtor="lead", creditor="worker"),
        ], nxt=[("endorsement", 0.06)], meetings=["{proj.short} consultation"]),
        P("endorsement", [
            L("paper", "Send {creditor.first} the {proj.short} endorsement paper", "I owe {creditor.first} the {proj.short} endorsement paper",
              ["endorsement paper", "{proj.kw}"], creditor="sponsor", kind="ask"),
        ]),
    ),
    start=("drafting", "consultation"),
    decisions=(D("d_tiers", "Adopt a three-tier risk model in the {proj.short} framework", "Decided to adopt a three-tier risk model in the {proj.short} framework",
                 ["three-tier risk model", "{proj.kw}"], by=("sponsor", "worker"),
                 counter=("Adopt a two-tier risk model in the {proj.short} framework",
                          "Decided to adopt a two-tier risk model in the {proj.short} framework",
                          ["two-tier risk model", "{proj.kw}"]),
                 reasons=("{unit.short} found three tiers too complex to apply", "legal advised a simpler model")),),
)

HIRING = Archetype(
    "hiring_pipeline", "hiring pipeline that reopens",
    "Hiring a {role} for the central team.",
    phases=(
        P("sourcing", [
            L("jd", "Post the {proj.short} job description", "{debtor.first} will post the {proj.short} job description",
              ["job description", "{proj.kw}"], debtor="hr", creditor="worker", kind="task"),
            L("jdreview", "Review the {proj.short} job description", "{creditor.first} asked me to review the {proj.short} job description",
              ["review the {proj.short} job description", "job description"], creditor="hr", kind="ask"),
        ], nxt=[("screens", 0.12)]),
        P("screens", [
            L("screen", "Send {creditor.first} my phone screen notes on {cand.first}", "{creditor.first} asked for my phone screen notes on {cand.first}",
              ["phone screen notes", "{cand.first}"], creditor="hr", kind="ask"),
        ], nxt=[("panel", 0.12)], meetings=["Phone screen: {cand.first}"]),
        P("panel", [
            L("panel", "Submit panel feedback for {cand.first}", "{creditor.first} needs my panel feedback for {cand.first}",
              ["panel feedback", "{cand.first}"], creditor="hr", kind="ask", due=(1, 2), w=2),
            L("refs", "Check references for {cand.first}", "{debtor.first} will check references for {cand.first}",
              ["references for {cand.first}", "{cand.first}"], debtor="hr", creditor="worker", kind="task"),
        ], nxt=[("offer", 0.12)], meetings=["Panel: {cand.first}"]),
        P("offer", [
            L("approve", "Approve the offer for {cand.first}", "{debtor.first} will approve the offer for {cand.first}",
              ["offer for {cand.first}", "{cand.first}"], debtor="sponsor", creditor="worker", kind="task"),
            L("startdate", "Agree a start date for the {proj.short} role with {cand.first}", "I'll agree a start date with {cand.first}",
              ["start date", "{proj.kw}"], creditor="cand", kind="task"),
        ], activity=0.6),
    ),
    start=("sourcing", "screens"),
)

EDUCATION = Archetype(
    "education_programme", "education programme revived by one booking",
    "A {topic} learning series for {v.users}, run with {partner.short}.",
    phases=(
        P("dormant", status="active", nxt=(("revived", 0.04),), activity=0.05),
        P("revived", [
            L("session", "Run the first {proj.short} session", "{debtor.first} booked the first {proj.short} session",
              ["first {proj.short} session", "{proj.kw}"], debtor="partner", creditor="worker", kind="task", ch="calendar"),
            L("materials", "Send {cp.first} the {proj.short} pre-reading", "I promised {cp.first} the {proj.short} pre-reading",
              ["pre-reading", "{proj.kw}"]),
            L("pack", "Send {creditor.first} a reading pack for the {proj.short}", "{creditor.first} asked me for a reading pack for the {proj.short}",
              ["reading pack", "{proj.kw}"], creditor="partner", kind="ask"),
        ], nxt=[("scheduling", 0.10)]),
        P("scheduling", [
            L("dates", "Confirm the spring {proj.short} dates", "{debtor.first} will confirm the spring {proj.short} dates",
              ["spring {proj.short} dates", "{proj.kw}"], debtor="collab", creditor="worker", kind="task"),
        ]),
    ),
    start=("dormant",),
)

PLACEHOLDER = Archetype(
    "placeholder", "placeholder",
    "Placeholder for {lead.first}'s {topic} idea at {unit.short}; waiting on a problem statement.",
    phases=(P("placeholder", [
        L("stmt", "Send {creditor.first} the {topic} problem statement", "Waiting on {debtor.first} for the {topic} problem statement",
          ["problem statement", "{topic}"], debtor="lead", creditor="worker", status="waiting"),
    ], activity=0.02),),
    start=("placeholder",),
)

STALLED = Archetype(
    "stalled_discovery", "stalled discovery cited only as evidence",
    "Diligence on {vendor.short}'s {topic} offering; enthusiasm early, nothing dated since.",
    phases=(
        P("diligence", [
            L("deepdive", "Send {creditor.first} the {vendor.short} deep-dive materials", "I asked {debtor.first} for the {vendor.short} deep-dive materials",
              ["deep-dive materials", "{vendor.short}"], debtor="ae", creditor="worker"),
        ], nxt=[("stalled", 0.06)], activity=0.3),
        P("stalled", status="dormant", activity=0.02),
    ),
    start=("diligence", "stalled"),
)

INCIDENT = Archetype(
    "operational_incident", "operational incident",
    "{hub.short} incident affecting {unit.short}: nightly sync jobs failing.",
    phases=(
        P("investigating", [
            L("fix", "Deploy the {proj.short} fix to production", "{debtor.first} is deploying the {proj.short} fix",
              ["{proj.short} fix", "production"], debtor="eng", creditor="worker", kind="task", w=2),
            L("statusmsg", "Send the {proj.short} status update to {unit.short}", "I'll send the {proj.short} status update to {unit.short}",
              ["status update", "{proj.kw}"], creditor="lead", kind="task"),
        ], nxt=[("postmortem", 0.25)], activity=2.0, meetings=["{proj.short} incident standup"]),
        P("postmortem", [
            L("pm", "Write the {proj.short} postmortem", "{creditor.first} asked {debtor.first} for the {proj.short} postmortem",
              ["postmortem", "{proj.kw}"], debtor="owner", creditor="sponsor", kind="ask", due=(4, 6)),
            L("impact", "Write the {unit.short} impact summary for the {proj.short} postmortem", "I owe the {unit.short} impact summary for the postmortem",
              ["impact summary", "{unit.short}"], creditor="owner", kind="ask", due=(2, 4)),
        ], nxt=[("closed", 0.08)], meetings=["{proj.short} postmortem review"]),
        P("closed", status="done", activity=0.0),
    ),
    start=("investigating",),
)

PEER_REVIEW = Archetype(
    "peer_review", "peer review exchange",
    "{owner.first}'s {topic} operating model, out for peer review before it goes to leadership.",
    phases=(
        P("review requested", [
            L("review", "Review {creditor.first}'s {proj.short} draft v2", "{creditor.first} asked me to review the {proj.short} draft v2",
              ["{proj.short} draft v2", "draft v2"], creditor="owner", kind="ask", w=3),
        ], nxt=[("revision", 0.15)]),
        P("revision", [
            L("v3", "Send {creditor.first} the {proj.short} draft v3", "{debtor.first} will send the {proj.short} draft v3",
              ["{proj.short} draft v3", "draft v3"], debtor="owner", creditor="worker", kind="task"),
            L("session", "Book a {proj.short} review session", "{debtor.first} will book a {proj.short} review session",
              ["review session", "{proj.kw}"], debtor="owner", creditor="worker", kind="task"),
        ], nxt=[("done", 0.08)]),
        P("done", status="done", activity=0.0),
    ),
    start=("review requested",),
)

RELATIONSHIP = Archetype(
    "relationship_thread", "relationship thread",
    "Keeping the relationship with {partner.short} warm: introductions, catch-ups and favours.",
    phases=(P("ongoing", [
        L("intro", "Introduce {creditor.first} to {cp.first} for the {partner.short} working group",
          "I offered to introduce {creditor.first} to {cp.first}",
          ["introduce", "{partner.short} working group"], creditor="partner", kind="task", n=2),
        L("catchup", "Set up a {partner.short} catch-up with {creditor.first}", "I said I'd set up a catch-up with {creditor.first}",
          ["{partner.short} catch-up", "catch-up"], creditor="partner", kind="task"),
        L("paper", "Send {creditor.first} the {partner.short} working paper", "{debtor.first} offered the {partner.short} working paper",
          ["working paper", "{partner.short}"], debtor="partner", creditor="worker", kind="task"),
    ], activity=0.5),),
    start=("ongoing",),
)

DELEGATED = Archetype(
    "delegated_asks", "delegated asks",
    "Collecting input from {v.unit_word}s on {topic} for {sponsor.first}.",
    phases=(
        P("asking", [
            L("input", "Send {creditor.first} {unit.short}'s input on {topic}", "I asked {debtor.first} for {unit.short}'s input on {topic}",
              ["input on {topic}", "{unit.short}"], debtor="lead", creditor="worker", n=3, w=3),
            L("summary", "Summarize the {topic} input for {creditor.first}", "I owe {creditor.first} a summary of the {topic} input",
              ["{topic} input", "summarize"], creditor="sponsor", kind="ask"),
        ], nxt=[("collected", 0.05)]),
        P("collected", status="done", activity=0.0),
    ),
    start=("asking",),
)

ARCHETYPES: dict[str, Archetype] = {
    a.name: a
    for a in (
        FLAGSHIP, HUB, VENDOR_PAIR, UNIT_DISCOVERY, PIVOTING, ADVISORY, SUPPLIER, EVENT, INCUBATION,
        ECONOMICS, FRAMEWORK, HIRING, EDUCATION, PLACEHOLDER, STALLED, INCIDENT, PEER_REVIEW,
        RELATIONSHIP, DELEGATED,
    )
}

# Archetypes a mid-size or small project can take (the planner draws from these).
MID_ARCHETYPES = (
    "vendor_pair_evaluation", "unit_discovery", "pivoting_discovery", "economics_model",
    "strategic_framework", "hiring_pipeline", "event_preparation", "internal_incubation",
    "supplier_negotiation",
)
SMALL_ARCHETYPES = ("background_advisory", "peer_review", "relationship_thread", "delegated_asks")
DORMANT_ARCHETYPES = ("stalled_discovery", "education_programme")


def get(name: str) -> Archetype:
    return ARCHETYPES[name]


# Artifact nouns for `{noun}` slots, per archetype, so that a hiring project asks for an interview
# scorecard rather than an integration spec. Archetypes missing here (the flagship, the hub, the
# incident) draw from the setting's nouns; every archetype falls back to `GENERIC_NOUNS`.
NOUNS: dict[str, tuple[str, ...]] = {
    "vendor_pair_evaluation": ("evaluation rubric", "vendor comparison", "requirements matrix", "demo script",
                               "reference-check notes", "pricing comparison", "risk register", "decision memo"),
    "unit_discovery": ("interview guide", "process map", "stakeholder map", "findings summary", "survey questions",
                       "pain-point list", "observation notes", "opportunity list"),
    "pivoting_discovery": ("interview guide", "process map", "stakeholder map", "findings summary",
                           "problem framing note", "pain-point list", "observation notes", "opportunity list"),
    "economics_model": ("cost model", "usage forecast", "pricing options table", "assumptions log",
                        "budget justification", "chargeback scenarios"),
    "strategic_framework": ("consultation plan", "principles draft", "glossary", "risk taxonomy", "comment log",
                            "decision memo"),
    "hiring_pipeline": ("interview scorecard", "interview plan", "role profile", "sourcing plan", "question bank",
                        "candidate pack"),
    "event_preparation": ("run sheet", "speaker brief", "registration list", "session outline", "feedback form",
                          "room plan"),
    "internal_incubation": ("user journey map", "backlog snapshot", "usability test script", "release notes",
                            "roadmap slide", "feature list"),
    "supplier_negotiation": ("seat-count summary", "pricing comparison", "term sheet", "redline summary",
                             "negotiation brief", "renewal timeline"),
    "background_advisory": ("guidance comments", "reading list", "options note", "FAQ draft"),
    "peer_review": ("review comments", "comparison table", "summary of changes"),
    "relationship_thread": ("meeting notes", "working paper summary", "contact list", "event invitation"),
    "delegated_asks": ("input template", "response tracker", "summary table", "reminder note"),
    "education_programme": ("session outline", "attendance list", "feedback form", "speaker brief"),
    "placeholder": ("problem statement draft", "one-pager"),
    "stalled_discovery": ("diligence notes", "reference-check notes", "question list"),
    "operational_incident": ("incident timeline", "runbook update", "status page draft", "root-cause notes"),
}
# Nouns that fit any project.
GENERIC_NOUNS = ("decision memo", "status slide", "timeline", "risk register", "comms plan", "lessons-learned note",
                 "stakeholder map", "dependency list", "one-page summary", "action log")
# Archetypes whose `{noun}` also draws on the setting's domain nouns (exports, audits, specs).
DOMAIN_NOUN_ARCHETYPES = frozenset({"flagship_pilot", "platform_hub", "operational_incident", "unit_discovery",
                                    "pivoting_discovery"})


_SLOT = re.compile(r"\{([a-z_0-9]+)(?:\.([a-z_0-9]+))?\}")


def check_library() -> list[str]:
    """Problems in the beat library: keywords that are not substrings of `what`, missing text,
    unknown roles or phases. Empty when the library is sound."""
    problems: list[str] = []
    for arch in ARCHETYPES.values():
        names = {p.name for p in arch.phases}
        for s in arch.start:
            if s not in names:
                problems.append(f"{arch.name}: start phase {s!r} unknown")
        for p in arch.phases:
            for nxt, prob in p.next:
                if nxt not in names or not 0 < prob <= 1:
                    problems.append(f"{arch.name}.{p.name}: bad transition {nxt!r} {prob}")
        for b in arch.beats():
            problems += _beat_problems(f"{arch.name}.{b.key}", b)
        problems += _desc_state_problems(arch)
    for b in GENERIC + UNATTACHED:
        problems += _beat_problems(f"generic.{b.key}", b)
    return problems


def _desc_state_problems(arch: Archetype) -> list[str]:
    """Description slots must appear in `desc`; decision effects must change state that `desc`
    shows, and only through a replacement decision (`counter`)."""
    out: list[str] = []
    used = {m.group(1) for m in _SLOT.finditer(arch.desc)}
    slots = {name for name, _ in arch.slots}
    for name in slots - used:
        out.append(f"{arch.name}: slot {{{name}}} is not in desc {arch.desc!r}")
    for b in arch.beats():
        for slot, value in b.effect:
            where = f"{arch.name}.{b.key}"
            if b.type != "decision" or b.counter is None:
                out.append(f"{where}: only a decision with a counter can have an effect")
            if slot == "n":
                if "n" not in used or not re.fullmatch(r"\+[1-9]", value):
                    out.append(f"{where}: effect n={value!r} needs {{n}} in desc and a value like '+1'")
            elif slot not in slots:
                out.append(f"{where}: effect slot {slot!r} is not one of the archetype's slots")
    return out


def _beat_problems(where: str, b: Beat) -> list[str]:
    out: list[str] = []
    if b.type in ("loop", "decision"):
        if not b.what or not b.summary:
            out.append(f"{where}: needs what and summary")
        if len(b.keywords) < 2:
            out.append(f"{where}: needs at least two keywords")
        what = b.what.lower()
        for kw in b.keywords:
            # {proj.kw} is a substring of {proj.short} by construction (see the planner).
            if kw.lower().replace("{proj.kw}", "{proj.short}") not in what:
                out.append(f"{where}: keyword {kw!r} is not in what {b.what!r}")
    if b.type == "loop":
        for role in (b.debtor, b.creditor, b.others):
            if role is not None and role not in ROLES:
                out.append(f"{where}: unknown role {role!r}")
        if b.kind not in ("task", "ask"):
            out.append(f"{where}: kind {b.kind!r}")
    if b.type == "decision":
        for role in b.by:
            if role not in ROLES:
                out.append(f"{where}: unknown role {role!r}")
        if b.counter is not None:
            cwhat, csummary, ckws = b.counter
            if not cwhat or not csummary or len(ckws) < 2:
                out.append(f"{where}: counter needs what, summary and two keywords")
            for kw in ckws:
                if kw.lower().replace("{proj.kw}", "{proj.short}") not in cwhat.lower():
                    out.append(f"{where}: counter keyword {kw!r} is not in {cwhat!r}")
    if b.type == "fact" and b.attr is None:
        out.append(f"{where}: fact beat needs attr")
    return out
