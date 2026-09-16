import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sources import Job, _resolve_country

RECENCY_DAYS = 3
RECENCY_BONUS = 5


@dataclass
class Match:
    score: float
    reasons: list


def _contains(text: Optional[str], term: str) -> bool:
    pattern = r"\b" + re.escape(term.lower()) + r"\b"
    return re.search(pattern, (text or "").lower()) is not None


def _location_match(job: Job, locations: list) -> Optional[str]:
    """Returns the matched location label for the reasons list, or None."""
    for loc in locations:
        loc = (loc or "").strip()
        if not loc:
            continue
        if loc.lower() == "remote":
            if job.remote:
                return "Remote"
            continue
        code = _resolve_country(loc)
        if code:
            if job.country and job.country.upper() == code.upper():
                return loc
        elif loc.lower() in (job.location or "").lower():
            return loc
    return None


def _is_recent(published: Optional[str]) -> bool:
    if not published:
        return False
    try:
        published_date = date.fromisoformat(published)
    except ValueError:
        return False
    return (datetime.now(timezone.utc).date() - published_date).days <= RECENCY_DAYS


def score_job(job: Job, profile: dict) -> Optional[Match]:
    title = job.title or ""
    description = job.description or ""

    for term in profile.get("exclude", []):
        if _contains(title, term):
            return None

    for term in profile.get("must_have", []):
        if not (_contains(title, term) or _contains(description, term)):
            return None

    points = 0.0
    max_possible = 0.0
    reasons = []

    for term, weight in profile.get("nice_to_have", {}).items():
        max_possible += weight * 3
        if _contains(title, term):
            points += weight * 3
            reasons.append(f"title: {term}")
        elif _contains(description, term):
            points += weight * 1
            reasons.append(f"description: {term}")

    locations = profile.get("locations", [])
    if locations:
        max_possible += 10
        matched = _location_match(job, locations)
        if matched:
            points += 10
            reasons.append(f"location: {matched}")

    remote_bonus = profile.get("remote_bonus", 0)
    if remote_bonus:
        max_possible += remote_bonus
        if job.remote:
            points += remote_bonus
            reasons.append("remote")

    max_possible += RECENCY_BONUS
    if _is_recent(job.published):
        points += RECENCY_BONUS
        reasons.append(f"posted within {RECENCY_DAYS} days")

    score = round(100 * points / max_possible, 1) if max_possible else 0.0
    return Match(score=score, reasons=reasons)


if __name__ == "__main__":
    import yaml

    from sources import _parse_sample_file

    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    profile = config.get("profile", {})

    jobs = _parse_sample_file("samples/ba_search.json")
    scored = []
    for job in jobs:
        match = score_job(job, profile)
        if match:
            scored.append((match.score, job, match.reasons))
    scored.sort(key=lambda t: t[0], reverse=True)

    print(f"{len(scored)}/{len(jobs)} jobs passed hard filters\n")
    for s, job, reasons in scored[:10]:
        print(f"{s:5.1f}  {job.title!r}  {job.company!r}")
        print(f"       {', '.join(reasons) if reasons else '(no matches)'}")
