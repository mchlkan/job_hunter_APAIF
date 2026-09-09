import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

import requests

SEARCH_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
API_KEY = "jobboerse-jobsuche"

COUNTRY_MAP = {"DEUTSCHLAND": "DE"}


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
        params_base = {
            "was": query.was,
            "wo": query.wo,
            "umkreis": query.umkreis,
            "size": size,
        }
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
