import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

import requests

SEARCH_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
API_KEY = "jobboerse-jobsuche"

ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"

EURES_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"

COUNTRY_MAP = {"DEUTSCHLAND": "DE"}

# EURES filters by ISO2 country code server-side, not free-text location, so a
# query's `wo` is only honoured here when it names one of these countries.
# Anything else (a city name, "Remote") falls through unfiltered — see
# Eures.fetch(). Extend this table as more countries are needed.
EURES_COUNTRY_CODES = {
    "spain": "es", "germany": "de", "france": "fr", "netherlands": "nl",
    "italy": "it", "portugal": "pt", "poland": "pl", "austria": "at",
    "belgium": "be", "ireland": "ie", "sweden": "se", "denmark": "dk",
    "finland": "fi",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: Optional[str]) -> Optional[str]:
    if not text:
        return text
    return _TAG_RE.sub(" ", text)


@dataclass
class Job:
    id: str
    source: str
    external_id: str
    title: str
    company: Optional[str]
    location: Optional[str]
    country: Optional[str]
    remote: bool
    published: Optional[str]
    url: str
    description: Optional[str]
    raw: str
    fetched_at: str


@dataclass
class Query:
    was: str
    wo: str
    umkreis: int


class Source(Protocol):
    name: str

    def fetch(self, query: Query) -> list:
        ...


def _make_id(source: str, external_id: str) -> str:
    return hashlib.sha1(f"{source}{external_id}".encode()).hexdigest()[:12]


def _map_record(record: dict, source: str, fetch_config: dict) -> Optional[Job]:
    external_id = record.get("referenznummer")
    if not external_id:
        return None

    title = record.get("stellenangebotsTitel") or record.get("hauptberuf")
    company = record.get("firma")

    locations = record.get("stellenlokationen") or []
    location = None
    country = None
    if locations:
        adresse = locations[0].get("adresse", {})
        location = adresse.get("ort")
        land = adresse.get("land")
        country = COUNTRY_MAP.get(land, land)

    remote = bool(record.get("homeofficemoeglich", False))
    published = record.get("datumErsteVeroeffentlichung")

    external_url = record.get("externeURL")
    url = external_url or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{external_id}"

    return Job(
        id=_make_id(source, external_id),
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        country=country,
        remote=remote,
        published=published,
        url=url,
        description=None,
        raw=json.dumps(record, ensure_ascii=False),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


class Arbeitsagentur:
    name = "arbeitsagentur"

    def __init__(self, fetch_config: Optional[dict] = None):
        self.fetch_config = fetch_config or {}

    def fetch(self, query: Query) -> list:
        size = self.fetch_config.get("size", 100)
        max_pages = self.fetch_config.get("max_pages", 10)
        sleep_seconds = self.fetch_config.get("sleep_seconds", 0.5)
        params_base = {"was": query.was, "size": size}
        if query.wo:
            # BA 400s on wo="" (must be omitted, not empty) and ignores umkreis
            # without wo — so both stay out when there is no location filter,
            # which falls back to a nationwide-Germany search.
            params_base["wo"] = query.wo
            params_base["umkreis"] = query.umkreis
        if "veroeffentlichtseit" in self.fetch_config:
            params_base["veroeffentlichtseit"] = self.fetch_config["veroeffentlichtseit"]
        if "pav" in self.fetch_config:
            params_base["pav"] = str(self.fetch_config["pav"]).lower()

        headers = {"X-API-Key": API_KEY}
        jobs = []
        page = 1
        max_ergebnisse = None

        while page <= max_pages:
            params = dict(params_base, page=page)
            resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if max_ergebnisse is None:
                max_ergebnisse = data.get("maxErgebnisse", 0)

            records = data.get("ergebnisliste") or []
            if not records:
                break

            for record in records:
                job = _map_record(record, self.name, self.fetch_config)
                if job:
                    jobs.append(job)

            if page * size >= max_ergebnisse:
                break

            page += 1
            time.sleep(sleep_seconds)

        return jobs

    def fetch_description(self, external_id: str) -> Optional[str]:
        import base64

        b64 = base64.b64encode(external_id.encode()).decode()
        url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{b64}"
        headers = {"X-API-Key": API_KEY}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("stellenangebotsBeschreibung")


def _map_arbeitnow_record(record: dict, source: str) -> Optional[Job]:
    external_id = record.get("slug")
    if not external_id:
        return None

    title = record.get("title")
    company = record.get("company_name")
    location = record.get("location")
    country = "DE" if location and "germany" in location.lower() else None
    remote = bool(record.get("remote", False))

    created_at = record.get("created_at")
    published = None
    if created_at:
        published = datetime.fromtimestamp(created_at, tz=timezone.utc).date().isoformat()

    return Job(
        id=_make_id(source, external_id),
        source=source,
        external_id=external_id,
        title=title,
        company=company,
        location=location,
        country=country,
        remote=remote,
        published=published,
        url=record.get("url"),
        description=_strip_html(record.get("description")),
        raw=json.dumps(record, ensure_ascii=False),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def _matches_query(job: Job, query: Query) -> bool:
    keywords = [w.lower() for w in query.was.split() if w]
    title = (job.title or "").lower()
    if keywords and not any(kw in title for kw in keywords):
        return False

    wo = (query.wo or "").strip().lower()
    if wo == "remote":
        return job.remote
    if wo:
        # A job's `remote` flag says nothing about which country it's remote
        # *from* — a Germany-only remote role must not match a "Spain" query.
        return wo in (job.location or "").lower()
    return True


class Arbeitnow:
    """Second source, deferred in the original spec. No API key, no server-side
    keyword/location filter — the API returns its full feed per page, so filtering
    against `Query` happens client-side after fetch. Descriptions arrive inline,
    so there is no separate detail call and no description backfill needed.

    The feed is identical regardless of query, so pages are fetched once per run
    and cached — calling fetch() for N searches costs the same handful of page
    requests as calling it once. This also keeps well clear of the API's rate
    limit, which returns plain 429s with no auth to fall back on."""

    name = "arbeitnow"

    def __init__(self, fetch_config: Optional[dict] = None):
        self.fetch_config = fetch_config or {}
        self._cache: Optional[list] = None

    def _fetch_all(self) -> list:
        max_pages = self.fetch_config.get("max_pages", 5)
        sleep_seconds = self.fetch_config.get("sleep_seconds", 0.3)

        jobs = []
        seen_ids = set()
        page = 1
        while page <= max_pages:
            data = self._get_page(page)
            records = data.get("data") or []
            if not records:
                break

            for record in records:
                job = _map_arbeitnow_record(record, self.name)
                if job and job.id not in seen_ids:
                    seen_ids.add(job.id)
                    jobs.append(job)

            if not data.get("links", {}).get("next"):
                break

            page += 1
            time.sleep(sleep_seconds)

        return jobs

    def _get_page(self, page: int) -> dict:
        for attempt in range(3):
            resp = requests.get(ARBEITNOW_URL, params={"page": page}, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 2 * (attempt + 1)))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}

    def fetch(self, query: Query) -> list:
        if self._cache is None:
            self._cache = self._fetch_all()
        return [job for job in self._cache if _matches_query(job, query)]


def _map_eures_record(record: dict, source: str, preferred_country: Optional[str] = None) -> Optional[Job]:
    external_id = record.get("id")
    if not external_id:
        return None

    location_map = record.get("locationMap") or {}
    # A posting can list several eligible countries at once (e.g. a role open
    # across DE/AT/PT/IT/ES). Prefer whichever country the query actually
    # filtered on, so a Spain search doesn't display "DE" for a match that
    # only exists in the results because Spain was one of several options.
    if preferred_country and preferred_country.upper() in location_map:
        country = preferred_country.upper()
    else:
        country = next(iter(location_map), None)
    nuts_codes = [c for c in (location_map.get(country) or []) if c] if country else []
    # No city/region name is returned, only NUTS codes (e.g. "ES61") — there is
    # no lookup table for those yet, so the raw code is stored as-is rather
    # than inventing a human-readable name.
    location = nuts_codes[0] if nuts_codes else country

    creation_date = record.get("creationDate")
    published = None
    if creation_date:
        published = datetime.fromtimestamp(creation_date / 1000, tz=timezone.utc).date().isoformat()

    employer = record.get("employer") or {}

    return Job(
        id=_make_id(source, external_id),
        source=source,
        external_id=external_id,
        title=record.get("title"),
        company=employer.get("name"),
        location=location,
        country=country,
        remote=False,  # EURES exposes no remote/telework flag in this response
        published=published,
        url=f"https://europa.eu/eures/portal/jv-se/jv-details/{external_id}?lang=en",
        description=_strip_html(record.get("description")),
        raw=json.dumps(record, ensure_ascii=False),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


class Eures:
    """Third source: the EU's own public job-mobility portal, aggregating
    vacancies from the public employment services of all EU/EEA member states
    (Arbeitsagentur among them — EURES job IDs decode to the same refnr format,
    so the same posting can legitimately appear via both sources; cross-source
    dedup on dedup_key is not implemented, same known gap as with Arbeitnow).

    The endpoint is undocumented but public, no key required. Location
    filtering is server-side but only at country granularity (ISO2 codes via
    locationCodes) — there is no free-text city search and no remote flag."""

    name = "eures"

    def __init__(self, fetch_config: Optional[dict] = None):
        self.fetch_config = fetch_config or {}

    def fetch(self, query: Query) -> list:
        # The API 400s above 50 ("Too many results per page were requested").
        results_per_page = min(self.fetch_config.get("results_per_page", 50), 50)
        max_pages = self.fetch_config.get("max_pages", 10)
        sleep_seconds = self.fetch_config.get("sleep_seconds", 0.3)

        keywords = [{"keyword": query.was, "specificSearchCode": "EVERYWHERE"}] if query.was else []
        iso2 = EURES_COUNTRY_CODES.get((query.wo or "").strip().lower())
        location_codes = [iso2] if iso2 else []

        jobs = []
        page = 1
        while page <= max_pages:
            body = {
                "resultsPerPage": results_per_page,
                "page": page,
                "sortSearch": "MOST_RECENT",
                "keywords": keywords,
                "publicationPeriod": None,
                "occupationUris": [],
                "skillUris": [],
                "requiredExperienceCodes": [],
                "positionScheduleCodes": [],
                "sectorCodes": [],
                "educationAndQualificationLevelCodes": [],
                "positionOfferingCodes": [],
                "locationCodes": location_codes,
                "euresFlagCodes": [],
                "otherBenefitsCodes": [],
                "requiredLanguages": [],
                "minNumberPost": None,
                "sessionId": "job-hunter-apaif",
                "requestLanguage": "en",
            }
            data = self._post(body)
            records = data.get("jvs") or []
            if not records:
                break

            for record in records:
                job = _map_eures_record(record, self.name, preferred_country=iso2)
                if job:
                    jobs.append(job)

            total = data.get("numberRecords", 0)
            if page * results_per_page >= total:
                break

            page += 1
            time.sleep(sleep_seconds)

        return jobs

    def _post(self, body: dict) -> dict:
        for attempt in range(3):
            resp = requests.post(EURES_URL, json=body, timeout=15)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 2 * (attempt + 1)))
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        resp.raise_for_status()
        return {}


def _parse_sample_file(path: str, source: str = "arbeitsagentur") -> list:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("ergebnisliste") or []
    jobs = []
    for record in records:
        job = _map_record(record, source, {})
        if job:
            jobs.append(job)
    return jobs


if __name__ == "__main__":
    jobs = _parse_sample_file("samples/ba_search.json")
    print(f"parsed {len(jobs)} jobs from sample file")
    for job in jobs[:20]:
        print(f"  {job.id}  {job.title!r}  {job.company!r}  {job.location}  remote={job.remote}")
