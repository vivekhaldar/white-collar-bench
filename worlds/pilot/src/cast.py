"""Cast, organizations and projects of the pilot world (all synthetic)."""

from dsl import org, person, project

W = "p-mara-ilves"

# ------------------------------------------------------------------ worker
person(W, "2027-02-15 08:00", "Mara Ilves",
       ["Mara", "M. Ilves", "Mara I.", "mara.ilves@tarrow.example", "@mara", "the principal architect"],
       org="o-ods", role="Principal Architect, AI & Data", email="mara.ilves@tarrow.example",
       summary="Mara Ilves (the worker), Principal Architect for AI & Data in the Office of Digital Strategy",
       group="worker",
       voice="Terse. Lowercase in chat, no greetings, arrows and abbreviations in notes (pkg, eval, w/, tbd, EOW). "
             "Polite but brief in email; signs '— Mara'. Rarely uses exclamation marks.")

# ------------------------------------------------------------------ orgs
org("o-tarrow-system", "2027-02-15 08:05", "Tarrow University System Office",
    ["Tarrow University System", "the System", "the system office", "TUS", "tarrow.example"],
    kind="internal", domain="tarrow.example", summary="Tarrow University System Office (our employer)")
org("o-ods", "2027-02-15 08:05", "Office of Digital Strategy",
    ["ODS", "Digital Strategy", "the Office of Digital Strategy"],
    kind="internal", domain="tarrow.example", summary="Office of Digital Strategy, the worker's team at the system office")
org("o-kestrow", "2027-02-15 08:05", "Tarrow University Kestrow",
    ["TU Kestrow", "Kestrow", "the Kestrow campus", "the flagship", "kestrow.tarrow.example"],
    kind="internal", domain="kestrow.tarrow.example", summary="TU Kestrow, the flagship campus hosting the Tinderbox pilot")
org("o-saltmarren", "2027-02-15 08:05", "Tarrow University Saltmarren",
    ["TU Saltmarren", "Saltmarren", "saltmarren.tarrow.example"],
    kind="internal", domain="saltmarren.tarrow.example", summary="TU Saltmarren, second campus (discovery and writing-tool selection)")
org("o-orrin-valley", "2027-02-15 08:05", "Tarrow University Orrin Valley",
    ["TU Orrin Valley", "Orrin Valley", "OV", "orrinvalley.tarrow.example"],
    kind="internal", domain="orrinvalley.tarrow.example", summary="TU Orrin Valley, lightly engaged campus")
org("o-brackwater", "2027-02-15 08:05", "Tarrow University Brackwater",
    ["TU Brackwater", "Brackwater", "brackwater.tarrow.example"],
    kind="internal", domain="brackwater.tarrow.example", summary="TU Brackwater, lightly engaged campus (library idea)")
org("o-scrivelo", "2027-02-16 10:18", "Scrivelo Learning",
    ["Scrivelo", "Scrivelo Feedback", "scrivelo.example"],
    kind="vendor", domain="scrivelo.example", summary="Scrivelo Learning, writing-feedback vendor in the bake-off")
org("o-penmarq", "2027-02-16 10:18", "Penmarq",
    ["Penmarq Inc.", "penmarq.example", "Pen Mark", "Penmark"],
    kind="vendor", domain="penmarq.example", summary="Penmarq, writing-feedback vendor in the bake-off")
org("o-eskerfield", "2027-02-19 11:00", "Eskerfield Learning Research Institute",
    ["Eskerfield", "ELRI", "the Eskerfield institute", "eskerfield.example"],
    kind="partner", domain="eskerfield.example", summary="Eskerfield Learning Research Institute, external research partner")

# ------------------------------------------------------------------ central (system office / ODS)
person("p-folasade-renwick", "2027-02-15 08:05", "Folasade Renwick",
       ["Sade", "Folasade", "Dr. Renwick", "F. Renwick", "VC Renwick", "the VC", "folasade.renwick@tarrow.example", "@sade"],
       org="o-ods", role="Vice Chancellor for Digital Strategy", email="folasade.renwick@tarrow.example", rel="manager",
       summary="Folasade (Sade) Renwick, Vice Chancellor for Digital Strategy, my manager and sponsor",
       group="central",
       voice="Crisp, decisive, short paragraphs. Wants 'three bullets and one risk'. Routes Mara through connectors "
             "('go through Bart's office', 'Lucía will find time') rather than introducing her directly. States "
             "preferences ('I lean toward...') separately from decisions ('Here is what I am deciding').")
person("p-lucia-ferreyra", "2027-02-15 09:32", "Lucía Ferreyra",
       ["Lucía", "Lucia", "Lulu", "L. Ferreyra", "Sade's EA", "lucia.ferreyra@tarrow.example", "@lucia"],
       org="o-ods", role="Executive Assistant to the Vice Chancellor", email="lucia.ferreyra@tarrow.example", rel="stakeholder",
       summary="Lucía Ferreyra, the VC's executive assistant who books Sade's time",
       group="central",
       voice="Friendly, efficient, calendar-speak ('I've put a hold', 'invite to follow'). Signs 'Lulu' in chat.")
person("p-ramona-szabo", "2027-02-15 08:05", "Ramona Szabo",
       ["Ramona", "Mona", "R. Szabo", "our programs director", "the Director of Programs", "ramona.szabo@tarrow.example", "@ramona"],
       org="o-ods", role="Director of Programs", email="ramona.szabo@tarrow.example", rel="peer",
       summary="Ramona Szabo, ODS Director of Programs and my most frequent collaborator",
       group="central",
       voice="Warm, fast, logistics-minded; emoji in chat (✅ 🎉), exclamation points, 'quick one:'. Writes tidy "
             "bulleted notes when delegated.")
person("p-ilya-marchetti", "2027-02-15 08:05", "Ilya Marchetti",
       ["Ilya", "I. Marchetti", "Marchetti", "the data platform lead", "ilya.marchetti@tarrow.example", "@ilya"],
       org="o-ods", role="Principal Architect, Data Platform", email="ilya.marchetti@tarrow.example", rel="peer",
       summary="Ilya Marchetti, peer principal for the data platform and owner of Kettleyard",
       group="central",
       voice="Precise, numbered lists, long technical emails, dry humour. Says 'per your comment 7'.")
person("p-hyunwoo-park", "2027-02-22 14:30", "Hyun-woo Park",
       ["Hyun-woo", "Hyunwoo", "Hugo", "Hugo Park", "H. Park", "the security principal", "hyunwoo.park@tarrow.example", "@hpark"],
       org="o-ods", role="Principal, Security & Identity", email="hyunwoo.park@tarrow.example", rel="peer",
       summary="Hyun-woo (Hugo) Park, peer principal for security and identity; Tinderbox's security reviewer",
       group="central",
       voice="Formal, careful, 'per policy', never commits to approval dates. Campus people call him Hugo.")
person("p-bettina-oduya", "2027-02-22 14:30", "Bettina Oduya",
       ["Bettina", "Tina", "B. Oduya", "the product principal", "bettina.oduya@tarrow.example", "@bettina"],
       org="o-ods", role="Principal, Product", email="bettina.oduya@tarrow.example", rel="peer",
       summary="Bettina Oduya, peer principal for product; worries about support handoffs",
       group="central",
       voice="User- and support-centric; asks 'who picks up the phone at 2am?'. Medium-length chat messages.")
person("p-bartosz-zielke", "2027-02-18 13:44", "Bartosz Zielke",
       ["Bartosz", "Bart", "B. Zielke", "Bart from platform", "the on-call", "bartosz.zielke@tarrow.example", "@bart"],
       org="o-ods", role="Platform Engineer", email="bartosz.zielke@tarrow.example", rel="stakeholder",
       summary="Bartosz (Bart) Zielke, Kettleyard platform engineer (gateway on-call)",
       group="central",
       voice="Lowercase chat, optimistic ('should be fine', 'all good now'), types fast, typos. Goes by 'Bart' "
             "(collides with Kestrow CIO Bart Ngata).")
person("p-marisol-etxeberria", "2027-02-15 08:05", "Marisol Etxeberria",
       ["Marisol", "Sol", "M. Etxeberria", "our talent partner", "marisol.etxeberria@tarrow.example", "@marisol"],
       org="o-tarrow-system", role="Talent Partner", email="marisol.etxeberria@tarrow.example", rel="stakeholder",
       summary="Marisol (Sol) Etxeberria, System HR talent partner on the staff ML engineer search",
       group="central",
       voice="Upbeat, process-oriented, mentions requisition rules and approvals.")
person("p-clement-oyelaran", "2027-02-16 10:18", "Clement Oyelaran",
       ["Clement", "Clem", "C. Oyelaran", "the procurement officer", "clement.oyelaran@tarrow.example"],
       org="o-tarrow-system", role="Procurement Officer", email="clement.oyelaran@tarrow.example", rel="stakeholder",
       summary="Clement Oyelaran, system procurement officer for the writing-tool purchase",
       group="central",
       voice="Careful, cites thresholds and policy numbers, catches inconsistencies, never states budget figures in email.")
person("p-agnieszka-wolanin", "2027-02-25 17:10", "Agnieszka Wolanin",
       ["Agnieszka", "Aga", "A. Wolanin", "system counsel", "agnieszka.wolanin@tarrow.example"],
       org="o-tarrow-system", role="Associate General Counsel", email="agnieszka.wolanin@tarrow.example", rel="stakeholder",
       summary="Agnieszka (Aga) Wolanin, system legal counsel (DPA and data-sharing agreements)",
       group="central",
       voice="Precise, numbered points, caveats ('subject to'), restrictive about student data leaving the System.")
person("p-percival-ndiaye", "2027-02-15 08:05", "Percival Ndiaye",
       ["Percival", "Percy", "P. Ndiaye", "the budget director", "percival.ndiaye@tarrow.example"],
       org="o-tarrow-system", role="Director of Budget & Finance", email="percival.ndiaye@tarrow.example", rel="stakeholder",
       summary="Percival (Percy) Ndiaye, system budget director who supplies chargeback inputs",
       group="central",
       voice="Numbers first, terse, conditional ('no FY28 money unless someone owns the cost').")
person("p-ods-mailbox", "2027-02-19 13:15", "ODS Team Mailbox",
       ["ODS Team", "the ODS inbox", "ods-team", "ods-team@tarrow.example"],
       org="o-ods", role="Shared team mailbox", email="ods-team@tarrow.example", rel="other",
       summary="The ODS shared team mailbox, which sends announcements and Monday reminders",
       group="central",
       voice="Behaves like a person: signs '— ODS Team', sends Monday reminders, polite boilerplate footer "
             "'This mailbox is monitored during business hours.'")

# ------------------------------------------------------------------ Kestrow (flagship)
person("p-bart-ngata", "2027-02-15 09:32", "Bartholomew Ngata",
       ["Bart", "Bart Ngata", "Dr. Ngata", "B. Ngata", "the Kestrow CIO", "Kestrow's CIO", "bart.ngata@kestrow.tarrow.example"],
       org="o-kestrow", role="Chief Information Officer", email="bart.ngata@kestrow.tarrow.example", rel="executive",
       summary="Bartholomew (Bart) Ngata, CIO of TU Kestrow",
       group="kestrow",
       voice="Big-picture, campus-first, protective of Kestrow autonomy; prefers internal builds; rarely in chat.")
person("p-yusra-haddad", "2027-02-15 08:05", "Yusra Haddad",
       ["Yusra", "Y. Haddad", "the TLT director", "Kestrow TLT", "yusra.haddad@kestrow.tarrow.example", "@yusra"],
       org="o-kestrow", role="Director of Teaching & Learning Technology", email="yusra.haddad@kestrow.tarrow.example", rel="stakeholder",
       summary="Yusra Haddad, Kestrow's director of teaching & learning technology and Tinderbox's campus lead",
       group="kestrow",
       voice="Organized, runs the Tinderbox standup, pragmatic, short sentences, 'let's take that offline'.")
person("p-joaquin-sepulveda", "2027-02-15 11:04", "Joaquín Sepúlveda",
       ["Joaquín", "Joaquin", "Jack", "J. Sepúlveda", "J. Sepulveda", "Kestrow's enterprise architect", "joaquin.sepulveda@kestrow.tarrow.example", "@jsep"],
       org="o-kestrow", role="Enterprise Architect", email="joaquin.sepulveda@kestrow.tarrow.example", rel="stakeholder",
       summary="Joaquín (Jack) Sepúlveda, Kestrow enterprise architect who chairs the campus architecture review board",
       group="kestrow",
       voice="Standards-minded, refers to 'ARB', polite but firm. Mara calls him Jack in notes.")
person("p-dmitri-halloran", "2027-02-15 11:04", "Dmitri Halloran",
       ["Dmitri", "Dima", "D. Halloran", "dmitri.halloran@kestrow.tarrow.example", "@dima"],
       org="o-kestrow", role="Software Engineer", email="dmitri.halloran@kestrow.tarrow.example", rel="stakeholder",
       summary="Dmitri (Dima) Halloran, Kestrow engineer building Tinderbox's LMS context API",
       group="kestrow",
       voice="Blunt, frustrated by spec churn, dev slang, lowercase, sarcasm.")
person("p-saanvi-raghunathan", "2027-02-26 09:30", "Saanvi Raghunathan",
       ["Saanvi", "S. Raghunathan", "saanvi.raghunathan@kestrow.tarrow.example", "@saanvi"],
       org="o-kestrow", role="Site Reliability Engineer", email="saanvi.raghunathan@kestrow.tarrow.example", rel="stakeholder",
       summary="Saanvi Raghunathan, Kestrow SRE who owns the Tinderbox load test",
       group="kestrow",
       voice="Precise, quotes numbers (p95, concurrency), calm.")
person("p-teodor-lisowski", "2027-02-16 17:20", "Teodor Lisowski",
       ["Teodor", "Teo", "T. Lisowski", "Teo Lisofsky", "Lisofsky", "the identity admin", "teodor.lisowski@kestrow.tarrow.example", "@teo"],
       org="o-kestrow", role="Identity & Access Administrator", email="teodor.lisowski@kestrow.tarrow.example", rel="stakeholder",
       summary="Teodor (Teo) Lisowski, Kestrow identity & access administrator (Tinderbox SSO)",
       group="kestrow",
       voice="Quiet, ticket numbers, 'waiting on the IdP vendor'. Auto-transcripts spell his surname 'Lisofsky'.")
person("p-greta-voss", "2027-02-26 09:30", "Margarethe Voss",
       ["Greta", "Margarethe", "M. Voss", "the service desk lead", "greta.voss@kestrow.tarrow.example", "@greta"],
       org="o-kestrow", role="Service Desk Lead", email="greta.voss@kestrow.tarrow.example", rel="stakeholder",
       summary="Margarethe (Greta) Voss, Kestrow service desk lead writing the Tinderbox tier-1 runbook",
       group="kestrow",
       voice="Practical, joins meetings late from a shared room device, asks about tickets and FAQs.")
person("p-emeka-nwosu-hart", "2027-02-17 10:50", "Emeka Nwosu-Hart",
       ["Emeka", "Prof. Nwosu-Hart", "Professor Nwosu-Hart", "E. Nwosu-Hart", "the faculty champion", "emeka.nwosuhart@kestrow.tarrow.example"],
       org="o-kestrow", role="Associate Professor of Chemistry", email="emeka.nwosuhart@kestrow.tarrow.example", rel="stakeholder",
       summary="Emeka Nwosu-Hart, chemistry professor and Tinderbox faculty champion",
       group="kestrow",
       voice="Enthusiastic, long friendly emails, many exclamation marks, mentions students by course number.")
person("p-constance-wilberforce", "2027-02-19 11:00", "Constance Wilberforce",
       ["Constance", "Connie", "Prof. Wilberforce", "C. Wilberforce", "constance.wilberforce@kestrow.tarrow.example"],
       org="o-kestrow", role="Professor of History", email="constance.wilberforce@kestrow.tarrow.example", rel="stakeholder",
       summary="Constance (Connie) Wilberforce, history professor and the pilot's most pointed skeptic",
       group="kestrow",
       voice="Sharp, skeptical, asks for evidence, dislikes 'satisfaction' metrics; dry wit.")
person("p-ingrid-solberg", "2027-02-17 10:50", "Ingrid Solberg",
       ["Ingrid", "I. Solberg", "the instructional designer", "ingrid.solberg@kestrow.tarrow.example", "@ingrid"],
       org="o-kestrow", role="Senior Instructional Designer", email="ingrid.solberg@kestrow.tarrow.example", rel="stakeholder",
       summary="Ingrid Solberg, Kestrow instructional designer running Tinderbox faculty onboarding",
       group="kestrow",
       voice="Calm, structured, short emails with dates and room numbers.")
person("p-hana-kobayashi-reyes", "2027-03-02 08:05", "Hana Kobayashi-Reyes",
       ["Hana", "H. Kobayashi-Reyes", "the new privacy officer", "Kestrow privacy", "hana.kobayashireyes@kestrow.tarrow.example"],
       org="o-kestrow", role="Privacy Officer", email="hana.kobayashireyes@kestrow.tarrow.example", rel="stakeholder",
       summary="Hana Kobayashi-Reyes, Kestrow's new privacy officer (Tinderbox privacy review)",
       group="kestrow",
       voice="Formal, new in role, introduces herself, references the campus privacy impact assessment (PIA) process. "
             "Near-homophone of Scrivelo's Hannah Feld.")

# ------------------------------------------------------------------ Saltmarren
person("p-delphine-arceneaux", "2027-02-15 08:05", "Delphine Arceneaux",
       ["Delphine", "D. Arceneaux", "the registrar", "the interim registrar", "delphine.arceneaux@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Interim Registrar", email="delphine.arceneaux@saltmarren.tarrow.example", rel="stakeholder",
       summary="Delphine Arceneaux, Saltmarren's interim registrar and campus sponsor for the discovery and the writing tool",
       group="saltmarren",
       voice="Warm, direct, juggling a lot; uses relative dates ('by Thursday', 'next Tuesday').")
person("p-lionel-mbatha", "2027-02-23 11:00", "Lionel Mbatha",
       ["Lionel", "L. Mbatha", "Saltmarren's IT director", "lionel.mbatha@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Director of IT", email="lionel.mbatha@saltmarren.tarrow.example", rel="stakeholder",
       summary="Lionel Mbatha, Saltmarren IT director who prefers building on Kettleyard to buying a tool",
       group="saltmarren",
       voice="Skeptical of vendors, 'for the record', precise about what he did and did not agree to.")
person("p-ottilie-brandvold", "2027-03-02 12:40", "Ottilie Brandvold",
       ["Tillie", "Ottilie", "O. Brandvold", "Tillie from advising", "the advising lead", "ottilie.brandvold@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Advising Operations Lead", email="ottilie.brandvold@saltmarren.tarrow.example", rel="stakeholder",
       summary="Ottilie (Tillie) Brandvold, Saltmarren advising operations lead",
       group="saltmarren",
       voice="Energetic, data-driven, signs emails 'Tillie' with full signature block underneath.")
person("p-rufus-adekunle", "2027-02-16 14:02", "Rufus Adekunle",
       ["Rufus", "R. Adekunle", "the transfer credit coordinator", "rufus.adekunle@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Transfer Credit Coordinator", email="rufus.adekunle@saltmarren.tarrow.example", rel="stakeholder",
       summary="Rufus Adekunle, Saltmarren transfer credit coordinator",
       group="saltmarren",
       voice="Methodical, process-map person, short emails with attachments.")

person("p-corwin-bellamy-tate", "2027-03-01 11:48", "Corwin Bellamy-Tate",
       ["Corwin", "C. Bellamy-Tate", "Mr. Bellamy-Tate", "the writing center director", "corwin.bellamytate@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Director of the Writing Center", email="corwin.bellamytate@saltmarren.tarrow.example", rel="stakeholder",
       summary="Corwin Bellamy-Tate, director of Saltmarren's writing center (would staff any sandbox trial)",
       group="saltmarren",
       voice="Kind, overcommitted, talks about his tutors and midterm crunch; hedges ('honestly we're slammed').")
person("p-ezinne-marlowe-abara", "2027-03-04 11:20", "Ezinne Marlowe-Abara",
       ["Ezinne", "Dr. Marlowe-Abara", "E. Marlowe-Abara", "the VP", "Saltmarren's VP for Academic Affairs", "ezinne.marloweabara@saltmarren.tarrow.example"],
       org="o-saltmarren", role="Vice President for Academic Affairs", email="ezinne.marloweabara@saltmarren.tarrow.example", rel="executive",
       summary="Dr. Ezinne Marlowe-Abara, Saltmarren VP for Academic Affairs, who countersigns the data-sharing agreement",
       group="saltmarren",
       voice="Brief, formal, signs with full title; delegates to Delphine.")

# ------------------------------------------------------------------ lightly engaged campuses
person("p-niall-fairbrother", "2027-02-15 08:05", "Niall Fairbrother",
       ["Niall", "N. Fairbrother", "the Orrin Valley CIO", "niall.fairbrother@orrinvalley.tarrow.example"],
       org="o-orrin-valley", role="Chief Information Officer", email="niall.fairbrother@orrinvalley.tarrow.example", rel="stakeholder",
       summary="Niall Fairbrother, Orrin Valley CIO (citation-helper idea; skeptical of chargeback)",
       group="light",
       voice="Rarely replies; when he does, one line.")
person("p-ramona-iturbe", "2027-02-15 08:05", "Ramona Iturbe",
       ["Ramona", "R. Iturbe", "Ramona I.", "Brackwater's library dean", "ramona.iturbe@brackwater.tarrow.example"],
       org="o-brackwater", role="Associate Dean of Libraries", email="ramona.iturbe@brackwater.tarrow.example", rel="stakeholder",
       summary="Ramona Iturbe, Brackwater associate dean of libraries (library research assistant idea)",
       group="light",
       voice="Gracious, unhurried, academic tone. Shares a first name with Ramona Szabo.")

# ------------------------------------------------------------------ vendors
person("p-gregor-lindahl", "2027-02-16 10:18", "Gregor Lindahl",
       ["Gregor", "Grig", "G. Lindahl", "gregor.lindahl@scrivelo.example"],
       org="o-scrivelo", role="Account Executive", email="gregor.lindahl@scrivelo.example", rel="vendor",
       summary="Gregor Lindahl, Scrivelo account executive",
       group="vendor", voice="Salesy but competent; follow-up nudges; signature with a calendar link.")
person("p-hannah-feld", "2027-02-23 11:00", "Hannah Feld",
       ["Hannah", "H. Feld", "Scrivelo's solutions engineer", "hannah.feld@scrivelo.example"],
       org="o-scrivelo", role="Solutions Engineer", email="hannah.feld@scrivelo.example", rel="vendor",
       summary="Hannah Feld, Scrivelo solutions engineer",
       group="vendor", voice="Technical, demo-driven. Near-homophone of Hana Kobayashi-Reyes.")
person("p-juniper-hale", "2027-02-16 10:18", "Juniper Hale",
       ["Juniper", "Juni", "J. Hale", "juniper.hale@penmarq.example"],
       org="o-penmarq", role="Account Executive", email="juniper.hale@penmarq.example", rel="vendor",
       summary="Juniper (Juni) Hale, Penmarq account executive",
       group="vendor", voice="Bubbly, responsive; goes on parental leave from 5 March and hands off to Ximena.")
person("p-callum-ferris", "2027-03-01 11:50", "Callum Ferris",
       ["Callum", "C. Ferris", "the Penmarq SE", "callum.ferris@penmarq.example"],
       org="o-penmarq", role="Solutions Engineer", email="callum.ferris@penmarq.example", rel="vendor",
       summary="Callum Ferris, Penmarq solutions engineer",
       group="vendor", voice="Technical, terse, sends credentials in plain email (bad practice).")
person("p-ximena-robles", "2027-03-03 09:05", "Ximena Robles",
       ["Ximena", "X. Robles", "Juniper's cover at Penmarq", "ximena.robles@penmarq.example"],
       org="o-penmarq", role="Senior Account Executive", email="ximena.robles@penmarq.example", rel="vendor",
       summary="Ximena Robles, Penmarq senior account executive covering Juniper's leave",
       group="vendor", voice="Polished, formal, long legal-ish email footer.")

# ------------------------------------------------------------------ external researcher and candidate
person("p-ines-vardakis", "2027-02-19 11:00", "Ines Vardakis",
       ["Ines", "Dr. Vardakis", "I. Vardakis", "ines.vardakis@eskerfield.example"],
       org="o-eskerfield", role="Senior Research Scientist", email="ines.vardakis@eskerfield.example", rel="partner",
       summary="Dr. Ines Vardakis, Eskerfield researcher (workshop keynote; library assistant evaluation)",
       group="external", voice="Collegial, precise, research vocabulary, books meetings herself.")
person("p-mateus-okonedo", "2027-02-17 16:30", "Mateus Okonedo",
       ["Mateus", "Mats", "M. Okonedo", "the MLE candidate", "mateus.okonedo@postbox.example"],
       role="Candidate, Staff ML Engineer", email="mateus.okonedo@postbox.example", rel="candidate",
       summary="Mateus (Mats) Okonedo, candidate for the staff ML engineer role",
       group="external", voice="Polite, careful, slightly formal; signs 'Mats'.")

# ------------------------------------------------------------------ minor people
person("p-lorne-castellan", "2027-03-01 07:12", "Lorne Castellan",
       ["Lorne", "The Lattice Ledger", "lorne@latticeledger.example"],
       minor=True, note="Editor of The Lattice Ledger, a higher-ed tech newsletter",
       summary="Lorne Castellan, newsletter editor", group="minor", voice="Newsletter prose.")
person("p-ksd-bot", "2027-03-01 16:48", "Kestrow Service Desk",
       ["KSD", "noreply-servicedesk@kestrow.tarrow.example"],
       minor=True, note="Automated ticketing notifications", summary="Kestrow Service Desk (automated)", group="minor",
       voice="Automated ticket template.")
person("p-recruit-bot", "2027-03-02 07:00", "TarrowRecruit Notifications",
       ["TarrowRecruit", "noreply@recruit.tarrow.example"],
       minor=True, note="Applicant-tracking system notifications", summary="TarrowRecruit (automated)", group="minor",
       voice="Automated reminder template.")
person("p-tus-itservices", "2027-03-02 06:30", "Tarrow IT Services",
       ["System IT", "itservices@tarrow.example", "Tarrow IT Services Desk"],
       minor=True, note="System-wide IT all-staff notices", summary="Tarrow IT Services (all-staff notices)", group="minor",
       voice="All-staff notice template.")
person("p-kettleyard-status", "2027-03-03 10:04", "Kettleyard Status",
       ["Kettleyard Status", "status-noreply@tarrow.example"],
       minor=True, note="Automated status-page notifications", summary="Kettleyard status page (automated)", group="minor",
       voice="Status-page template.")
person("p-wendell-wickham", "2027-03-03 15:30", "Wendell Wickham",
       ["Wendell", "Kestrow Event Services", "wendell.wickham@kestrow.tarrow.example"],
       minor=True, note="Kestrow event services coordinator", summary="Wendell Wickham, Kestrow event services", group="minor",
       voice="Booking-confirmation boilerplate.")
person("p-beatriz-solano", "2027-03-06 07:00", "Beatriz Solano",
       ["Beatriz", "Campus Futures Forum", "beatriz@campusfutures.example"],
       minor=True, note="Conference organizer, Campus Futures Forum", summary="Beatriz Solano, conference organizer",
       group="minor", voice="Conference marketing.")

# ------------------------------------------------------------------ projects (all known from Mara's portfolio note, 15 Feb)
P0 = "2027-02-15 08:05"
project("pr-tinderbox", P0, "Tinderbox",
        ["Project Tinderbox", "the Kestrow course assistant pilot", "the course assistant pilot", "the Kestrow pilot", "KCA", "Tinderbox pilot"],
        summary="Tinderbox: AI course-assistant pilot at TU Kestrow",
        status="active", owner=W, phase="build", target_date="2027-03-22", sponsor="p-folasade-renwick",
        members=[W, "p-yusra-haddad", "p-ramona-szabo"], orgs=["o-kestrow", "o-ods"],
        state='Pilot of an AI course assistant for a handful of Kestrow courses, to be hosted centrally. I am writing the architecture one-pager and the LMS interface spec; Yusra Haddad leads the campus team. Go-live is targeted for 22 March.',
        _archetype="flagship_pilot")
project("pr-kettleyard", P0, "Kettleyard",
        ["the hub", "Kettleyard hub", "the shared AI platform", "the shared platform", "KYD"],
        summary="Kettleyard: the shared AI platform hub (tenants, identity, model gateway, secrets)",
        status="active", owner="p-ilya-marchetti", phase="tenant onboarding", sponsor="p-folasade-renwick",
        members=["p-ilya-marchetti", W], orgs=["o-ods"], state="Ilya's team is onboarding the first tenants onto Kettleyard's shared model gateway, identity broker and secrets vault, with Tinderbox first in line; reference architecture v3 is being drafted.", _archetype="reference_design_programme")
project("pr-wft", P0, "Writing Feedback Tool Selection",
        ["the writing tool bake-off", "the bake-off", "WFT selection", "the writing feedback tool", "the Scrivelo/Penmarq evaluation"],
        summary="Writing Feedback Tool Selection for Saltmarren (potentially system-wide)",
        status="active", owner=W, phase="vendor questionnaires", target_date="2027-03-26", sponsor="p-delphine-arceneaux",
        members=[W, "p-delphine-arceneaux"], orgs=["o-saltmarren"], state='Selecting a writing-feedback tool for Saltmarren (possibly system-wide later); vendor security questionnaires are about to go to Scrivelo and Penmarq. Recommendation targeted for 26 March.', _archetype="competitive_vendor_selection")
project("pr-transfer-eval", P0, "Saltmarren Transfer Evaluation Discovery",
        ["the Saltmarren discovery", "transfer credit discovery", "the transcript evaluation work", "TCE discovery"],
        summary="Saltmarren discovery on AI help for transfer-student transcript evaluation",
        status="active", owner=W, phase="discovery", target_date="2027-03-19", sponsor="p-delphine-arceneaux",
        members=[W, "p-delphine-arceneaux"], orgs=["o-saltmarren"], state="Discovery with Saltmarren's registrar on AI support for transfer-student transcript evaluation; a site visit is being planned. Readout targeted for 19 March.", _archetype="pivoting_discovery")
project("pr-workshop", P0, "Teaching with AI Faculty Workshop",
        ["the faculty workshop", "the workshop", "the March 4 workshop", "TwAI workshop"],
        summary="Teaching with AI faculty workshop at Kestrow on 4 March",
        status="active", owner="p-ramona-szabo", phase="planning", target_date="2027-03-04", sponsor="p-folasade-renwick",
        members=["p-ramona-szabo", W], orgs=["o-ods", "o-kestrow"], state='Ramona is organizing a half-day Teaching with AI workshop for Kestrow faculty on 4 March; keynote and panel are being lined up and I own the deck.', _archetype="recurring_programme")
project("pr-chargeback", P0, "Kettleyard Cost-Sharing Model",
        ["the chargeback model", "the cost model", "cost-sharing model", "chargeback", "the econ model"],
        summary="Cost-sharing / chargeback model for Kettleyard across campuses",
        status="active", owner=W, phase="inputs", target_date="2027-03-12", sponsor="p-folasade-renwick",
        members=[W, "p-percival-ndiaye", "p-ramona-szabo"], orgs=["o-ods", "o-tarrow-system"], state='Building cost-sharing options for Kettleyard. Sade needs options well ahead of the 12 March Council of Campus CIOs; waiting on budget inputs from Percy.',
        _archetype="economics_model")
project("pr-mle-hire", P0, "Staff ML Engineer Hire",
        ["the MLE hire", "the staff MLE search", "REQ-2207", "the ML engineer req"],
        summary="Hiring a staff ML engineer for ODS",
        status="active", owner="p-folasade-renwick", phase="screening", sponsor="p-folasade-renwick",
        members=[W, "p-marisol-etxeberria", "p-folasade-renwick"], orgs=["o-ods"], state='Staff ML engineer requisition is open with Sade as hiring manager; Marisol is sourcing and I run the technical phone screens, which start this week.', _archetype="hiring_pipeline")
project("pr-library-ra", P0, "Library Research Assistant",
        ["the library RA idea", "library research assistant", "the Brackwater library idea", "LRA"],
        summary="Library research-assistant idea with Brackwater's library (parked)",
        status="dormant", owner=W, phase="idea", members=[W, "p-ramona-iturbe"], orgs=["o-brackwater"],
        state="Parked since January: a library research-assistant idea with Brackwater's library. I still owe Ramona Iturbe a concept note; no activity.", _archetype="vendor_diligence_that_stalls")
project("pr-citation-helper", P0, "Citation Helper (placeholder)",
        ["citation helper", "the citation checker", "Niall's citation checker idea"],
        summary="Placeholder for Niall's citation-checker idea at Orrin Valley",
        status="dormant", owner="p-niall-fairbrother", phase="placeholder", members=[W, "p-niall-fairbrother"], orgs=["o-orrin-valley"],
        state="Placeholder for Niall's citation-checker idea from Orrin Valley; waiting on his requirements, no activity.", _archetype="placeholder")
