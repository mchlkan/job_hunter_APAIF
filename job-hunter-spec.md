# Job Hunter — Build Spec

**Course:** Applied Programming · **Author:** Vanessa Weiss · **Date:** 2026-09-09

A small, dependable tool that collects job postings once a day, scores them against a
personal profile, and produces a digest of what is new and worth reading.

Two components, deliberately nothing more:

1. **Collection** — pull postings from one API, normalise them to a single JSON schema, store them.
2. **Match engine** — score each posting against a profile, surface the top ones.

---

## 1. Platform decision

**Primary source: Bundesagentur für Arbeit — Jobsuche API.**

```
GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
Header: X-API-Key: jobboerse-jobsuche
```

Why this one, over StepStone, Indeed, Adzuna, or ATS endpoints:

| Criterion | Verdict |
|---|---|
| Cost | Free, no account, no billing, no quota to run out mid-project |
| Auth | A single fixed header. No OAuth, no key rotation, no secret to leak in a repo |
| Legality | Official public API of a federal agency. No ToS grey zone, no bot detection to fight |
| Coverage | The largest job database in Germany (~1M postings), incl. EU roles posted to the German market |
| Format | JSON out of the box — no HTML parsing, no BeautifulSoup, no breakage when a site redesigns |
| Filters | Location + radius, keyword, publication age, contract type (remote is client-side — see below) |

The alternatives were rejected for concrete reasons, not preference: Indeed retired its
Publisher API; StepStone has no public search API and active bot protection; Adzuna's free
tier is ~1,000 calls/month, which a daily job barely fits; Greenhouse and the other ATS
endpoints have no global search — they require a hand-curated list of company tokens.

**Deferred, not discarded:** [Arbeitnow](https://www.arbeitnow.com/api/job-board-api)
(free, no key, EU-wide, English-language postings). The `Source` interface in §3 exists so
this can be added as a second adapter of roughly 30 lines — *after* the core works
end to end, not before.

### Endpoints used

| Purpose | Call |
|---|---|
| Search | `/pc/v6/jobs?was={kw}&wo={city}&umkreis={km}&size=100&page={n}&veroeffentlichtseit=7` |
| Detail | `/pc/v4/jobdetails/{base64(referenznummer)}` — needed for the full description text |

The detail path takes the **base64-encoded** reference number, not the raw one. Passing the
raw `referenznummer` returns 404.

Useful params, all verified against live responses: `angebotsart=1` (regular employment),
`befristung=2` (permanent), `veroeffentlichtseit=0..100` (days since publication),
`pav=false` (exclude private recruiters — cuts a lot of noise). Default `size` is 25, so
pass it explicitly.

**No server-side remote filter.** The old `arbeitszeit=ho` returns zero results on v6, and
`homeofficemoeglich=true` as a query param is silently ignored (it returns the unfiltered
count). Filter on the `homeofficemoeglich` boolean in the response instead — client-side,
in `sources.py`.

> **Version history — do not revert.** The original spec targeted `/pc/v4/app/jobs`, which
> now returns **403 on every request** (1-byte body, no auth challenge — retired, not a key
> problem). `/pc/v2/jobs` is likewise 403. `/pc/v6/jobs` is the live endpoint and the field
> names changed with it (see §4). If a tutorial or older example shows `v4/app`, it predates
> this change.

> **Verified before coding.** Real responses are saved to `samples/ba_search.json` and
> `samples/ba_detail.json`. Build the parser against those files, not against assumptions.
> Note that the search list gives title, employer, and location; the full description
> requires the detail call.

---

## 2. Data flow

```
   fetch          normalise         dedup           score          report
BA API  ──▶  raw JSON  ──▶  Job objects  ──▶  SQLite  ──▶  ranked  ──▶  digest.md
                                              (new only)
```

One daily run. Everything is idempotent — running it twice on the same day changes nothing
and alerts nothing twice.

---

## 3. Project structure

Flat and boring on purpose. Six files.

```
job-hunter/
├── config.yaml          profile + search queries
├── sources.py           API adapters → list[Job]
├── store.py             SQLite: upsert, "what's new", mark notified
├── score.py             Job × Profile → score + reasons
├── report.py            ranked jobs → markdown digest
├── run.py               the pipeline, ~40 lines
├── samples/             real API responses, committed — the parser's fixtures
├── data/jobs.db
└── out/digest-2026-09-09.md
```

`sources.py` defines the only abstraction in the project:

```python
class Source(Protocol):
    name: str
    def fetch(self, query: Query) -> list[Job]: ...
```

One implementation now (`Arbeitsagentur`). A second later costs one file, no refactor.

---

## 4. Normalised job schema

Every source maps into this. This is the contract between collection and matching — get it
right and the two halves can be developed independently.

```json
{
  "id":          "a3f9c1e8b2d4",
  "source":      "arbeitsagentur",
  "external_id": "10000-1198765432-S",
  "title":       "Data Analyst (m/w/d)",
  "company":     "Beispiel GmbH",
  "location":    "Berlin",
  "country":     "DE",
  "remote":      false,
  "published":   "2026-09-07",
  "url":         "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1198765432-S",
  "description": "Wir suchen zum nächstmöglichen Zeitpunkt...",
  "fetched_at":  "2026-09-09T07:00:00+02:00"
}
```

**`id`** = first 12 hex chars of `sha1(source + external_id)`. Stable across runs, so
re-fetching the same posting updates rather than duplicates it.

**Field mapping (Arbeitsagentur v6 → schema).** Verified against a live response — these are
*not* the v4 names, all of which changed:

| Schema | API field (v6) |
|---|---|
| `external_id` | `referenznummer` |
| `title` | `stellenangebotsTitel`, fallback `hauptberuf` |
| `company` | `firma` |
| `location` | `stellenlokationen[0].adresse.ort` |
| `country` | `stellenlokationen[0].adresse.land` — full name (`"DEUTSCHLAND"`), map to ISO `"DE"` |
| `remote` | `homeofficemoeglich` (bool, absent on ~⅓ of records → treat as false) |
| `published` | `datumErsteVeroeffentlichung` |
| `url` | `externeURL` (capital URL), else construct from `referenznummer` |
| `description` | `stellenangebotsBeschreibung` (detail call — the one name that survived) |

Search results are under **`ergebnisliste`**, not `stellenangebote`. The envelope is
`{ergebnisliste, maxErgebnisse, page, size, woOutput, facetten}`.

`externeURL` is present on only ~20% of records, so the constructed-URL fallback is the
main path, not the exception — check that the URL you build actually resolves before
trusting it in the digest.

Keep the untouched API response in a `raw` JSON column. Storage is free, and when a mapping
turns out wrong in week 3 you can re-derive without re-fetching everything.

---

## 5. Storage

One SQLite file, one table. No ORM, no migrations, no Postgres.

```sql
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title       TEXT NOT NULL,
    company     TEXT,
    location    TEXT,
    remote      INTEGER DEFAULT 0,
    published   TEXT,
    url         TEXT,
    description TEXT,
    raw         TEXT,
    dedup_key   TEXT,
    score       REAL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    notified    INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_dedup ON jobs(dedup_key);
```

Write with `INSERT ... ON CONFLICT(id) DO UPDATE SET last_seen = ...`, which makes the
whole run safely repeatable.

`first_seen` is what makes alerting work — and it quietly builds a longitudinal dataset, so
the market-analysis angle stays open later without any rework.

**Deduplication.** The same role appears twice with slightly different titles. One
normalised key catches most of it:

```
dedup_key = slug(company) + "|" + slug(title) + "|" + slug(location)
```

where `slug()` lowercases, strips `(m/w/d)`, `m/f/d`, `*innen`, punctuation, and collapses
whitespace. Exact-match on that key is enough. Fuzzy matching is a nice extension for the
report if you have time — it is not needed for the thing to work.

---

## 6. Match engine

Transparent and rule-based. Every score comes with the reasons that produced it, which
matters more for a course write-up than a marginally better ranking would.

**Profile (`config.yaml`):**

```yaml
profile:
  must_have:   ["python", "sql"]              # absent → rejected outright
  nice_to_have:                               # keyword: weight
    "power bi":   3
    "tableau":    3
    "dbt":        2
    "werkstudent": 4
    "praktikum":   2
    english:      2
  exclude:     ["senior", "lead", "head of", "10 jahre"]
  locations:   ["Berlin", "Hamburg", "München", "Remote"]
  remote_bonus: 5

searches:
  - was: "Data Analyst"
    wo: "Berlin"
    umkreis: 30
  - was: "Business Intelligence"
    wo: "Berlin"
    umkreis: 30
  - was: "Werkstudent Data"
    wo: "Berlin"
    umkreis: 30

alert_threshold: 40
```

**Algorithm:**

```
1. HARD FILTERS  — any exclude term in title      → drop
                 — any must_have missing from text → drop

2. POINTS        — nice_to_have hit in title       → weight × 3
                 — nice_to_have hit in description → weight × 1
                 — location in profile.locations   → +10
                 — remote == true                  → +remote_bonus
                 — published within 3 days         → +5

3. NORMALISE     score = 100 × points / max_possible_points

4. ALERT         new (first_seen == today) AND score >= alert_threshold
```

Match on lowercased text with word boundaries (`\bsql\b`), so "SQL" does not match
"NoSQLite" and "R" does not match every second word.

Return reasons alongside the score:

```python
Match(score=72.0, reasons=["title: python", "title: sql", "location: Berlin", "posted 1d ago"])
```

Those reasons go straight into the digest. When a bad match shows up you can see *why*,
which is how the weights get tuned — and it is the honest answer to "how does your
ranking work?" in the presentation.

---

## 7. Output

`out/digest-YYYY-MM-DD.md`, and the same content printed to the terminal.

```markdown
# Job digest — 2026-09-09
14 new postings · 5 above threshold

## 1. Data Analyst (m/w/d) — 78
**Beispiel GmbH** · Berlin · posted 1 day ago
Matched: python, sql, power bi, location
https://www.arbeitsagentur.de/jobsuche/jobdetail/...

## 2. ...
```

Markdown first. Email or a Notion page is a later addition and does not change anything
upstream of `report.py`.

---

## 8. Build order

Each step ends with something that runs. Do not start the next one until the current one
works from the command line.

| # | Step | Done when |
|---|---|---|
| 1 | ~~One `requests.get` to the search endpoint, dump to `samples/`~~ — **done**, see `samples/` | You have a real JSON file to look at |
| 2 | `sources.py`: parse that file into `Job` objects | `python sources.py` prints 20 jobs |
| 3 | `store.py`: schema + upsert + `get_new()` | Running twice inserts nothing the second time |
| 4 | `run.py`: fetch → store, loop over `searches` | The DB fills up with real postings |
| 5 | Add the detail call for descriptions (base64 the refnr) | `description` is populated, not null |
| 6 | `score.py`: filters + points + reasons | Scores look sane on 20 real jobs |
| 7 | `report.py`: markdown digest | A digest file you would actually read |
| 8 | Tune weights against real output | Top 5 are genuinely the best 5 |
| 9 | Schedule daily (`cron`, or GitHub Actions) | It runs without you |

Steps 1–4 are the collection deliverable. Steps 6–8 are the match engine. Step 9 turns it
from a script into a tool.

---

## 9. Scope discipline

Deliberately **out** of scope for v1 — each is a defensible sentence in the write-up, not
an oversight:

- Multiple sources (interface is ready; adding one is a later commit)
- Embeddings / semantic similarity — keyword scoring with visible reasons is more
  explainable and, on a few hundred postings, not obviously worse
- A web UI — markdown reads fine and costs nothing to maintain
- CV parsing, auto-apply, salary prediction

**Risks worth naming:**

| Risk | Mitigation |
|---|---|
| API changes its response shape | **Already happened once** — v4 retired, every field renamed. `raw` column keeps originals; parser is one file; `samples/` are the regression fixtures |
| Rate limiting | One run/day, `size=100`, ~0.5s sleep between calls |
| German-language descriptions | Keyword lists carry both languages (`erfahrung`/`experience`) |
| Too few results | Real datapoint: "Data Analyst" + Berlin + 30km = **37 total**. Broaden `umkreis`, add search queries, lower threshold |

---

## Sources

- [bundesAPI/jobsuche-api](https://github.com/bundesAPI/jobsuche-api) — endpoints, parameters, working example
- [Arbeitnow Job Board API](https://www.arbeitnow.com/blog/job-board-api) — the deferred second source
- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html) — considered, rejected (no global search)
