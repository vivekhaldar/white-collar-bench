# Store contract (Track A)

In Track A the agent keeps the worker's knowledge store in a fixed format, described in [`contract/CONTRACT.md`](../contract/CONTRACT.md). Each workspace gets a copy of that file as `CONTRACT.md`. It is the only specification the agent sees. It says **what** the store must contain (people, organizations, projects, loops and daily logs as Markdown records with YAML front matter) and which rules it must follow. It does not say **how** to produce it.

A fixed contract makes stores comparable across agents. The benchmark can then:

- inspect the store directly after every ingestion day and compare it with the hidden world state (entity, loop and field accuracy; see [scoring](scoring.md#store-integrity-track-a));
- swap in a correct "oracle" store for the same date, to separate ingestion errors from synthesis errors;
- check mechanical rules, such as IDs, links, `Current state` paragraphs and privacy, with a validator that competitors can run themselves.

The front-matter schemas are in [`contract/schemas/`](../contract/schemas/), one per record type. Unknown extra fields are allowed. For a small, fully valid example store, see [`tests/fixtures/sample-store/`](../tests/fixtures/sample-store/).

## Validating a store

```bash
wcb validate store <dir>          # human-readable report
wcb validate store <dir> --json   # machine-readable list of issues
```

The exit code is 0 when there are no errors (warnings are allowed), 1 when there is at least one error, and 2 when the directory does not exist. Errors count against the store's **Validity** metric: `1 − min(1, errors / records)`. Warnings are advice and do not affect any score.

The validator ignores `.git/`, `inbox/` and `.wcb/`. All other files are read, including `sources/` and `notes/`, because the privacy rules apply everywhere.

Sample output for a store with a few deliberate mistakes:

```text
$ wcb validate store my-store
ERROR   loops/return-tessellate-security-questionnaire.md: [link.missing] owner: no person record 'people/ada'
ERROR   loops/send-january-reconciliation-report.md: [schema] status: 'in-progress' is not one of ['open', 'waiting', 'blocked', 'done', 'dropped']
ERROR   notes/meetings.md: [privacy.join-link] line 1: meeting join link to meet.vidlink.example; write [redacted] instead
ERROR   notes/meetings.md: [privacy.passcode] line 1: 'passcode' followed by a value; write [redacted] instead
WARNING people/sam-patel.md: [duplicate.email] people/sam-patel, people/samir share the email address sam.patel@larchmont.example
ERROR   projects/quillon.md: [project.current-state] '## Current state' must begin 'As of YYYY-MM-DD:'
5 error(s), 1 warning(s)
```

### Checks

The authoritative list is `CODES` in [`wcb/contract/validate.py`](../wcb/contract/validate.py).

**Layout**

| Code | Severity | Check |
|---|---|---|
| `me.missing` | error | `people/me.md`, the worker's record, exists. |
| `name.slug` | error | Record file names are lowercase slugs (`[a-z0-9][a-z0-9-]*.md`); daily logs are `YYYY-MM-DD.md`. |
| `path.nested` | error | Records sit directly in their directory, not in a subdirectory. |
| `file.unexpected` | warning | Record directories hold only `.md` records. |
| `contract.missing`, `contract.modified` | warning | `CONTRACT.md` is present and unedited. |

**Every record**

| Code | Severity | Check |
|---|---|---|
| `frontmatter` | error | The file starts with YAML front matter that parses. An impossible date such as `2027-02-30` is a parse error. |
| `type.mismatch` | error | `type` matches the directory: `people/` → `person`, `orgs/` → `org`, `projects/` → `project`, `loops/` → `loop`, `logs/` → `log`. |
| `id.mismatch` | error | `id` equals the path without `.md`, for example `loops/send-scorecard`. |
| `schema` | error | The front matter validates against `contract/schemas/<type>.schema.json`. Each field location gets at most one error. |
| `date.invalid` | error | Quoted `YYYY-MM-DD` values are real calendar dates. |
| `date.order` | warning | `created` is not after `updated`. |
| `link.missing` | error | Link fields (`org`, `owner`, `counterparty`, `people`, `orgs`, `others`, `project`, `parent`, `split_into`, `merged_into`) name existing records. |
| `link.unresolved` | warning | Body links `[[...]]` resolve to a record or another store file. |
| `citation.format` | warning | Citations `[src: ...]` hold artifact IDs such as `em-0193`. |
| `citation.undelivered` | warning | Cited artifacts were actually delivered (only when the delivered set is known; see below). |

**Record types**

| Code | Severity | Check |
|---|---|---|
| `project.current-state` | error | A project's `## Current state` exists and is exactly one prose paragraph (no blank lines, lists or headings) beginning `As of YYYY-MM-DD`. |
| `project.section` | warning | A project also has `## Knowledge` and `## Log`, in the order Current state, Knowledge, Log. |
| `log.bullet`, `log.order` | warning | `## Log` bullets in people, projects and loops read `- YYYY-MM-DD: ...`, oldest first. |
| `evidence.source` | warning | Loop evidence sources use a known artifact prefix (`em`, `ch`, `mt`, `mn`, `dc`, `nt`, `ca`). The schema already requires the artifact-ID shape. |
| `evidence.undelivered` | warning | Evidence sources were actually delivered (only when the delivered set is known). |
| `log.date` | error | A daily log's `date` equals its file name. |
| `log.entry` | warning | Daily-log bullets start with the artifact ID: `- em-0193 (email): ...`. |

**Privacy** (contract rule 11). Every text file in the store is scanned. `[redacted]` and similar placeholders are fine, and so is ordinary prose such as "password reset ticket" or "dial-in details to follow".

| Code | Severity | Finds |
|---|---|---|
| `privacy.secret` | error | A literal secret planted in the inputs (only when the secrets are known). |
| `privacy.join-link` | error | Video-meeting join links (`/j/<digits>`, `meetup-join`, `?pwd=`, meeting-service hosts with a meeting ID) and long meeting IDs. |
| `privacy.passcode` | error | `passcode`, `password`, `pwd=`, `PIN`, `access code` or a one-time code followed by an actual value. |
| `privacy.dial-in` | error | Dial-in numbers (`Dial-in: +1 ...`, `<phone>,,<code>#`). Ordinary phone numbers are not flagged. |
| `privacy.api-key` | error | API keys and tokens: well-known key prefixes (`sk-...`), `api_key: ...` assignments, long hex or random base64 strings. |

Validator messages show only the first few characters of a matched secret.

**Duplicates** (contract rules 1 and 2)

| Code | Severity | Check |
|---|---|---|
| `duplicate.email` | warning | Two people records share an email address, from `email` or an email-shaped alias. |
| `duplicate.name` | warning | Two people records, or two org records, share a full name. |
| `duplicate.project` | warning | Two project records share a name. |

Duplicates are only warnings here, because two people can share a name. The store-integrity grader decides against hidden ground truth.

### Secrets and delivered artifacts

The command line checks only the generic patterns. The Python API can also check against the world's ground truth:

```python
from wcb.contract.validate import validate_store

issues = validate_store(store_dir, secrets=state["secrets"], delivered=set(state["delivered"]))
```

`secrets` and `delivered` come from the gold state for the store's date (`gold/state/<date>.json`; see [formats](formats.md#2-gold-state-goldstatedatejson)). With them, the validator reports any planted secret (`privacy.secret`) and warns about evidence or citations that name artifacts which were never delivered.

## Validating answers

```bash
wcb validate answers .wcb/answers.json --questions .wcb/questions.json
```

This checks each answer against [`contract/answers/answers.schema.json`](../contract/answers/answers.schema.json). With `--questions`, it also checks that every question has an answer of the matching `type`. The questions file can be the agent-visible `.wcb/questions.json` or a gold `gold/questions/<cp>.json`.

| Code | Severity | Meaning |
|---|---|---|
| `answers.json` | error | The file is not valid JSON. |
| `answers.schema` | error | An answer fails the schema or has the wrong `type`. It would score 0. |
| `answers.missing` | error | A question has no answer. |
| `answers.unknown` | warning | An answer's question ID is not in the questions file. |
