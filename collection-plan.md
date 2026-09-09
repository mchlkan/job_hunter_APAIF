# Data Collection — Build Plan

**Companion to:** [`job-hunter-spec.md`](job-hunter-spec.md) · **Date:** 2026-09-09

Covers steps 2–5 of the spec's build order: the pipeline that goes from an API call to
populated rows in `data/jobs.db`. Step 1 (real sample responses) is already done and
committed under `samples/`.

Scoring, reporting and scheduling are **out of scope here** — they read the table this plan
fills, and nothing in them changes how collection works.

---

## 0. What is already verified

Everything below was checked against live API responses on 2026-09-09, not assumed. Build
against these facts; if one turns out wrong, the sample files are the tiebreaker.

| Fact | Value |
|---|---|
| Search endpoint | `GET /jobboerse/jobsuche-service/pc/v6/jobs` (v4/app and v2 return 403) |
| Auth | `X-API-Key: jobboerse-jobsuche` — nothing else |
| Results array | `ergebnisliste` (not `stellenangebote`) |
| Detail endpoint | `/pc/v4/jobdetails/{base64(referenznummer)}` — raw refnr 404s |
| Description field | `stellenangebotsBeschreibung`, detail response only |
| Page size | Default 25; `size=100` and `size=200` both honoured |
| Paging | `page=1` is the first page; `page=2` returns the next block correctly |
| Constructed URL | `https://www.arbeitsagentur.de/jobsuche/jobdetail/{referenznummer}` → **HTTP 200** |
| Remote filter | No server-side option — filter client-side on `homeofficemoeglich` |

Two numbers worth carrying into the config: `"Data Analyst"` + Berlin + 30km returns **37**
results, while the broader `"Data"` + Berlin + 50km returns **810**. Query breadth, not the
API, is what decides whether the digest is thin.

---

## 1. Environment

The machine has **Python 3.9.6** (macOS system Python) and neither `requests` nor `PyYAML`
installed. There is no newer interpreter present.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install requests pyyaml
pip freeze > requirements.txt
```

3.9 has one consequence for the code: **`X | None` union syntax is 3.10+**, so use
`Optional[str]` from `typing`. `list[Job]` is fine (PEP 585 landed in 3.9), so the spec's
`Source` protocol works as written.

Add `.venv/`, `data/`, `out/` and `.DS_Store` to `.gitignore`. `samples/` stays tracked —
those files are the parser's fixtures.

---

## 2. `config.yaml`

Written first because both `sources.py` and `run.py` read it. Only the collection-relevant
half is needed now; the `profile:` block from spec §6 can be added later without touching
this code.

```yaml
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

fetch:
  size: 100
  veroeffentlichtseit: 7      # days back; keeps daily runs cheap
  pav: false                  # drop private recruiters
  max_pages: 10               # hard stop, so a broad query can't run away
  sleep_seconds: 0.5
```

**Done when:** `yaml.safe_load` returns the dict and `run.py` can iterate `searches`.

---

## 3. `sources.py`

The only abstraction in the project, plus one implementation.

**Contract:**

```python
class Source(Protocol):
    name: str
    def fetch(self, query: Query) -> list[Job]: ...
```

`Job` is a `@dataclass` mirroring spec §4 exactly — `id`, `source`, `external_id`, `title`,
`company`, `location`, `country`, `remote`, `published`, `url`, `description`, `raw`,
`fetched_at`.

**`Arbeitsagentur.fetch()` does, in order:**

1. `GET /pc/v6/jobs` with the query params, `page` starting at 1.
2. Read `ergebnisliste`; stop when it is empty, when `page * size >= maxErgebnisse`, or when
   `max_pages` is hit — whichever comes first.
3. Map each record with the §4 table. Guard every optional field: `homeofficemoeglich`,
   `externeURL` and `arbeitgeberKundennummerHash` are each absent on a meaningful fraction of
   records. `stellenlokationen` is a list — take `[0]`, but do not assume it is non-empty.
4. `id = sha1(f"{source}{external_id}".encode()).hexdigest()[:12]`.
5. `url = externeURL or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{referenznummer}"`
   — the fallback is the common path, not the exception (~80% of records).
6. `country`: map `"DEUTSCHLAND"` → `"DE"`; pass anything else through unchanged.
7. Keep the untouched record as `raw` (JSON string).
8. `description` stays `None` here. It is filled in step 5 below.
9. `time.sleep(fetch.sleep_seconds)` between page requests.

Build this against `samples/ba_search.json` first — parse the file, no network. Only point it
at the live endpoint once the parse is clean.

**Done when:** `python sources.py` parses the sample file and prints 20+ `Job` objects with
no field missing except `description`.

---

## 4. `store.py`

SQLite exactly as spec §5 defines it, including the `score` and `dedup_key` columns — they
stay NULL for now, and having them means the scoring step needs no migration.

**Four functions, nothing more:**

| Function | Behaviour |
|---|---|
| `init(path)` | `CREATE TABLE IF NOT EXISTS` + the `idx_dedup` index |
| `upsert(jobs)` | `INSERT … ON CONFLICT(id) DO UPDATE SET last_seen=…`; sets `first_seen` only on insert |
| `get_new(day)` | rows where `first_seen` falls on `day` |
| `needs_description()` | rows where `description IS NULL` — drives step 5 |

`dedup_key` is computed on write (`slug(company)|slug(title)|slug(location)`) even though
nothing reads it yet; it is one line and it keeps the column honest.

**Done when:** running `run.py` twice in a row inserts nothing the second time and leaves
`first_seen` untouched, while `last_seen` moves. This is the test that proves idempotency —
do not move on without it.

---

## 5. `run.py`

The pipeline, and it should stay near 40 lines.

```
load config
init db
for each search in config.searches:
    jobs = Arbeitsagentur().fetch(query)
    store.upsert(jobs)
for job in store.needs_description():
    fetch /pc/v4/jobdetails/{base64(job.external_id)}
    store description
    sleep
print: N fetched, M new today
```

The description backfill is a **separate pass**, not part of `fetch()`. That way a failed
detail call costs one description rather than a whole search, and re-running picks up exactly
what is still missing.

Base64 the reference number with `base64.b64encode(refnr.encode()).decode()`. Treat a 404 as
"skip this one and log it", not as a crash — postings expire between the search and the
detail call.

**Done when:** the DB fills with real postings across all three searches, and `description`
is populated rather than NULL.

---

## 6. Verification

In order. Each one catches a different failure.

1. **Parse:** `sources.py` against `samples/ba_search.json` — no network, no surprises.
2. **Idempotency:** run `run.py` twice; second run inserts 0 rows.
3. **Coverage:** `SELECT COUNT(*) FROM jobs WHERE description IS NULL` → 0 after a full run.
4. **URLs resolve:** spot-check five stored URLs return 200, since most are constructed.
5. **Field sanity:** `SELECT COUNT(*) FROM jobs WHERE title IS NULL OR company IS NULL` → 0.

---

## 7. Risks specific to this step

| Risk | Handling |
|---|---|
| A field absent on some records crashes the mapper | Guard every optional field; the sample file has records missing `externeURL`, `homeofficemoeglich` and `homeofficetyp` — test against those specifically |
| Detail call 404s on an expired posting | Catch, log, leave `description` NULL, move on — the next run retries it |
| A broad query pages forever | `max_pages` in config, plus the `maxErgebnisse` bound |
| Rate limiting | 0.5s between calls, one run/day; no evidence of a limit yet, but the detail pass is the call-heavy part |
| API shape shifts again | `raw` column keeps originals; `samples/` are the regression fixtures |

---

## 8. Not in this step

Scoring, the digest, cron/GitHub Actions, and the second source adapter. The `Source`
protocol is what keeps that last one to a single new file — but it stays unwritten until
this pipeline runs end to end.
