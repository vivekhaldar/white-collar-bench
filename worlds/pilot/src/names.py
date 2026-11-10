"""Short handles for entity IDs used across the day files."""

from dsl import PEOPLE

M = "p-mara-ilves"
SADE = "p-folasade-renwick"
LUCIA = "p-lucia-ferreyra"
RAMONA = "p-ramona-szabo"
ILYA = "p-ilya-marchetti"
HW = "p-hyunwoo-park"
BETT = "p-bettina-oduya"
BARTOSZ = "p-bartosz-zielke"
SOL = "p-marisol-etxeberria"
CLEM = "p-clement-oyelaran"
AGA = "p-agnieszka-wolanin"
PERCY = "p-percival-ndiaye"
MBOX = "p-ods-mailbox"
BART = "p-bart-ngata"
YUSRA = "p-yusra-haddad"
JACK = "p-joaquin-sepulveda"
DIMA = "p-dmitri-halloran"
SAANVI = "p-saanvi-raghunathan"
TEO = "p-teodor-lisowski"
GRETA = "p-greta-voss"
EMEKA = "p-emeka-nwosu-hart"
CONNIE = "p-constance-wilberforce"
INGRID = "p-ingrid-solberg"
HANA = "p-hana-kobayashi-reyes"
DELPH = "p-delphine-arceneaux"
LIONEL = "p-lionel-mbatha"
TILLIE = "p-ottilie-brandvold"
RUFUS = "p-rufus-adekunle"
CORWIN = "p-corwin-bellamy-tate"
EZINNE = "p-ezinne-marlowe-abara"
NIALL = "p-niall-fairbrother"
RAMI = "p-ramona-iturbe"
GREG = "p-gregor-lindahl"
HANNAH = "p-hannah-feld"
JUNI = "p-juniper-hale"
CALLUM = "p-callum-ferris"
XIM = "p-ximena-robles"
INES = "p-ines-vardakis"
MATEUS = "p-mateus-okonedo"

LAN, HUB, WFT, TCE, ADV = "pr-tinderbox", "pr-kettleyard", "pr-wft", "pr-transfer-eval", "pr-advising-sched"
WS, COP, CB, HIRE, LIB, CITE = "pr-workshop", "pr-cop", "pr-chargeback", "pr-mle-hire", "pr-library-ra", "pr-citation-helper"


def a(*pids: str) -> list[str]:
    """Render people as 'Name <email>' for artifact briefs."""
    out = []
    for p in pids:
        if p.startswith("p-"):
            info = PEOPLE[p]
            out.append(f"{info['name']} <{info['email']}>" if info.get("email") else info["name"])
        else:
            out.append(p)
    return out


def n(*pids: str) -> list[str]:
    return [PEOPLE[p]["name"] if p.startswith("p-") else p for p in pids]
