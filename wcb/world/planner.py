"""World planner: sample a synthetic organization, cast, portfolio and challenge schedule.

`make_plan(seed, ...)` returns the content of `plan.yaml` (docs/generator.md, "Planner"): a
plain, JSON- and YAML-serializable dict that the simulator turns into world events and
communications. Everything is drawn from one `random.Random`, so the same arguments always
produce the same plan.

The plan contains:

- `setting`: one of several organization templates (`SETTINGS`), its time zone and vocabulary;
- `calendar`: two seed weeks before the episode start (a Monday), the episode days (Monday to
  Friday plus an optional light Saturday per week) and the checkpoints;
- `orgs`, `people`, `worker`: an umbrella organization, a central team in which the worker is a
  senior individual contributor with no direct reports, 3-5 semi-autonomous units, 2-3 vendors,
  partners, a candidate and minor senders; deliberate first-name collisions and a
  near-homophone pair;
- `projects`: a heavy-tailed portfolio (one flagship, one hub, mid-size, small, placeholder and
  dormant projects), each with an archetype, an initial phase, a cast and a weight;
- `cadences`: recurring meetings and obligations;
- `challenges`: a schedule that places every planted-challenge tag (docs/formats.md §1.4) at
  least once in every episode week.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from wcb.util.dates import add_days, parse_date
from wcb.world import archetypes as A
from wcb.world.names import (
    HOMOPHONE_PAIRS,
    NICKNAMES,
    NameGen,
    ascii_slug,
    email_local,
    person_surface_forms,
)

GENERATOR_VERSION = 1

CHALLENGE_TAGS = (
    "supersession", "reversal", "alias", "name_collision", "new_entity", "duplicate_signal",
    "implied_commitment", "weak_evidence", "transfer", "silent_closure", "noise", "unobservable",
    "draft_vs_sent", "acceptance_vs_occurrence", "correction", "restructuring", "endorsement",
    "worker_directive", "version_mismatch", "batch_catchup", "scattered_evidence", "privacy",
)

SIZES: dict[str, dict[str, Any]] = {
    "small": {
        "projects": (6, 8), "units": (3, 3), "unit_staff": (1, 1), "vendors": (2, 2),
        "partners": (1, 1), "minor": 5, "mids": (2, 3), "smalls": (1, 1), "dormant": (1, 1),
        "volume": (10, 14), "loops_per_day": 4.2,
    },
    "standard": {
        "projects": (10, 14), "units": (3, 5), "unit_staff": (1, 2), "vendors": (2, 3),
        "partners": (1, 2), "minor": 7, "mids": (4, 6), "smalls": (2, 3), "dormant": (1, 2),
        "volume": (15, 20), "loops_per_day": 5.8,
    },
    "large": {
        "projects": (16, 20), "units": (5, 5), "unit_staff": (2, 3), "vendors": (3, 3),
        "partners": (2, 2), "minor": 8, "mids": (7, 9), "smalls": (3, 4), "dormant": (2, 3),
        "volume": (20, 26), "loops_per_day": 7.5,
    },
}


# ---------------------------------------------------------------- organization templates
@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    timezone: str
    umbrella: str  # pattern with {place}
    central: tuple[tuple[str, str], ...]  # (name, acronym) choices
    unit_patterns: tuple[str, ...]  # patterns with {place}
    unit_word: str
    vocab: dict[str, str]
    worker_titles: tuple[str, ...]
    roles: dict[str, tuple[str, str]]  # central/functional role key -> (title, role phrase)
    unit_head: tuple[str, str]
    unit_lead_titles: tuple[str, ...]
    unit_staff_titles: tuple[str, ...]
    partner_patterns: tuple[str, ...]
    topics: tuple[tuple[str, str], ...]  # (modifier, "an AI ... assistant" phrase)
    pivots: tuple[str, ...]
    hire_roles: tuple[str, ...]
    event_topics: tuple[str, ...]
    nouns: tuple[str, ...]
    newsletters: tuple[str, ...]
    framework: str = "AI-use"
    extra: dict[str, str] = field(default_factory=dict)


COMMON_NOUNS = (
    "risk register", "rollout checklist", "test plan", "decision memo", "status slide",
    "comms plan", "training outline", "budget justification", "vendor comparison",
    "architecture diagram", "integration spec", "access request", "pilot charter",
    "evaluation rubric", "data dictionary", "stakeholder map", "dependency list",
    "requirements matrix", "lessons-learned note", "timeline", "RACI chart", "cutover plan",
    "acceptance criteria", "metrics definition", "service blueprint", "support model",
    "retention schedule", "change request", "accessibility review", "help-desk script",
)

SETTINGS: dict[str, Setting] = {
    "university": Setting(
        key="university", label="public university system", timezone="-08:00",
        umbrella="{place} University System",
        central=(("Office of Academic Technology", "OAT"), ("Systemwide Learning Innovation Office", "SLIO"),
                 ("Academic Innovation Office", "AIO")),
        unit_patterns=("{place} University", "{place} State College", "University of {place}"),
        unit_word="campus",
        vocab={"sites": "courses", "site": "course", "users": "faculty", "end_users": "students",
               "council": "Council of Provosts", "data": "student data", "agreement": "data-sharing agreement",
               "platform": "shared AI platform", "unit_word": "campus"},
        worker_titles=("Principal Architect, AI Platforms", "Lead Solutions Architect, Teaching Technology",
                       "Principal Technologist, Learning Systems"),
        roles={
            "manager": ("Associate Provost for Academic Technology", "the associate provost"),
            "collab": ("Director of Programs", "our programs director"),
            "eng": ("Principal, Platform Engineering", "the platform lead"),
            "eng2": ("Platform Engineer", "the platform engineer"),
            "sec": ("Principal, Security & Identity", "the security principal"),
            "product": ("Principal, Product", "the product principal"),
            "ea": ("Executive Assistant to the Associate Provost", "the provost's EA"),
            "analyst": ("Senior Data Analyst", "our data analyst"),
            "proc": ("Procurement Officer, System Procurement", "the procurement officer"),
            "legal": ("Associate Counsel, System Legal", "system counsel"),
            "fin": ("Director, System Budget Office", "the budget director"),
            "hr": ("Talent Partner, System HR", "our talent partner"),
            "privacy": ("Chief Privacy Officer", "the privacy officer"),
        },
        unit_head=("Chief Information Officer", "CIO"),
        unit_lead_titles=("Director, Teaching & Learning Technology", "Registrar", "Dean of Libraries",
                          "Director of Advising", "Director of Institutional Research"),
        unit_staff_titles=("Software Engineer", "Instructional Designer", "Identity & Access Administrator",
                           "Service Desk Lead", "Site Reliability Engineer", "Enterprise Architect"),
        partner_patterns=("{place} Institute for Learning Research", "{place} Center for Digital Pedagogy"),
        topics=(("course assistant", "an AI course assistant"), ("transfer credit evaluation", "an AI transfer-credit evaluator"),
                ("advising scheduling", "an AI advising scheduler"), ("library research", "an AI library research assistant"),
                ("captioning", "an AI captioning service"), ("admissions triage", "an AI admissions document triage tool"),
                ("early alert", "an AI early-alert assistant"), ("financial aid chat", "an AI financial aid assistant"),
                ("course scheduling", "an AI course scheduling optimizer"), ("research computing", "an AI research computing broker"),
                ("syllabus review", "an AI syllabus review tool"), ("writing feedback", "an AI writing feedback tool")),
        pivots=("advising wait times", "prerequisite mapping", "transcript intake", "waitlist management"),
        hire_roles=("staff data engineer", "ML platform engineer", "accessibility specialist"),
        event_topics=("AI literacy", "assessment design", "open courseware"),
        nouns=COMMON_NOUNS + ("course roster export", "LMS integration notes", "accessibility audit", "faculty survey"),
        newsletters=("The Quad Ledger", "Campus Systems Weekly", "EdTech Signal"),
        extra={"vendor_suffixes": "Labs,Learning,Software,Analytics,AI"},
    ),
    "health": Setting(
        key="health", label="regional health network", timezone="-05:00",
        umbrella="{place} Health Partners",
        central=(("Shared Services Digital Office", "SSDO"), ("Clinical Digital Services", "CDS"),
                 ("Network Digital Office", "NDO")),
        unit_patterns=("{place} General Hospital", "{place} Medical Center", "{place} Community Clinics",
                       "{place} Children's Hospital", "{place} Rehabilitation Center"),
        unit_word="hospital",
        vocab={"sites": "wards", "site": "ward", "users": "nurses", "end_users": "patients",
               "council": "Clinical Operations Council", "data": "patient data", "agreement": "data-use agreement",
               "platform": "shared AI platform", "unit_word": "hospital"},
        worker_titles=("Principal Architect, Clinical AI", "Lead Solutions Architect, Shared Services",
                       "Principal Technologist, Clinical Systems"),
        roles={
            "manager": ("Chief Digital Officer", "the CDO"),
            "collab": ("Director of Digital Programs", "our programs director"),
            "eng": ("Principal, Integration Platform", "the platform lead"),
            "eng2": ("Integration Engineer", "the integration engineer"),
            "sec": ("Principal, Information Security", "the security principal"),
            "product": ("Product Lead, Clinical Apps", "the product lead"),
            "ea": ("Executive Assistant to the CDO", "the CDO's EA"),
            "analyst": ("Clinical Data Analyst", "our clinical analyst"),
            "proc": ("Supply Chain Contracts Manager", "the contracts manager"),
            "legal": ("Associate General Counsel", "network counsel"),
            "fin": ("Director, Finance Shared Services", "the finance director"),
            "hr": ("Talent Acquisition Partner", "our talent partner"),
            "privacy": ("Network Privacy Officer", "the privacy officer"),
        },
        unit_head=("Chief Medical Information Officer", "CMIO"),
        unit_lead_titles=("Chief Nursing Officer", "Director of Patient Access", "Clinical Informatics Lead",
                          "Director of Pharmacy", "Operations Director"),
        unit_staff_titles=("Nurse Informaticist", "Application Analyst", "Interface Engineer",
                           "Service Desk Lead", "Charge Nurse", "Revenue Cycle Analyst"),
        partner_patterns=("{place} Institute for Health Services Research", "{place} Nursing Research Collaborative"),
        topics=(("discharge summary", "an AI discharge summary assistant"), ("prior authorization", "an AI prior-authorization triage tool"),
                ("nurse scheduling", "an AI nurse scheduling assistant"), ("portal message routing", "an AI patient-portal message router"),
                ("radiology follow-up", "an AI radiology follow-up tracker"), ("bed management", "an AI bed management dashboard"),
                ("intake forms", "an AI intake forms reader"), ("denials analytics", "an AI claims-denial analyzer"),
                ("interpreter booking", "an AI interpreter booking assistant"), ("supply par levels", "an AI supply par-level forecaster"),
                ("clinical documentation", "an AI clinical documentation assistant"), ("referral triage", "an AI referral triage tool")),
        pivots=("outpatient no-shows", "discharge delays", "referral backlog", "medication reconciliation"),
        hire_roles=("clinical data engineer", "ML operations engineer", "informatics nurse specialist"),
        event_topics=("AI safety rounds", "clinical AI literacy", "documentation burden"),
        nouns=COMMON_NOUNS + ("bed census extract", "order set review", "downtime procedure", "clinical safety case"),
        newsletters=("Health Systems Dispatch", "The Ward Round Digest", "Clinical IT Briefing"),
        extra={"vendor_suffixes": "Health,Clinical,Labs,Systems,Analytics"},
    ),
    "manufacturer": Setting(
        key="manufacturer", label="mid-size manufacturer", timezone="-06:00",
        umbrella="{place} Industries",
        central=(("Digital Operations Office", "DOO"), ("Manufacturing Digital Office", "MDO"),
                 ("Operations Technology Group", "OTG")),
        unit_patterns=("{place} Plant", "{place} Assembly", "{place} Components", "{place} Distribution Center"),
        unit_word="plant",
        vocab={"sites": "lines", "site": "line", "users": "operators", "end_users": "customers",
               "council": "Plant Leadership Council", "data": "production data", "agreement": "data-sharing addendum",
               "platform": "shared data platform", "unit_word": "plant"},
        worker_titles=("Principal Architect, Industrial AI", "Lead Solutions Architect, Operations Technology",
                       "Principal Technologist, Smart Manufacturing"),
        roles={
            "manager": ("VP Digital Operations", "the VP"),
            "collab": ("Director of Digital Programs", "our programs director"),
            "eng": ("Principal, Data Platform", "the platform lead"),
            "eng2": ("Data Platform Engineer", "the platform engineer"),
            "sec": ("Principal, OT Security", "the OT security lead"),
            "product": ("Product Lead, Operator Tools", "the product lead"),
            "ea": ("Executive Assistant to the VP", "the VP's EA"),
            "analyst": ("Operations Data Analyst", "our ops analyst"),
            "proc": ("Strategic Sourcing Manager", "the sourcing manager"),
            "legal": ("Corporate Counsel", "corporate counsel"),
            "fin": ("Plant Finance Director", "the finance director"),
            "hr": ("Talent Partner", "our talent partner"),
            "privacy": ("Data Protection Officer", "the data protection officer"),
        },
        unit_head=("Plant Manager", "plant manager"),
        unit_lead_titles=("Quality Engineering Lead", "Maintenance Manager", "Production Planning Lead",
                          "Continuous Improvement Lead", "Logistics Manager"),
        unit_staff_titles=("Controls Engineer", "Maintenance Supervisor", "Process Engineer",
                           "Shift Supervisor", "Quality Technician", "MES Administrator"),
        partner_patterns=("{place} Advanced Manufacturing Institute", "{place} Industrial Research Center"),
        topics=(("predictive maintenance", "an AI predictive maintenance assistant"), ("visual inspection", "an AI visual quality inspector"),
                ("supplier onboarding", "an AI supplier onboarding portal"), ("production scheduling", "an AI production scheduling assistant"),
                ("energy monitoring", "an AI energy monitoring dashboard"), ("shift handover", "an AI shift handover assistant"),
                ("warranty claims", "an AI warranty claims analyzer"), ("spare parts", "an AI spare parts forecaster"),
                ("work instructions", "an AI work instruction assistant"), ("safety reporting", "an AI safety incident triage tool"),
                ("changeover planning", "an AI changeover planner"), ("scrap analysis", "an AI scrap analysis tool")),
        pivots=("changeover downtime", "tooling wear", "inbound dock delays", "label errors"),
        hire_roles=("controls data engineer", "ML engineer", "OT security analyst"),
        event_topics=("operator AI basics", "lean and data", "safety analytics"),
        nouns=COMMON_NOUNS + ("line downtime report", "sensor tag list", "PLC export", "control plan"),
        newsletters=("Shop Floor Signal", "Plant Ops Weekly", "Industrial Data Digest"),
        extra={"vendor_suffixes": "Systems,Industrial,Analytics,Labs,Automation"},
    ),
    "city": Setting(
        key="city", label="city government digital service", timezone="-07:00",
        umbrella="City of {place}",
        central=(("{place} Digital Service", "DS"), ("Office of Civic Technology", "OCT"),
                 ("Citywide Digital Services", "CDS")),
        unit_patterns=("{place} Department of Transportation", "{place} Parks and Recreation",
                       "{place} Housing Services", "{place} Public Works", "{place} Permitting Office",
                       "{place} Library Services"),
        unit_word="department",
        vocab={"sites": "service centers", "site": "service center", "users": "caseworkers", "end_users": "residents",
               "council": "Digital Steering Committee", "data": "resident data", "agreement": "data-sharing agreement",
               "platform": "shared AI platform", "unit_word": "department"},
        worker_titles=("Principal Architect, AI Services", "Lead Product Architect", "Senior Technologist, Civic AI"),
        roles={
            "manager": ("Chief Digital Officer", "the CDO"),
            "collab": ("Director of Delivery", "our delivery director"),
            "eng": ("Principal, Platform Engineering", "the platform lead"),
            "eng2": ("Platform Engineer", "the platform engineer"),
            "sec": ("Chief Information Security Officer", "the CISO"),
            "product": ("Product Lead, Resident Services", "the product lead"),
            "ea": ("Executive Assistant to the CDO", "the CDO's EA"),
            "analyst": ("Performance Analyst", "our performance analyst"),
            "proc": ("Purchasing Agent", "the purchasing agent"),
            "legal": ("Deputy City Attorney", "the deputy city attorney"),
            "fin": ("Budget Director", "the budget director"),
            "hr": ("Recruitment Partner", "our recruitment partner"),
            "privacy": ("Privacy Officer", "the privacy officer"),
        },
        unit_head=("Department Director", "director"),
        unit_lead_titles=("Deputy Director", "Customer Service Manager", "Program Manager", "Operations Manager",
                          "Chief of Staff"),
        unit_staff_titles=("GIS Analyst", "Business Analyst", "Systems Administrator", "Caseworker Supervisor",
                           "Records Manager", "Web Coordinator"),
        partner_patterns=("{place} Civic Data Collaborative", "{place} Institute for Public Service Design"),
        topics=(("service request triage", "an AI service request triage tool"), ("permit intake", "an AI permit intake assistant"),
                ("benefits screening", "an AI benefits eligibility screener"), ("meeting minutes", "an AI meeting minutes drafter"),
                ("notice translation", "an AI public notice translator"), ("street tree inventory", "an AI street tree inventory"),
                ("pothole reporting", "an AI pothole reporting assistant"), ("records requests", "an AI records request router"),
                ("parking analytics", "an AI parking analytics dashboard"), ("library help", "an AI library help assistant"),
                ("inspection scheduling", "an AI inspection scheduler"), ("code enforcement", "an AI code enforcement triage tool")),
        pivots=("inspection backlog", "call-center wait times", "duplicate requests", "fee waiver delays"),
        hire_roles=("data engineer", "service designer", "accessibility specialist"),
        event_topics=("AI in public service", "plain language", "open data"),
        nouns=COMMON_NOUNS + ("service request extract", "council memo", "equity impact review", "public notice draft"),
        newsletters=("Civic Tech Bulletin", "The Municipal Byte", "Public Sector Digital Weekly"),
        extra={"vendor_suffixes": "Civic,Software,Labs,Systems,Analytics"},
    ),
    "nonprofit": Setting(
        key="nonprofit", label="nonprofit federation", timezone="+01:00",
        umbrella="{place} Community Federation",
        central=(("Federation Digital Hub", "FDH"), ("Shared Technology Office", "STO"),
                 ("Federation Data Office", "FDO")),
        unit_patterns=("{place} Food Network", "{place} Literacy Council", "{place} Youth Alliance",
                       "{place} Housing Trust", "{place} Family Services"),
        unit_word="member organization",
        vocab={"sites": "branches", "site": "branch", "users": "volunteers", "end_users": "clients",
               "council": "Federation Board", "data": "client data", "agreement": "data-sharing agreement",
               "platform": "shared data platform", "unit_word": "member organization"},
        worker_titles=("Principal Architect, Data & AI", "Lead Solutions Architect", "Senior Technologist"),
        roles={
            "manager": ("Director of Shared Technology", "the director"),
            "collab": ("Programs Manager", "our programs manager"),
            "eng": ("Platform Lead", "the platform lead"),
            "eng2": ("Data Engineer", "the data engineer"),
            "sec": ("Security & Privacy Lead", "the security lead"),
            "product": ("Product Manager", "the product manager"),
            "ea": ("Operations Coordinator", "the ops coordinator"),
            "analyst": ("Impact Analyst", "our impact analyst"),
            "proc": ("Grants & Contracts Officer", "the contracts officer"),
            "legal": ("Pro Bono Counsel", "our counsel"),
            "fin": ("Finance Director", "the finance director"),
            "hr": ("People Partner", "our people partner"),
            "privacy": ("Data Protection Lead", "the data protection lead"),
        },
        unit_head=("Executive Director", "ED"),
        unit_lead_titles=("Programs Director", "Volunteer Coordinator", "Development Director", "Operations Lead"),
        unit_staff_titles=("Database Administrator", "Program Coordinator", "Case Manager", "Volunteer Lead",
                           "Grants Writer"),
        partner_patterns=("{place} Philanthropy Lab", "{place} Social Research Institute"),
        topics=(("volunteer matching", "an AI volunteer matching assistant"), ("grant reporting", "an AI grant reporting assistant"),
                ("donor records", "an AI donor records cleaner"), ("pantry inventory", "an AI pantry inventory forecaster"),
                ("outcomes dashboard", "an AI outcomes dashboard"), ("helpline triage", "an AI multilingual helpline"),
                ("case notes", "an AI case notes assistant"), ("eligibility intake", "an AI eligibility intake tool"),
                ("event signups", "an AI event signup assistant"), ("newsletter drafting", "an AI newsletter drafter"),
                ("referral matching", "an AI referral matching tool"), ("translation help", "an AI translation helper"),
                ("shift rostering", "an AI shift rostering assistant")),
        pivots=("volunteer no-shows", "duplicate client records", "intake wait times"),
        hire_roles=("data engineer", "digital programs lead"),
        event_topics=("data literacy", "AI for small charities", "digital safeguarding"),
        nouns=COMMON_NOUNS + ("client intake form", "member survey", "safeguarding checklist", "board paper"),
        newsletters=("Third Sector Tech", "The Charity Data Letter", "Community Digital Notes"),
        extra={"vendor_suffixes": "Software,Labs,Cloud,Analytics,Impact"},
    ),
}

VOICES = ("formal", "terse", "chatty", "lowercase")

# Archetypes whose project is about a domain topic drawn from the setting.
TOPIC_ARCHETYPES = frozenset(
    {"flagship_pilot", "vendor_pair_evaluation", "unit_discovery", "pivoting_discovery",
     "internal_incubation", "background_advisory", "delegated_asks", "education_programme",
     "placeholder", "stalled_discovery"}
)
FIXED_TOPICS = {
    "platform_hub": "shared platform", "economics_model": "cost sharing",
    "strategic_framework": "responsible AI use", "supplier_negotiation": "licensing",
    "peer_review": "platform", "relationship_thread": "partnership",
}


# ---------------------------------------------------------------- the planner
def make_plan(
    seed: int,
    *,
    weeks: int = 1,
    size: str = "standard",
    world_id: str | None = None,
    start: str = "2027-04-05",
    setting: str | None = None,
) -> dict:
    """The plan (plan.yaml content) for a world. Deterministic in its arguments.

    `start` must be a Monday: the first episode day. The seed is the two weeks before it.
    `setting` forces an organization template (default: drawn from the seed).
    """
    if size not in SIZES:
        raise ValueError(f"size must be one of {', '.join(SIZES)}")
    if weeks < 1:
        raise ValueError("weeks must be at least 1")
    if parse_date(start).weekday() != 0:
        raise ValueError(f"start {start} is not a Monday")
    rng = random.Random(f"wcb-plan:{seed}:{size}:{weeks}")
    return _Planner(rng, seed, weeks, size, world_id or f"gen-s{seed}-w{weeks}", start, setting).build()


class _Planner:
    def __init__(self, rng: random.Random, seed: int, weeks: int, size: str, world_id: str,
                 start: str, setting: str | None):
        self.rng = rng
        self.seed = seed
        self.weeks = weeks
        self.size = size
        self.sz = SIZES[size]
        self.world_id = world_id
        self.start = start
        key = setting or rng.choice(sorted(SETTINGS))
        if key not in SETTINGS:
            raise ValueError(f"unknown setting {key!r}")
        self.st = SETTINGS[key]
        self.names = NameGen(rng)
        self.orgs: list[dict] = []
        self.people: list[dict] = []
        self.projects: list[dict] = []
        self.used_handles: set[str] = set()
        self.used_phrases: set[str] = set()
        self.used_topics: set[str] = set()

    # ------------------------------------------------------------ build
    def build(self) -> dict:
        cal = self._calendar()
        self.cal = cal
        self._orgs()
        self._cast()
        self._portfolio()
        cadences = self._cadences()
        challenges = self._challenges()
        return {
            "plan_version": GENERATOR_VERSION,
            "world_id": self.world_id,
            "generator": {"kind": "wcb-gen", "version": GENERATOR_VERSION, "seed": self.seed,
                          "size": self.size, "weeks": self.weeks},
            "setting": {
                "key": self.st.key, "label": self.st.label, "timezone": self.st.timezone,
                "vocab": dict(self.st.vocab), "nouns": list(self.st.nouns),
                "umbrella": self.umbrella["id"], "central": self.central["id"],
                "video_domain": f"meet.{self.umbrella['domain']}",
                "chat_workspace": self.umbrella["slug"],
                "volume": list(self.sz["volume"]), "loops_per_day": self.sz["loops_per_day"],
            },
            "calendar": cal,
            "worker": self.worker["id"],
            "orgs": self.orgs,
            "people": self.people,
            "projects": self.projects,
            "collisions": self.collisions,
            "cadences": cadences,
            "challenges": challenges,
        }

    # ------------------------------------------------------------ calendar
    def _calendar(self) -> dict:
        start = self.start
        seed_start = add_days(start, -14)
        seed_sat = self.rng.random() < 0.7
        seed_days: list[str] = []
        for w in range(2):
            monday = add_days(seed_start, 7 * w)
            seed_days += [add_days(monday, i) for i in range(5)]
            if seed_sat:
                seed_days.append(add_days(monday, 5))
        weeks: list[list[str]] = []
        for w in range(self.weeks):
            monday = add_days(start, 7 * w)
            days = [add_days(monday, i) for i in range(5)]
            if self.rng.random() < 0.85:
                days.append(add_days(monday, 5))
            weeks.append(days)
        checkpoints = []
        for w, days in enumerate(weeks):
            for d, label in ((days[1], "end of Tuesday"), (days[3], "end of Thursday"),
                             (days[-1], "end of week")):
                checkpoints.append({"id": f"cp{len(checkpoints) + 1}", "date": d,
                                    "label": label + (f" (week {w + 1})" if self.weeks > 1 else "")})
        return {
            "start": start,
            "seed": {"start": seed_start, "end": seed_days[-1], "days": seed_days},
            "episode": {"days": [d for days in weeks for d in days], "weeks": weeks},
            "checkpoints": checkpoints,
        }

    # ------------------------------------------------------------ organizations
    def _org(self, name: str, kind: str, role: str, domain: str, *, short: str, forms: list[str],
             receptiveness: str | None = None) -> dict:
        oid = "o-" + ascii_slug(name)
        org = {"id": oid, "name": name, "short": short, "kind": kind, "role": role, "domain": domain,
               "slug": ascii_slug(short), "surface_forms": _dedup([*forms, domain]),
               "receptiveness": receptiveness}
        self.orgs.append(org)
        return org

    def _orgs(self) -> None:
        st, rng = self.st, self.rng
        place = self.names.place()
        uname = st.umbrella.format(place=place)
        udomain = f"{ascii_slug(place)}.example"
        self.umbrella = self._org(uname, "internal", "umbrella", udomain, short=place,
                                  forms=[place, _acronym(uname)])
        cname, cacr = rng.choice(st.central)
        cname = cname.format(place=place)
        self.central = self._org(cname, "internal", "central", udomain, short=cacr,
                                 forms=[cacr, "central", f"the {cacr} team"])
        n_units = rng.randint(*self.sz["units"])
        patterns = list(st.unit_patterns)
        rng.shuffle(patterns)
        recept = ["high", "medium", "low", "low", "medium"]
        self.units = []
        for i in range(n_units):
            up = self.names.place()
            name = patterns[i % len(patterns)].format(place=up)
            dom = f"{ascii_slug(up)}.{udomain}"
            self.units.append(self._org(name, "internal", "unit", dom, short=up,
                                        forms=[up, _acronym(name)], receptiveness=recept[i]))
        self.vendors = []
        for _ in range(rng.randint(*self.sz["vendors"])):
            full, short = self.names.vendor(self.st.extra.get("vendor_suffixes", "").split(",") or None)
            self.vendors.append(self._org(full, "vendor", "vendor", f"{ascii_slug(short)}.example",
                                          short=short, forms=[short]))
        self.partners = []
        for _ in range(rng.randint(*self.sz["partners"])):
            pp = self.names.place()
            name = rng.choice(st.partner_patterns).format(place=pp)
            self.partners.append(self._org(name, "partner", "partner", f"{ascii_slug(pp)}-research.example",
                                           short=pp, forms=[pp, _acronym(name)]))

    # ------------------------------------------------------------ people
    def _person(self, org: dict | None, title: str, relationship: str, group: str, *,
                phrase: str | None = None, first: str | None = None, weight: float = 1.0,
                appears: str | None = None, minor: bool = False) -> dict:
        if minor:
            f, last = self.names.person()
        else:
            f, last = self.names.person(first=first)
        nick = NICKNAMES.get(f) if not minor and self.rng.random() < 0.75 else None
        name = f"{f} {last}"
        pid = "p-" + ascii_slug(name)
        while any(p["id"] == pid for p in self.people):
            pid += "-2"
        domain = org["domain"] if org else "post.example"
        email = f"{email_local(f, last)}@{domain}"
        handle = "@" + ascii_slug(f).replace("-", "")
        if handle in self.used_handles:
            handle = handle + ascii_slug(last)[:1]
        while handle in self.used_handles:
            handle += "x"
        self.used_handles.add(handle)
        if phrase and phrase in self.used_phrases:
            phrase = None
        if phrase:
            self.used_phrases.add(phrase)
        person = {
            "id": pid, "name": name, "first": f, "last": last, "nickname": nick,
            "org": org["id"] if org else None, "role": title, "role_phrase": phrase,
            "email": email, "handle": handle, "relationship": relationship, "group": group,
            "tier": "minor" if minor else "core", "weight": weight, "appears": appears,
            "voice": self.rng.choice(VOICES),
            "surface_forms": [] if minor else person_surface_forms(
                f, last, email, handle, nickname=nick, role_phrase=phrase),
        }
        self.people.append(person)
        return person

    def _cast(self) -> None:
        st, rng = self.st, self.rng
        # Collision and homophone plans: first names reused deliberately across orgs.
        pool = [n for n in self._collision_firsts()]
        coll_a, coll_b = pool[0], pool[1]
        homo = rng.choice(HOMOPHONE_PAIRS)
        for n in (coll_a, coll_b, *homo):
            self.names.reserve_first(n)

        c = self.central
        self.worker = self._person(c, rng.choice(st.worker_titles), "peer", "central", weight=0)
        self.worker["voice"] = "terse"
        self.worker["relationship"] = None
        r = st.roles
        self.role_people: dict[str, dict] = {}
        self.role_people["manager"] = self._person(c, r["manager"][0], "manager", "central", phrase=r["manager"][1], weight=2.0)
        self.role_people["collab"] = self._person(c, r["collab"][0], "peer", "central", phrase=r["collab"][1], weight=7.0,
                                                  first=coll_a)
        self.role_people["eng"] = self._person(c, r["eng"][0], "peer", "central", phrase=r["eng"][1], weight=2.6)
        self.role_people["eng2"] = self._person(c, r["eng2"][0], "stakeholder", "central", phrase=r["eng2"][1], weight=1.2)
        self.role_people["sec"] = self._person(c, r["sec"][0], "peer", "central", phrase=r["sec"][1], weight=2.4)
        self.role_people["product"] = self._person(c, r["product"][0], "peer", "central", phrase=r["product"][1], weight=1.2)
        self.role_people["ea"] = self._person(c, r["ea"][0], "assistant", "central", phrase=r["ea"][1], weight=0.8)
        if self.size != "small":
            self.role_people["analyst"] = self._person(c, r["analyst"][0], "peer", "central", phrase=r["analyst"][1], weight=1.0,
                                                       first=homo[0])
        mailbox_name = f"{c['short']} Shared Inbox"
        mb = {
            "id": "p-" + ascii_slug(mailbox_name), "name": mailbox_name, "first": f"{c['short']} Team",
            "last": "Mailbox", "nickname": None, "org": c["id"], "role": "Shared team mailbox",
            "role_phrase": f"the {c['short']} inbox", "email": f"{ascii_slug(c['short'])}-team@{c['domain']}",
            "handle": "@" + ascii_slug(c["short"]) + "-team", "relationship": "other", "group": "mailbox",
            "tier": "core", "weight": 0.3, "appears": None, "voice": "formal",
            "surface_forms": [f"{c['short']} Team", f"the {c['short']} inbox", f"{ascii_slug(c['short'])}-team@{c['domain']}"],
        }
        self.people.append(mb)
        self.role_people["mailbox"] = mb
        u = self.umbrella
        for key, rel in (("proc", "stakeholder"), ("legal", "stakeholder"), ("fin", "stakeholder"),
                         ("hr", "stakeholder"), ("privacy", "stakeholder")):
            self.role_people[key] = self._person(u, r[key][0], rel, "functional", phrase=r[key][1], weight=0.9)

        # Units: a head (executive), an operational lead and staff.
        self.unit_people: dict[str, dict[str, Any]] = {}
        lead_titles = list(st.unit_lead_titles)
        rng.shuffle(lead_titles)
        staff_titles = list(st.unit_staff_titles)
        homo_b_used = False
        for i, unit in enumerate(self.units):
            head = self._person(unit, f"{st.unit_head[0]}, {unit['name']}", "executive", "unit",
                                phrase=f"{unit['short']}'s {st.unit_head[1]}", weight=0.7)
            lead = self._person(unit, f"{lead_titles[i % len(lead_titles)]}, {unit['name']}", "stakeholder", "unit",
                                phrase=f"the {unit['short']} lead", weight=2.4 if i == 0 else 1.3,
                                first=coll_b if i == 1 else None)
            staff = []
            titles = rng.sample(staff_titles, rng.randint(*self.sz["unit_staff"]))
            for title in titles:
                first = None
                if not homo_b_used and i >= 1:
                    first, homo_b_used = homo[1], True
                staff.append(self._person(unit, f"{title}, {unit['name']}", "stakeholder", "unit", weight=1.0, first=first))
            self.unit_people[unit["id"]] = {"head": head, "lead": lead, "staff": staff}

        # Vendors: an account executive and a solutions engineer each.
        self.vendor_people: dict[str, dict[str, dict]] = {}
        for k, v in enumerate(self.vendors):
            ae = self._person(v, f"Account Executive, {v['name']}", "vendor", "vendor", weight=1.1,
                              first=coll_a if k == 0 else None)
            se = self._person(v, f"Solutions Engineer, {v['name']}", "vendor", "vendor", weight=0.9,
                              first=coll_b if k == 1 else None)
            self.vendor_people[v["id"]] = {"ae": ae, "se": se}
        if not homo_b_used:
            v0 = self.vendors[0]
            self.vendor_people[v0["id"]]["csm"] = self._person(
                v0, f"Customer Success Manager, {v0['name']}", "vendor", "vendor", first=homo[1])
        if "analyst" not in self.role_people:
            self.role_people["analyst"] = self._person(c, r["analyst"][0], "peer", "central", phrase=r["analyst"][1],
                                                       weight=1.0, first=homo[0])
        self.partner_people = [
            self._person(p, f"Senior Research Scientist, {p['name']}", "partner", "partner", weight=0.8)
            for p in self.partners
        ]
        self.candidate = self._person(None, "Candidate", "candidate", "candidate", weight=0.6)
        self.collisions = {
            "first_names": [
                [p["id"] for p in self.people if p["first"] == coll_a],
                [p["id"] for p in self.people if p["first"] == coll_b],
            ],
            "homophones": [next(p["id"] for p in self.people if p["first"] == homo[0]),
                           next(p["id"] for p in self.people if p["first"] == homo[1])],
        }
        # One newcomer per episode week (dates are filled in by the challenge schedule).
        self.newcomers = []
        newcomer_roles = [
            (lambda: self.units[0], "Privacy Officer", "stakeholder", "the new privacy officer"),
            (lambda: self.vendors[0], "Senior Account Executive", "vendor", None),
            (lambda: self.central, "Data Engineer (contract)", "stakeholder", "the new contractor"),
            (lambda: self.units[-1], "Operations Analyst", "stakeholder", None),
        ]
        for w in range(self.weeks):
            org_fn, title, rel, phrase = newcomer_roles[w % len(newcomer_roles)]
            org = org_fn()
            p = self._person(org, f"{title}, {org['name']}" if org["role"] != "central" else title, rel,
                             "newcomer", phrase=phrase, weight=1.4, appears="TBD")
            self.newcomers.append(p)
        # Minor senders: newsletters and automated notifications.
        self._minors()

    def _collision_firsts(self) -> list[str]:
        from wcb.world.names import FIRST_NAMES

        cands = [n for n in FIRST_NAMES if n not in NICKNAMES and len(n) <= 7]
        self.rng.shuffle(cands)
        return cands[:2]

    def _minors(self) -> None:
        st, u = self.st, self.umbrella
        specs = [
            ("newsletter", f"Editor, {self.rng.choice(st.newsletters)}", None),
            ("service_desk", f"{u['short']} IT Service Desk", "bot"),
            ("status", "Platform Status Page", "bot"),
            ("comms", f"{u['short']} Internal Communications", "bot"),
            ("events", "Events Coordinator", None),
            ("conference", "Conference Organizer", None),
            ("benefits", "Benefits Enrollment Notices", "bot"),
            ("marketing", f"Marketing, {self.vendors[-1]['name']}", None),
        ][: self.sz["minor"]]
        for key, title, bot in specs:
            if bot:
                name = title
                pid = "p-" + ascii_slug(name)
                local = {"service_desk": "servicedesk-noreply", "status": "status-noreply", "comms": "news",
                         "benefits": "benefits-noreply"}[key]
                email = f"{local}@{u['domain']}"
                person = {"id": pid, "name": name, "first": name, "last": "", "nickname": None, "org": None,
                          "role": title, "role_phrase": None, "email": email, "handle": None,
                          "relationship": None, "group": "minor", "tier": "minor", "weight": 0.0,
                          "appears": None, "voice": "formal", "surface_forms": [email], "minor_kind": key}
                self.people.append(person)
            else:
                p = self._person(None, title, "other", "minor", minor=True)
                p["minor_kind"] = key
                p["relationship"] = None
                dom = {"newsletter": "newsletters.example", "events": u["domain"], "conference": "conference.example",
                       "marketing": self.vendors[-1]["domain"]}[key]
                p["email"] = f"{email_local(p['first'], p['last'])}@{dom}"
                p["surface_forms"] = [p["email"]]
                p["weight"] = 0.0

    # ------------------------------------------------------------ portfolio
    def _topic(self) -> tuple[str, str]:
        opts = [t for t in self.st.topics if t[0] not in self.used_topics] or list(self.st.topics)
        t = self.rng.choice(opts)
        self.used_topics.add(t[0])
        return t

    def _portfolio(self) -> None:
        rng, sz = self.rng, self.sz
        lo, hi = sz["projects"]
        n_total = rng.randint(lo, hi)
        n_place = 1 if self.size == "small" or self.weeks <= 2 else 2
        n_dorm = rng.randint(*sz["dormant"])
        n_small = rng.randint(*sz["smalls"])
        n_mid = min(max(sz["mids"][0], n_total - 2 - n_place - n_dorm - n_small), sz["mids"][1])
        while 2 + n_mid + n_small + n_place + n_dorm > hi and n_small > 0:
            n_small -= 1
        while 2 + n_mid + n_small + n_place + n_dorm > hi and n_dorm > 1:
            n_dorm -= 1
        while 2 + n_mid + n_small + n_place + n_dorm < lo:
            n_mid += 1
        mids = ["vendor_pair_evaluation", "pivoting_discovery"]
        others = [a for a in A.MID_ARCHETYPES if a not in mids]
        rng.shuffle(others)
        mids = (mids + others)[:n_mid]
        while len(mids) < n_mid:
            mids.append(rng.choice(A.MID_ARCHETYPES))
        smalls = list(A.SMALL_ARCHETYPES)
        rng.shuffle(smalls)
        smalls = smalls[:n_small]
        dorm = [A.DORMANT_ARCHETYPES[i % 2] for i in range(n_dorm)]

        seed_start = self.cal["seed"]["start"]
        flagship_unit = self.units[0]
        self.hub = self._project("platform_hub", "hub", None)
        self.flagship = self._project("flagship_pilot", "flagship", flagship_unit)
        self.projects.reverse()  # flagship first
        for a in mids:
            self._project(a, "mid", self._unit_for(a))
        for a in smalls:
            self._project(a, "small", self._unit_for(a))
        for _ in range(n_place):
            self._project("placeholder", "placeholder", self.units[-1 if len(self.projects) % 2 else 1])
        for a in dorm:
            self._project(a, "dormant", self._unit_for(a))
        for p in self.projects:
            p["start"] = seed_start
        # Heavy-tailed weights: flagship ~35% of loops, top two ~50%.
        base = {"flagship": 34.0, "hub": 14.0, "mid": 7.0, "small": 2.5, "placeholder": 0.15, "dormant": 0.6}
        for p in self.projects:
            p["weight"] = round(base[p["size"]] * rng.uniform(0.75, 1.25), 2)

    def _unit_for(self, archetype: str) -> dict:
        weights = {"high": 3, "medium": 2, "low": 1}
        units = self.units
        return self.rng.choices(units, weights=[weights[u["receptiveness"]] for u in units])[0]

    def _project(self, archetype: str, size: str, unit: dict | None) -> dict:
        rng, st = self.rng, self.st
        arch = A.get(archetype)
        rp = self.role_people
        unit = unit or self.units[0]
        up = self.unit_people[unit["id"]]
        if archetype in TOPIC_ARCHETYPES:
            topic, topic_a = self._topic()
        else:
            topic, topic_a = FIXED_TOPICS.get(archetype, "AI adoption"), ""
        hub = getattr(self, "hub", None)
        hub_short = hub["short"] if hub else ""
        vendors = rng.sample(self.vendors, min(2, len(self.vendors)))
        partner = self.partners[0] if self.partners else None
        code = None
        name = short = kw = ""
        forms: list[str] = []
        role = ""
        if archetype in ("flagship_pilot", "platform_hub", "internal_incubation"):
            code = self.names.code_word()
            name = short = code
            kw = code.lower()
            if archetype == "flagship_pilot":
                forms = [f"Project {code}", f"the {topic} pilot", f"the {unit['short']} pilot", code.upper()[:3] + "P"]
            elif archetype == "platform_hub":
                forms = ["the platform", "the common platform", f"{code} platform", f"the {st.vocab['platform']}"]
            else:
                forms = [f"Project {code}", f"the {topic} prototype"]
        elif archetype == "vendor_pair_evaluation":
            name, short = f"{_title(topic)} Tool Selection", f"{topic} selection"
            kw = short
            forms = [f"the {topic} bake-off", f"the {vendors[0]['short']}/{vendors[-1]['short']} evaluation", _acronym(name) + " selection"]
        elif archetype in ("unit_discovery", "pivoting_discovery"):
            name, short = f"{unit['short']} {_title(topic)} Discovery", f"{topic} discovery"
            kw = short
            forms = [f"the {unit['short']} discovery", f"the {topic} work", _acronym(name) + " discovery"]
        elif archetype == "economics_model":
            name, short, kw = f"{hub_short} Funding Model", "funding model", "funding model"
            forms = ["the recharge model", "the funding options", f"{hub_short} recharge"]
        elif archetype == "strategic_framework":
            name, short, kw = f"{self.umbrella['short']} Responsible AI Use Framework", st.framework, st.framework.lower()
            forms = ["the AI framework", "the framework", "the responsible-use framework"]
        elif archetype == "hiring_pipeline":
            role = topic = rng.choice(st.hire_roles)
            name, short, kw = f"{_title(role)} Hire", role, role
            forms = [f"the {role} search", f"REQ-{rng.randint(2100, 4899)}", f"the {_acronym(role)} hire"]
        elif archetype == "event_preparation":
            et = topic = rng.choice(st.event_topics)
            name, short = f"{_title(et)} Workshop", f"{et} workshop"
            kw = short
            forms = ["the workshop", f"the {unit['short']} workshop", f"the {et} session"]
        elif archetype == "supplier_negotiation":
            v = vendors[0]
            name, short, kw = f"{v['short']} Enterprise Agreement", f"{v['short']} enterprise agreement", f"{v['short'].lower()} enterprise"
            forms = [f"the {v['short']} deal", f"the {v['short']} renewal"]
        elif archetype == "background_advisory":
            name, short = f"{_title(topic)} Advisory", f"{topic} advisory"
            kw = short
            forms = [f"the {topic} advice", f"{unit['short']} {topic} advisory"]
        elif archetype == "peer_review":
            name, short, kw = f"{hub_short} Operating Model Review", f"{hub_short} operating model", "operating model"
            forms = ["the operating model review", "the ops model draft", f"the {hub_short} operating model"]
        elif archetype == "relationship_thread":
            ps = partner["short"] if partner else unit["short"]
            name, short, kw = f"{ps} Partnership", f"{ps} partnership", f"{ps.lower()} partnership"
            forms = [f"the {ps} relationship", f"{ps}"]
        elif archetype == "delegated_asks":
            name, short = f"{_title(topic)} Input Round", f"{topic} input round"
            kw = short
            forms = [f"the {topic} input", f"the {topic} round"]
        elif archetype == "education_programme":
            name, short = f"{_title(topic)} Learning Series", f"{topic} series"
            kw = short
            forms = ["the learning series", f"the {topic} talks"]
        elif archetype == "placeholder":
            name, short, kw = f"{_title(topic)} (placeholder)", topic, topic
            forms = [f"{up['lead']['first']}'s {topic} idea", f"the {topic} placeholder"]
        elif archetype == "stalled_discovery":
            v = vendors[0]
            name, short = f"{v['short']} {_title(topic)} Diligence", f"{v['short']} diligence"
            kw = short.lower()
            forms = [f"the {v['short']} deep dive", f"the {topic} diligence"]
        else:  # pragma: no cover - every archetype is handled above
            raise ValueError(archetype)
        pid = "pr-" + ascii_slug(name)
        while any(p["id"] == pid for p in self.projects):
            pid += "-2"
        # Cast: who fills each role on this project.
        owner = {
            "flagship_pilot": up["lead"], "platform_hub": rp["eng"], "peer_review": rp["eng"],
            "event_preparation": rp["collab"], "economics_model": self.worker, "strategic_framework": self.worker,
            "hiring_pipeline": self.worker, "placeholder": up["lead"], "supplier_negotiation": rp["proc"],
            "relationship_thread": self.worker, "delegated_asks": self.worker, "education_programme": rp["collab"],
            "internal_incubation": self.worker, "background_advisory": up["lead"], "stalled_discovery": self.worker,
        }.get(archetype, self.worker if rng.random() < 0.6 else up["lead"])
        sponsor = up["head"] if archetype in ("flagship_pilot", "unit_discovery", "pivoting_discovery",
                                              "vendor_pair_evaluation") and rng.random() < 0.4 else rp["manager"]
        vend_people = [self.vendor_people[v["id"]] for v in vendors]
        cast = {
            "owner": owner["id"], "sponsor": sponsor["id"], "lead": up["lead"]["id"],
            "unit": [p["id"] for p in up["staff"]] + [up["lead"]["id"]],
            "ae": [vp["ae"]["id"] for vp in vend_people], "se": [vp["se"]["id"] for vp in vend_people],
            "eng": rp["eng"]["id"] if archetype != "platform_hub" else rp["eng2"]["id"],
            "sec": rp["sec"]["id"], "privacy": rp["privacy"]["id"], "legal": rp["legal"]["id"],
            "proc": rp["proc"]["id"], "fin": rp["fin"]["id"], "hr": rp["hr"]["id"], "ea": rp["ea"]["id"],
            "collab": rp["collab"]["id"], "partner": self.partner_people[0]["id"] if self.partner_people else rp["collab"]["id"],
            "cand": self.candidate["id"],
        }
        members = [self.worker["id"], owner["id"]]
        core = [rp["collab"]["id"], up["lead"]["id"], *cast["unit"]]
        if archetype in ("flagship_pilot",):
            core += [rp["eng"]["id"], rp["sec"]["id"], rp["eng2"]["id"], rp["product"]["id"], up["head"]["id"]]
        elif archetype == "platform_hub":
            core += [rp["eng2"]["id"], rp["sec"]["id"]]
        elif archetype in ("vendor_pair_evaluation", "supplier_negotiation", "stalled_discovery"):
            core += cast["ae"][:1] + [rp["proc"]["id"]]
        elif archetype == "economics_model":
            core += [rp["fin"]["id"], rp["eng"]["id"]]
        elif archetype == "hiring_pipeline":
            core = [rp["hr"]["id"], rp["eng"]["id"]]
        cap = {"flagship": 12, "hub": 7, "mid": 6, "small": 4, "placeholder": 3, "dormant": 3}[size]
        for m in core:
            if m not in members and len(members) < cap:
                members.append(m)
        orgs = [unit["id"]] if archetype not in ("platform_hub", "hiring_pipeline", "strategic_framework") else []
        if archetype in ("vendor_pair_evaluation", "supplier_negotiation", "stalled_discovery"):
            orgs += [v["id"] for v in vendors]
        if archetype in ("relationship_thread", "education_programme") and partner:
            orgs.append(partner["id"])
        phase = rng.choice(arch.start)
        target = None
        if archetype in ("flagship_pilot", "vendor_pair_evaluation", "unit_discovery", "pivoting_discovery",
                         "event_preparation", "economics_model", "strategic_framework", "internal_incubation",
                         "supplier_negotiation"):
            target = add_days(self.start, 7 * self.weeks + rng.randint(4, 30))
            while parse_date(target).weekday() >= 5:
                target = add_days(target, 1)
        status = arch.phase(phase).status
        n = rng.choice([3, 4, 5]) if archetype == "flagship_pilot" else 2
        proj = {
            "id": pid, "name": name, "short": short, "kw": kw.lower(), "code": code,
            "surface_forms": _dedup([f for f in forms if f and f != name]),
            "archetype": archetype, "size": size, "topic": topic, "topic_a": topic_a,
            "pivot": rng.choice(st.pivots), "role": role,
            "unit": unit["id"], "vendors": [v["id"] for v in vendors], "partner": partner["id"] if partner else None,
            "owner": owner["id"], "sponsor": sponsor["id"], "members": members, "orgs": orgs,
            "status": status, "phase": phase, "target_date": target, "n": n,
            "cast": cast, "weight": 1.0, "start": None,
        }
        self.projects.append(proj)
        return proj

    # ------------------------------------------------------------ cadences
    def _cadences(self) -> list[dict]:
        rp = self.role_people
        fl = self.flagship
        unit_leads = [self.unit_people[u["id"]]["lead"]["id"] for u in self.units]
        central_team = [rp[k]["id"] for k in ("collab", "eng", "sec", "product", "manager")]
        return [
            {"key": "standup", "title": f"{fl['short']} standup", "kind": "meeting", "project": fl["id"],
             "weekdays": [0, 1, 2, 3, 4], "every": 1, "time": "09:30", "minutes": 25,
             "organizer": fl["cast"]["lead"], "attendees": fl["members"][:8]},
            {"key": "leads", "title": f"{self.central['short']} leads call", "kind": "meeting", "project": None,
             "weekdays": [0], "every": 1, "time": "11:00", "minutes": 45,
             "organizer": rp["manager"]["id"], "attendees": [self.worker["id"], *central_team]},
            {"key": "hub_sync", "title": f"{self.hub['short']} platform sync", "kind": "meeting", "project": self.hub["id"],
             "weekdays": [2], "every": 1, "time": "14:00", "minutes": 30,
             "organizer": rp["eng"]["id"], "attendees": self.hub["members"][:6]},
            {"key": "one_on_one", "title": f"1:1 {self.worker['first']} / {rp['collab']['first']}", "kind": "meeting",
             "project": None, "weekdays": [1], "every": 2, "time": "15:00", "minutes": 30,
             "organizer": rp["collab"]["id"], "attendees": [self.worker["id"], rp["collab"]["id"]]},
            {"key": "forum", "title": f"Cross-{self.st.unit_word} AI forum", "kind": "meeting", "project": None,
             "weekdays": [3], "every": 2, "time": "13:00", "minutes": 60,
             "organizer": rp["collab"]["id"], "attendees": [self.worker["id"], rp["collab"]["id"], *unit_leads]},
            {"key": "weekly_update", "title": "Weekly update", "kind": "obligation", "project": None,
             "weekdays": [0, 4], "every": 1, "organizer": rp["mailbox"]["id"],
             "attendees": [self.worker["id"], rp["manager"]["id"]]},
        ]

    # ------------------------------------------------------------ challenge schedule
    def _challenges(self) -> list[dict]:
        rng = self.rng
        weeks = self.cal["episode"]["weeks"]
        seed_days = [d for d in self.cal["seed"]["days"] if parse_date(d).weekday() < 5]
        by_arch: dict[str, list[dict]] = {}
        for p in self.projects:
            by_arch.setdefault(p["archetype"], []).append(p)
        placeholders = list(by_arch.get("placeholder", []))
        splittable = [p for p in self.projects if p["archetype"] in ("pivoting_discovery", "strategic_framework")]
        mids = [p for p in self.projects if p["size"] in ("mid", "flagship")]
        dated = [p for p in self.projects if p["target_date"] and p["size"] in ("flagship", "mid")]
        out: list[dict] = []

        def day(days: list[str], idx: list[int]) -> str:
            ok = [days[i] for i in idx if i < len(days)]
            return rng.choice(ok) if ok else days[-1]

        for w, days in enumerate(weeks, 1):
            last = len(days) - 1
            prev_days = seed_days[-4:] if w == 1 else weeks[w - 2][:5]

            def add(tag: str, d: str, w: int = w, **kw: Any) -> None:
                out.append({"week": w, "tag": tag, "day": d, **kw})

            add("worker_directive", days[0], project=rng.choice(mids)["id"])
            add("noise", days[0])
            add("implied_commitment", day(days, [0, 1]), project=self.flagship["id"])
            add("duplicate_signal", day(days, [0, 1]), project=rng.choice(mids)["id"])
            add("privacy", day(days, [0, 1, 2, 3]))
            add("alias", day(days, [1, 2]))
            add("name_collision", day(days, [1, 2, 3]))
            nd = day(days, [1, 2])
            newcomer = self.newcomers[w - 1]
            newcomer["appears"] = nd
            add("new_entity", nd, person=newcomer["id"],
                project=(self.flagship if w % 2 else rng.choice(mids))["id"])
            add("supersession", day(days, [1, 2]), project=(self.flagship if w == 1 else rng.choice(dated or mids))["id"])
            add("unobservable", day(days, [1, 2, 3]), project=rng.choice(mids)["id"],
                attribute=["budget", "budget_ceiling", "savings_target", "discount"][(w - 1) % 4])
            add("draft_vs_sent", day(days, [1, 4]), setup=days[0])
            add("batch_catchup", day(days, [1, 2]))
            add("transfer", day(days, [2, 3]))
            add("correction", day(days, [2, 3]), setup=days[1])
            add("weak_evidence", day(days, [2, 3]), setup=days[0])
            add("acceptance_vs_occurrence", day(days, [3, 4]))
            if w % 2 == 1 and splittable:
                add("restructuring", day(days, [3, 4]), mode="split", project=splittable.pop(0)["id"])
            elif placeholders:
                ph = placeholders.pop(0)
                target = next((p for p in self.projects if p["unit"] == ph["unit"] and p["size"] in ("mid", "flagship")),
                              self.flagship)
                add("restructuring", day(days, [3, 4]), mode="merge", project=ph["id"], into=target["id"])
            else:
                add("restructuring", day(days, [3, 4]), mode="split", project=self.flagship["id"])
            add("version_mismatch", days[3], setup=days[0])
            add("silent_closure", day(days, [3, 4]), setup=day(days, [0, 1]))
            rev_proj = self.flagship if w == 1 else rng.choice(mids)
            add("reversal", day(days, [3, 4]), setup=rng.choice(prev_days), project=rev_proj["id"])
            add("endorsement", day(days, [4, 5]) if last >= 4 else days[last], setup=day(days, [0, 1]))
            add("scattered_evidence", days[min(3, last)], setup=days[0], steps=[days[1], days[2], days[min(3, last)]])
        return out


# ---------------------------------------------------------------- helpers
def _dedup(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x and x not in out:
            out.append(x)
    return out


def _title(s: str) -> str:
    small = {"and", "of", "for", "in", "the", "a", "an", "to", "on"}
    words = s.split()
    return " ".join(w if (i and w in small) or w[:1].isupper() else w[:1].upper() + w[1:] for i, w in enumerate(words))


def _acronym(s: str) -> str:
    words = [w for w in s.replace("-", " ").split() if w[:1].isalpha() and w.lower() not in ("of", "and", "the", "for")]
    return "".join(w[0].upper() for w in words)
