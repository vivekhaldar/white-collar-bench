# Privacy policy and leak scanner

white-collar-bench is modelled on the structure of a real, private knowledge-work repository. This page states the synthetic-only policy, explains how the leak scanner checks benchmark content against a private repository, and defines the release gate. The scanner lives in `wcb/privacy/` and runs as `wcb privacy scan`.

## Policy: synthetic data only

These rules come from [AGENTS.md](../AGENTS.md) and apply to everyone who writes benchmark content, people and models alike.

- Every project, person, organization, email address, document, meeting, date and other detail in this repository must be synthetic.
- Borrow patterns only: record types, workflows, failure modes and task shapes. Never copy, paraphrase or lightly disguise real names, projects, customers, products, events or quotations.
- Do not read private source repositories while authoring benchmark content, unless the user explicitly asks for a pattern-level review. Never transcribe their contents.
- If generated content resembles a real person or organization, replace it.

In practice:

- Use reserved domains for every address and link: `.example` (for example `ada.quist@larchmont.example`), or `example.com`. The scanner never reports these.
- Invent organization names. Do not use lookalikes of real companies.
- Take people's names from the synthetic name generator, not from memory of real colleagues.
- Generator prompts contain only archetypes, synthetic plans and calibration numbers, never private text (see [plan §6](plan.md#6-privacy-safeguards)).

## What the scanner catches

The scanner catches **lexical carry-over**: identifiers or sentences from the private repository that reappear in benchmark content. It does not catch paraphrase, a real situation retold with new names, or structural resemblance. Those need human review (see the [release gate](#release-gate)).

It compares five kinds of term:

| Kind | What overlaps | Severity |
|---|---|---|
| `email` | A full email address | high |
| `domain` | An email domain or a bare domain name in prose (`<org>.com`) | high |
| `url_host` | The host of a URL (`https://wiki.<org>.com/...`) | high |
| `proper_noun` | A run of 2-4 capitalized words, such as a full name or an organization name | high |
| `proper_noun` | A single capitalized word | medium, or low for a very common first name or surname |
| `phrase` | 6 or more consecutive words, where each 6-word window has at least two different uncommon words | high |

Matching details:

- **Hosts** are compared by registrable domain, so `mail.<org>.com` on one side matches `<org>.com` on the other. `.co.uk`-style suffixes are handled. On multi-tenant platforms the tenant is compared instead, so `<org>.slack.com`, `<org>.atlassian.net`, `<org>.sharepoint.com` and `<org>.github.io` each count as the organization's own host, not as the platform.
- **Ignored hosts and addresses:** reserved TLDs (`.example`, `.test`, `.invalid`, `.localhost`), `example.com/.org/.net`, well-known public hosts (`github.com`, `arxiv.org`, `google.com`, `anthropic.com`, `openai.com`, `schema.org`, `w3.org` and others; see `GENERIC_HOSTS` in `wcb/privacy/scan.py`) and shared role mailboxes on those hosts (`noreply@github.com`).
- **Proper nouns** ignore:
  - common English words, including inflected forms ("Planning", "Reviews");
  - months, weekdays and holidays;
  - countries, US states, major cities, nationalities and languages;
  - generic technology and business vocabulary ("Slack", "PDF", "OKR", "DTSTART");
  - Python builtin names ("ValueError");
  - words shorter than `--min-len` (default 4).
- **The lowercase rule:** a word must be capitalized at least as often as it is written in lowercase, on both sides. This drops ordinary words that are capitalized only at sentence starts and in headings. Lowercase slugs such as `quillon-marbeck` do not count as lowercase uses.
- **Runs** must start with an uncommon word ("Quillon Marbeck") or with a first name followed by another name or uncommon word ("Mark Quellby", but not "Grant Proposal"). They may include connectors ("Ludo van Brakel", "Brakel Institute of Vray") and middle initials.
- **Folding:** a single word or shorter run that only appears inside a longer reported run is folded into it. An email domain that only appears inside reported addresses is folded into the email finding. Overlapping phrase windows are merged into the longest span.
- **File and directory names** are scanned as text on both sides, so a private file called `people/Ottoline Vray.md` counts.

The built-in vocabulary is in `wcb/privacy/wordlist.py`. These are generic public word lists, not derived from any private repository.

## Running a scan

From the root of a benchmark checkout:

```bash
wcb privacy scan --private-repo ~/path/to/private-repo worlds/ docs/ contract/
```

- `--private-repo` is a local checkout of the private repository. It must not be inside the benchmark checkout, and the benchmark checkout must not be inside it. If either is nested in the other, the nested part is skipped on the other side.
- The positional paths are the benchmark content to check: files or directories. Also scan a freshly generated world before committing it: `wcb privacy scan --private-repo ~/path/to/private-repo /tmp/gen-s7-w2`.
- `--min-len N` sets the minimum length of a reported single word. The default is 4.
- Exit status: `0` no findings, `1` findings, `2` a path is missing or one side has nothing to scan. An empty side is an error because a scan of nothing proves nothing.

From Python:

```python
from pathlib import Path
from wcb.privacy.scan import scan

stats: dict = {}
findings = scan(Path("~/path/to/private-repo").expanduser(), [Path("worlds"), Path("docs")], stats=stats)
print(stats)  # {'corpus_files': ..., 'private_files': ..., 'private_files_skipped': ..., 'allowlist_files': [...]}
for f in findings:
    print(f.format())
```

`wcb.privacy.scan.extract_terms(texts)` returns the candidate terms of each kind for a few strings, which helps when you want to see why something was or was not flagged.

### What is read

| Side | Read | Skipped |
|---|---|---|
| Private repository | `.md .markdown .txt .rst .org .json .jsonl .yaml .yml .toml .vtt .eml .csv .tsv .ics .html .htm .py .ts .tsx .js .jsx .mjs .cjs` | `.git`, `node_modules`, `__pycache__`, virtual environments (any directory containing `pyvenv.cfg`, plus `.venv` and `venv`), tool caches, binary files, files over 2 MB, Office and PDF files |
| Benchmark corpus | The same text formats, plus `.docx`, `.xlsx` and `.pptx` (body text, comments, document properties, author attributes, hyperlink targets) and `.pdf` (best effort) | The same directories, files over 64 MB, `.privacy-allow.txt` |

JSON is reduced to its string keys and values. HTML is stripped of tags, but link targets are kept. Email is read raw, plus any base64 or quoted-printable text parts, decoded. For PDFs the scanner uses `pypdf` if it is installed. Otherwise a built-in reader handles simple PDFs with standard fonts, which covers PDFs rendered by the benchmark.

### What is never written

- The private repository is read at run time only. The scanner writes nothing to disk: no cache, no term list, no temporary files.
- Across the scan, memory holds only terms that already occur in the benchmark corpus. The scanner indexes the corpus first, then streams the private repository one file at a time and keeps only matches and per-term file counts; each private file's text and terms are discarded once it has been processed. Six-word windows are held as in-process hashes.
- A finding contains the **benchmark-side** term, the corpus file it appears in, and the **number** of private files that contain it. It never contains a private path or private context.

Even so, the output says that a term occurs in the private repository. Treat scan output as confidential. Do not paste it into public issues, pull requests or CI logs, and do not run the scan in public CI.

## Interpreting findings

Each finding is one line. This sample output is illustrative and uses invented terms:

```text
HIGH   proper_noun "Quillon Marbeck" in worlds/dev/w03/inbox/2027-02-01/em-0012.eml (+4 more corpus files); in 2 private files
HIGH   phrase      "we fold the brindle quorvane into the halcyon tessarine" in docs/design.md; in 1 private file
MEDIUM proper_noun "Zephyrine" in worlds/dev/w03/world.yaml; in 7 private files
LOW    proper_noun "Michael" in worlds/pilot/inbox/2027-01-05/ch-0003.json; in 31 private files
4 potential leak(s)
```

Findings are sorted by severity, kind and term. The corpus file is the first file, in sorted order, that contains the term. `(+N more corpus files)` means the term appears in N other files too. Use `grep -rn` to find them all.

How to triage:

- **High.** Treat it as a leak until you have shown otherwise. Replace the name, domain or sentence at its source: the hand-authored world files, the generator's name pools or templates, or the docs. Then rebuild derived files with `wcb world build` (never edit `gold/` by hand) and scan again. A full name or organization name that matches by coincidence still gets replaced, because renaming is cheap.
- **Medium.** An uncommon word appears in both. Decide what it is in the benchmark: a codename, product, surname, place or plain word.
  - If it could be what the private repository calls a person, project, customer or product, replace it.
  - If it is generic, such as a technical term, a public product or paper, or an ordinary word missing from the built-in list, allowlist it.
- **Low.** A very common first name or surname appears in both. This is usually a coincidence. Rename the synthetic character if the private count is high and the character plays a similar role, for example a vendor contact who shares a first name with a frequent private contact. Otherwise allowlist the name.
- **The private file count** gives context. A term found in many private files is central there. A phrase found in many private files is probably boilerplate, such as a template or an email signature.

## Allowlist: `.privacy-allow.txt`

To suppress a reviewed false positive, add it to a file named `.privacy-allow.txt`. The scanner reads this file from each corpus path and from every parent directory up to the repository root, which is the first directory containing `.git` or `pyproject.toml`. One file at the root of the benchmark checkout therefore covers `worlds/`, `docs/` and `contract/`. The allowlist file itself is never scanned.

```text
# .privacy-allow.txt: reviewed false positives. Keep reasons generic.
Michael              # very common first name
Telemetry            # ordinary word missing from the built-in list
toolvendor.example   # public vendor site (illustrative; real domains work the same way)
```

- Entries are matched case- and accent-insensitively. A `#` starts a comment, either on its own line or after a space.
- A **single word** is treated as common vocabulary everywhere. It is never reported alone, cannot start a run, and does not count as an uncommon word in phrases.
- A **multi-word entry** suppresses exactly that run, or a phrase finding whose full reported text matches it.
- An **entry containing a dot** suppresses `domain` and `url_host` findings for that host and its subdomains. Full email addresses at that domain are still reported.
- An **email address** suppresses that address.

**The allowlist is committed and public, and every entry implies that the term occurs in the private repository.** Only allowlist terms whose presence there reveals nothing: generic vocabulary, public products and publications, very common names. Never allowlist a term that is specific to the private repository; change the benchmark instead. Keep reasons generic ("common first name", "public tool") and never mention private context.

## Release gate

Every release, and every pull request that adds or regenerates worlds or documentation, must pass both checks.

1. **Clean scan.** Run `wcb privacy scan --private-repo <path> worlds/ docs/ contract/` against the current private repository. It must exit with status 0: fix every finding, or allowlist it with a generic reason. Record in the release notes or checklist that the scan was clean, with the `wcb --version`, the date and who ran it. Do not record the findings.
2. **Manual skim.** Someone familiar with the private repository reads a random sample of artifacts: at least 20 per world, or 5% of artifacts if that is more, spread across channels (email, chat, transcripts, notes, documents, calendar). `python scripts/realism_packet.py --world <w> --per-channel 4 --out review/` draws such a sample into one readable file with a score sheet, which also serves the realism review. They look for things the scanner cannot see:
   - real people, organizations, products or events described with new names;
   - paraphrased real situations or quotations;
   - distinctive real numbers, dates or places;
   - real meeting links, phone numbers or credentials.

3. **Name pools.** If the generator's name pools changed, run `python scripts/check_name_pools.py --private-repo <path>`. It writes every pool name into a line of prose, scans it, and prints only counts; `--fix` removes flagged names from `wcb/world/names.py`. Then regenerate the committed dev worlds. Never record what a review found in the repository (not even as hashes, which a dictionary reverses): remove the term at its source instead.

Prose rewritten by an LLM (`wcb generate --llm`) gets the same treatment. If a leak is found after release, remove it, regenerate the affected worlds, scan again and publish a new release.

## Limitations

- Only exact terms and sentences are matched. Paraphrases and look-alike names ("Quillon Marbek") are not detected.
- Names made entirely of dictionary words, such as a firm named after a color and a landmark, are only caught by the phrase check or the manual skim. The same goes for single-word codenames that are ordinary English words ("Harbor").
- Single words shorter than `--min-len` are not reported alone, though they still count inside runs.
- On the private side, only plain-text formats are read. Content that exists only in Office files, PDFs, images or audio there is not compared.
- PDF text extraction is best effort. PDFs with embedded CID fonts may yield no text unless `pypdf` is installed.
