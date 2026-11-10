"""Synthetic names for generated worlds (docs/generator.md, "Planner: Names").

Everything here is invented or generic. People are drawn from large first-name and surname
pools spanning many cultures and paired at random; organizations, products and project code
names are coined from syllable tables and short word lists. Every generated string is checked
against ``AVOID_TOKENS`` and ``FAMOUS_FULL_NAMES``:

- ``AVOID_TOKENS``: names used by the hand-authored pilot world, the test fixtures and the
  examples in the docs, plus a few famous or real-company names. Generated names may not use
  them as whole tokens, so generated worlds stay distinct from the pilot.

Nothing here may name what a private source repository contains, so terms found by privacy
reviews are removed rather than listed: the name pools are pruned with
``scripts/check_name_pools.py`` (docs/privacy.md), and released worlds are scanned with
``wcb privacy scan``. All randomness comes from the ``random.Random`` instance passed
in, so the same seed always produces the same names.
"""

from __future__ import annotations

import random
import re
import unicodedata

# ---------------------------------------------------------------- denylists
# Whole-token matches, case-insensitive: the pilot cast and orgs, fixture and doc examples,
# and a handful of real companies, products and famous names that coinage could hit.
AVOID_TOKENS: frozenset[str] = frozenset(
    """
    mara ilves folasade sade renwick lucia lucy ferreyra ramona mona szabo ilya marchetti
    hyun-woo hyunwoo harry park bettina tina oduya bartosz bart marisol sol etxeberria clement
    clem oyelaran agnieszka aga wolanin percival percy ndiaye bartholomew ngata yusra haddad
    joaquin jack sepulveda dmitri dima halloran saanvi raghunathan teodor teo lisowski lisofsky
    margarethe greta voss emeka nwosu-hart nwosu constance connie wilberforce ingrid solberg hana
    hannah kobayashi-reyes delphine arceneaux lionel mbatha ottilie tillie brandvold rufus
    adekunle niall fairbrother iturbe gregor greg lindahl feld juniper juni hale callum ferris
    ximena robles ines vardakis mateus matt okonedo lorne castellan wendell beatriz solano
    tarrow kestrow saltmarren orrin brackwater scrivelo penmarq draftcoach eskerfield
    huddlescribe talentlink lattice switchyard corwin ezinne kettleyard bellamy tate marlowe abara
    tarrowrecruit
    ada quist ben okoro sam samir patel reyes cora velez nina hart larchmont tessellate quillon
    freightwire imogen tran corvane rowan achterberg malik osei hollis baptiste teague
    thistledown harbor marisol
    google amazon apple microsoft meta oracle salesforce workday canvas blackboard moodle zoom
    slack okta adobe siemens philips intel nvidia openai anthropic claude gemini kaiser mayo
    optum cigna aetna humana tesla toyota bosch honeywell tableau snowflake databricks palantir
    accenture deloitte infosys wipro cisco vmware zendesk twilio stripe shopify hubspot asana
    notion figma atlassian github gitlab docusign dropbox epic cerner
    quinix equinix arent saffron heron veritas nutanix calix fenix onix lumen medix salix
    """.split()
)


# Full names that the pools can produce and that belong to well-known people (actors, athletes,
# writers, politicians, film characters). Checked as whole names, case- and accent-insensitive.
FAMOUS_FULL_NAMES: frozenset[str] = frozenset(
    """
    arjun reddy|kiran desai|sanjay gupta|deepa mehta|paolo rossi|diego costa|divya dutta|raymond chen|kiran rao
    nandini reddy|venkatesh iyer|harish rao|lakshmi menon|rohan joshi|gaurav gupta|matteo ricci|christopher lloyd
    malcolm fraser|daniel levy|gideon levy|michael rosen|robert shapiro|astrid lindgren|armen sargsyan
    tigran petrosyan|cem yilmaz|burak yilmaz|emre aydin|naoko takahashi|zainab balogun|francesca rossi
    valentina vargas|lorenzo lombardi|caio ribeiro|marcelo rocha|thiago costa|rafael costa|diego rivera
    paula navarro|daniela romo|wei zhang|jun wang|yan zhang|haruto sato|kenji watanabe|daniel kang|elif sahin
    michael douglas|robert fraser|douglas fraser|william lloyd|stanley kubrick|leonard cohen|siobhan byrne
    timothy spall|rebecca hall|elizabeth holmes|jennifer doyle|lars andersen|henrik lund|yuki tanaka
    """.replace("\n", "|").split("|")
) - {""}


def is_famous(full_name: str) -> bool:
    """True if a generated full name belongs to a well-known person."""
    return " ".join(_fold(full_name).split()) in {" ".join(n.split()) for n in FAMOUS_FULL_NAMES}


def _fold(s: str) -> str:
    """Lowercase ASCII fold: 'Zoë' -> 'zoe'."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii").lower()


def is_denied(text: str) -> bool:
    """True if `text` uses an avoided name as a token."""
    low = _fold(text)
    toks = set(re.findall(r"[a-z]+(?:-[a-z]+)*", low))
    toks |= {p for t in list(toks) for p in t.split("-")}
    return bool(toks & AVOID_TOKENS)


def _clean(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        if x and not is_denied(x) and x not in out:
            out.append(x)
    return out


# ---------------------------------------------------------------- people
_FIRST_RAW = """
Adaeze Chidi Kwame Ama Kofi Yaw Efua Abena Nnamdi Ifeoma Tunde Bisi Segun Funmilayo Uche Chiamaka
Obinna Adwoa Kojo Esi Akosua Femi Zainab Ngozi Babajide Temitope Oluwaseun Adebayo Ebun Kayode
Wanjiru Njeri Kamau Otieno Achieng Amani Baraka Zawadi Thandiwe Sipho Lindiwe Themba Nomvula Tendai
Rudo Kagiso Lerato Thabo Mpho Layla Omar Karim Rania Tariq Nadia Hassan Faris Salma Dina Yasmin
Rami Ziad Leila Amira Bilal Hiba Khalil Nour Imran Arash Parisa Darius Shirin Kian Roya Emre Elif
Deniz Burak Selin Cem Aylin Aarav Ananya Rohan Vikram Meera Kavya Nikhil Divya Ishaan Lakshmi Rahul
Sneha Tanvi Venkatesh Deepa Harish Ayesha Sanjay Pooja Kiran Gaurav Nandini Rekha Suresh Tahmina
Rafiq Mei Wei Jun Xiaoling Hao Yan Jia Haruto Yuki Sakura Kenji Aiko Takeshi Naoko Minji Jisoo
Dong-hyun Eun-ji Hyejin Ji-ho Tuan Minh Quang Thao Bao Anh Maricel Joselito Dalisay Bayani Ligaya
Siti Putri Agus Dewi Wayan Ratna Somchai Kanya Alejandro Valentina Mateo Camila Santiago Isabela
Daniela Diego Paula Andres Mariana Rodrigo Catalina Emilio Renata Thiago Leticia Guadalupe
Esperanza Rafael Ignacio Soledad Fernanda Tomas Luz Marcelo Joana Caio Bruna Vitoria Anouk Bram
Femke Joris Lotte Sander Ingeborg Henrik Astrid Sigrid Lars Freja Mikkel Elin Johan Aino Eero Tuuli
Pekka Liisa Katarzyna Tomasz Magdalena Pawel Zuzana Ondrej Milena Bogdan Ileana Andrei Sorina
Nikolai Anastasia Svetlana Oksana Taras Yaroslav Dragan Jelena Marko Ivana Goran Petra Ilse Jurgen
Friederike Matthias Annika Lukas Theresa Francesca Giulia Lorenzo Chiara Matteo Alessia Paolo
Federica Stefano Elena Aurelie Mathieu Celine Bastien Margaux Thibault Solene Yannick Elodie
Siobhan Ciaran Aoife Eoin Niamh Declan Saoirse Rhys Bronwen Gethin Carys Ewan Morag Fiona Alasdair
Hamish Isla Theodora Eleni Yiannis Stavros Katerina Nikos Despina Patricia Elizabeth Jonathan
Nathaniel Abigail Alexander Victoria Deborah Douglas Kenneth Eleanor Frederick Rosalind Tobias
Winifred Cassandra Dominic Gwendolyn Leonard Madeline Penelope Reginald Stanley Timothy Vanessa
Tyrone Darnell Keisha Shanice Malcolm Imani Jalen Aaliyah Desmond Cedric Aroha Tane Mere Wiremu
Kalani Leilani Malia Sione Losa Tevita Noa Yael Eitan Tamar Avi Shira Ronit Gideon Anahit Armen
Nare Tigran Lilit Giorgi Aigerim Nurlan Bolat Batbayar Saraa Phoebe Quentin Marguerite Corinne
Ottavio Benedikt Halima Mariam Yusuf Idris
"""

_SURNAME_RAW = """
Adeyemi Mensah Asante Boateng Owusu Nwachukwu Eze Obi Balogun Adewale Danjuma Ogunleye Ibekwe Amadi
Oduro Agyeman Appiah Quaye Tetteh Darko Ansah Afolabi Olawale Bankole Ekwueme Nnaji Chukwu Kariuki
Mwangi Njoroge Ochieng Wekesa Mutua Kiprono Chebet Nyambura Dlamini Ndlovu Khumalo Mokoena Sithole
Moyo Banda Phiri Tembo Mutasa Chikwanha Nkosi Molefe Khoury Saleh Farah Mansour Aziz Hamdan Qureshi
Rahimi Sabbagh Tahan El-Amin Bishara Haidari Jaber Kassem Malouf Najjar Rashed Shami Toubia Yassin
Ahmadi Karimi Moradi Tehrani Rostami Jafari Sadeghi Yilmaz Demir Aydin Kaya Sahin Ozturk Arslan
Korkmaz Erdem Kocak Raghavan Menon Pillai Krishnan Subramanian Chatterjee Banerjee Mukherjee
Sengupta Mehta Kulkarni Deshpande Agarwal Malhotra Bhatt Chaudhry Siddiqui Hossain Karunaratne
Perera Wickramasinghe Thapa Gurung Shrestha Naidu Venkataraman Bose Nakamura Takahashi Watanabe
Yamamoto Fujita Ishikawa Matsuda Hayashi Morimoto Tanaka Okada Choi Jeong Yoon Kang Baek Hwang Liu
Chen Zhou Xu Guo Luo Feng Deng Pham Vu Dang Ngo Duong Santos Bautista Villanueva Mendoza Pangilinan
Salazar Wijaya Santoso Hidayat Kusuma Siregar Suwannarat Chaiyaporn Rattanakorn Herrera Vargas
Navarro Ortega Fuentes Cabrera Paredes Zamora Arroyo Bustamante Cardenas Figueroa Ibarra Jimenez
Lozano Maldonado Montoya Quintero Rosales Sandoval Trujillo Valdez Villalobos Carvalho Oliveira
Ribeiro Almeida Barbosa Cardoso Costa Duarte Monteiro Pereira Rocha Teixeira Moreira Azevedo
Brandao Medeiros Jansen Bakker Visser Smit Meijer Mulder Hendriks Bergstrom Nyberg Holm Sandberg
Eriksen Dahl Lund Haugen Virtanen Korhonen Makinen Laine Nieminen Kowalski Nowak Wisniewska
Zielinski Lewandowska Dvorak Novotny Horvath Kovacs Nagy Popescu Ionescu Dumitru Petrov Ivanova
Sokolov Volkov Kuznetsova Bondarenko Kovalenko Jovanovic Petrovic Nikolic Horvat Babic Schreiber
Hoffmann Krause Neumann Becker Brandt Vogel Hartmann Zimmermann Lehmann Rossi Bianchi Ricci Romano
Colombo Greco Gallo Conti Esposito Moretti Lombardi Mancini Dubois Lefebvre Moreau Laurent Girard
Bonnet Mercier Fontaine Chevalier Garnier Faure Gauthier Byrne Doyle Kavanagh Gallagher Quinlan
MacLeod Fraser Munro Sinclair Galbraith Pritchard Rees Vaughan Penhallow Papadopoulos Georgiou
Nikolaidis Konstantinou Alexiou Whitfield Ashworth Pembroke Calloway Thornbury Merriweather Langley
Hargrove Carmichael Dunmore Everett Fenwick Gilchrist Kingsley Lockhart Northcott Prescott Sherwood
Tolliver Underhill Yardley Ashby Bramwell Cartwright Dempsey Ellery Forsythe Jessup Kimball Lowell
Mayfield Overton Pickering Quimby Rutledge Stanhope Upton Winslow Abernathy Blackwood Darrow Fifita
Taufa Kealoha Kahananui Parata Tapsell Horomona Kalua Ben-David Mizrahi Shapiro Katz Friedman
Peretz Golan Adler Petrosyan Hakobyan Sargsyan Grigoryan Beridze Kapanadze Abenova Nurlanov Batbold
Sato Kowalczyk Andersen Lindgren Halvorsen Okeke Achterhof Vandermeer Oyelami Delacroix Marchand
"""

FIRST_NAMES: list[str] = _clean(_FIRST_RAW.split())
SURNAMES: list[str] = _clean(_SURNAME_RAW.split())

NICKNAMES: dict[str, str] = {
    "Temitope": "Temi",
    "Oluwaseun": "Seun",
    "Funmilayo": "Funmi",
    "Thandiwe": "Thandi",
    "Venkatesh": "Venky",
    "Xiaoling": "Ling",
    "Joselito": "Lito",
    "Valentina": "Vale",
    "Guadalupe": "Lupe",
    "Rafael": "Rafa",
    "Ignacio": "Nacho",
    "Katarzyna": "Kasia",
    "Tomasz": "Tomek",
    "Magdalena": "Magda",
    "Nikolai": "Kolya",
    "Anastasia": "Nastya",
    "Svetlana": "Sveta",
    "Friederike": "Rike",
    "Theresa": "Resi",
    "Francesca": "Fran",
    "Katerina": "Katia",
    "Patricia": "Trish",
    "Elizabeth": "Liz",
    "Abigail": "Abby",
    "Alexander": "Xander",
    "Victoria": "Tori",
    "Douglas": "Doug",
    "Kenneth": "Ken",
    "Eleanor": "Nell",
    "Frederick": "Fred",
    "Rosalind": "Ros",
    "Winifred": "Winnie",
    "Cassandra": "Cass",
    "Gwendolyn": "Gwen",
    "Leonard": "Len",
    "Madeline": "Maddie",
    "Penelope": "Penny",
    "Vanessa": "Nessa",
    "Desmond": "Dez",
    "Wiremu": "Wiri",
    "Babajide": "Jide",
    "Adebayo": "Bayo",
    "Chiamaka": "Amaka",
    "Ifeoma": "Ife",
    "Annika": "Anni",
    "Lorenzo": "Enzo",
    "Federica": "Fede",
    "Yiannis": "Yanni",
    "Wanjiru": "Wanji",
    "Vikram": "Vik",
    "Nikhil": "Nik",
    "Ishaan": "Ish",
    "Benedikt": "Bene",
    "Marguerite": "Margo",
    "Ottavio": "Tavo",
    "Esperanza": "Espe",
    "Leticia": "Leti",
    "Bronwen": "Bron",
    "Gethin": "Geth",
    "Eleni": "Lena",
    "Isabela": "Bela",
    "Santiago": "Santi",
}

# Near-homophones spelled differently (deliberately confusable in transcripts and notes).
HOMOPHONE_PAIRS: list[tuple[str, str]] = [
    ("Aileen", "Eileen"),
    ("Kirsten", "Kristen"),
    ("Mikayla", "Michaela"),
    ("Zara", "Sara"),
    ("Rhea", "Ria"),
    ("Nadia", "Nadya"),
    ("Stephen", "Steven"),
    ("Katrin", "Catrin"),
    ("Lena", "Lina"),
    ("Carly", "Karli"),
    ("Allan", "Alan"),
    ("Teagan", "Tegan"),
    ("Marisa", "Maresa"),
]

# ---------------------------------------------------------------- coinage
_FIRST_SYLL = [
    "Cor", "Dal", "Del", "El", "Fen", "Gal", "Is", "Kel", "Lu", "Mer", "Nor", "Or", "Per",
    "Quin", "Ros", "Sel", "Tor", "Val", "Vel", "Zen", "Bri", "Cle", "Dra", "Fle", "Gri", "Tho",
    "Ves", "Ol", "Am", "En", "Ul", "Tam", "Mar", "Nev", "Pal", "Ren", "Tal", "Vor",
    "Ar", "Bel", "Cyr", "Eth", "Fal", "Hel", "Ith", "Jor", "Kas", "Lin", "Mol", "Ny",
]
_MID_SYLL = [
    "la", "ri", "na", "vo", "te", "mi", "ro", "da", "si", "ve", "lo", "qua", "ni", "be", "ca",
    "the", "le", "do", "ma", "ta", "go", "ze",
]
_ENDINGS = [
    "ra", "ix", "on", "is", "ia", "en", "ar", "o", "el", "um", "ex", "ine", "ory", "ant", "ys",
    "ett", "ane", "ova", "ic", "ent", "ura", "ion", "eth", "ol",
]
PLACE_SUFFIXES = [
    "mere", "dale", "wick", "haven", "stead", "ridge", "field", "moor", "ton", "bury", "holm",
    "vale", "brook", "cliff", "crest", "gate", "marsh", "port", "shaw", "thorpe", "wood", "worth",
    "ley", "combe", "ford", "fell", "hurst", "minster",
]
PLACE_STEMS = [
    "Ash", "Birch", "Calder", "Elm", "Fen", "Glen", "Hazel", "Ivy", "Kel", "Lin", "Mor",
    "Nor", "Oak", "Pen", "Quen", "Red", "Sel", "Tal", "Ul", "Ver", "Wil", "Yar", "Corr",
    "Dray", "Fal", "Gar", "Hol", "Ket", "Lan", "Mar", "Nether", "Ost", "Pell", "Sand",
    "Thorn", "Wex", "Alder", "Brin", "Cran", "Dor", "Ember", "Frost", "Gorse", "Heath", "Isel",
    "Juna", "Kirk", "Lom", "Mill", "Nant", "Orm", "Pyke", "Rad", "Stow", "Tey", "Vash", "Whin",
]
VENDOR_SUFFIXES = ["Labs", "Systems", "Software", "Analytics", "Health", "Learning", "Cloud", "AI"]
CODE_WORDS = [
    "Cobalt", "Marigold", "Tamarack", "Sorrel", "Bramble", "Fennel", "Lichen",
    "Basalt", "Driftwood", "Cinder", "Thicket", "Estuary", "Mistral", "Sirocco", "Halcyon", "Cirrus",
    "Pumice", "Obsidian", "Garnet", "Agate", "Feldspar", "Mica", "Shale", "Clover", "Yarrow", "Tansy",
    "Sedge", "Alder", "Linden", "Sumac", "Bittern", "Plover", "Godwit", "Curlew", "Dunlin", "Pipit",
    "Siskin", "Shrike", "Gannet", "Petrel", "Fulmar", "Kittiwake", "Wagtail", "Nuthatch", "Waxwing",
    "Lacewing", "Cicada", "Marten", "Stoat", "Ermine", "Pika", "Ibex", "Tapir", "Okapi", "Quokka",
    "Dugong", "Narwhal", "Axolotl", "Teasel", "Burdock", "Hawthorn", "Nettle", "Bracken", "Tarn",
    "Scree", "Corrie", "Moraine", "Cairn", "Fjord", "Isthmus", "Mesa", "Butte",
]


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


class NameGen:
    """Draws unique, denylist-checked names from one `random.Random`."""

    def __init__(self, rng: random.Random):
        self.rng = rng
        self.used_people: set[str] = set()
        self.used_first: set[str] = set()
        self.used_last: set[str] = set()
        self.used_words: set[str] = set()
        self.used_stems: set[str] = set()

    # ------------------------------------------------------------ people
    def person(self, *, first: str | None = None, avoid_first: set[str] | None = None) -> tuple[str, str]:
        """A (first, last) pair. First names are not reused unless given explicitly."""
        avoid_first = avoid_first or set()
        for _ in range(500):
            f = first or self.rng.choice(FIRST_NAMES)
            if first is None and (f in self.used_first or f in avoid_first):
                continue
            last = self.rng.choice(SURNAMES)
            if last in self.used_last:
                continue
            full = f"{f} {last}"
            if is_denied(full) or is_famous(full) or full in self.used_people:
                continue
            self.used_people.add(full)
            self.used_first.add(f)
            self.used_last.add(last)
            return f, last
        raise RuntimeError("name pools exhausted")

    def reserve_first(self, name: str) -> None:
        self.used_first.add(name)

    # ------------------------------------------------------------ coinage
    def coin(self, syllables: int = 2) -> str:
        """A pronounceable invented word such as 'Selvora' or 'Kelix'."""
        for _ in range(500):
            parts = [self.rng.choice(_FIRST_SYLL)]
            for _i in range(max(0, syllables - 2)):
                parts.append(self.rng.choice(_MID_SYLL))
            parts.append(self.rng.choice(_ENDINGS))
            word = parts[0]
            for p in parts[1:]:
                if word[-1] in "aeiouy" and p[0] in "aeiouy":
                    p = p[1:] or p
                word += p
            word = re.sub(r"(.)\1\1+", r"\1\1", word.lower())
            if not 5 <= len(word) <= 10 or not self._fresh(word):
                continue
            return _cap(word)
        raise RuntimeError("could not coin a word")

    def place(self) -> str:
        """A coined place name such as 'Calderwick' or 'Ostvale'. No two places in a world share
        a stem (no Vashmere next to Vashthorpe)."""
        for _ in range(500):
            stem = self.rng.choice(PLACE_STEMS)
            if stem in self.used_stems:
                continue
            word = stem + self.rng.choice(PLACE_SUFFIXES)
            if self._fresh(word):
                self.used_stems.add(stem)
                return word
        raise RuntimeError("could not coin a place")

    def code_word(self) -> str:
        """A project code name: an uncommon nature word or a coined word."""
        for _ in range(500):
            word = self.rng.choice(CODE_WORDS) if self.rng.random() < 0.55 else self.coin(2)
            if self._fresh(word):
                return word
        raise RuntimeError("could not pick a code word")

    def vendor(self, suffixes: list[str] | tuple[str, ...] | None = None) -> tuple[str, str]:
        """(full name, short name) such as ('Selvora Labs', 'Selvora')."""
        short = self.coin(self.rng.choice([2, 2, 3]))
        return f"{short} {self.rng.choice(list(suffixes or VENDOR_SUFFIXES))}", short

    def _fresh(self, word: str) -> bool:
        key = word.lower()
        if key in self.used_words or is_denied(word):
            return False
        self.used_words.add(key)
        return True


# ---------------------------------------------------------------- surface forms
def ascii_slug(s: str) -> str:
    """'Ji-ho Ó Briain' -> 'ji-ho-o-briain' (lowercase ASCII, for IDs)."""
    s = _fold(s).replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def email_local(first: str, last: str) -> str:
    f = re.sub(r"[^a-z0-9]", "", _fold(first))
    la = re.sub(r"[^a-z0-9]", "", _fold(last))
    return f"{f}.{la}"


def person_surface_forms(
    first: str,
    last: str,
    email: str,
    handle: str,
    *,
    nickname: str | None = None,
    role_phrase: str | None = None,
) -> list[str]:
    """Surface forms per docs/generator.md: first name, nickname, initial plus surname, email,
    chat handle and a role phrase (the canonical full name is the entity's `name`)."""
    forms = [first]
    if nickname:
        forms.append(nickname)
    forms.append(f"{first[0]}. {last}")
    forms.append(email)
    forms.append(handle)
    if role_phrase:
        forms.append(role_phrase)
    out: list[str] = []
    for f in forms:
        if f and f not in out:
            out.append(f)
    return out
