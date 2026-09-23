from datetime import datetime, timedelta, timezone

from conftest import make_job as _job
from score import score_job


def test_exclude_drops_job_on_title_match():
    job = _job(title="Senior Data Analyst")
    match = score_job(job, {"exclude": ["senior"]})
    assert match is None


def test_exclude_ignores_description():
    job = _job(title="Data Analyst", description="works with a senior team")
    match = score_job(job, {"exclude": ["senior"]})
    assert match is not None


def test_must_have_drops_job_when_missing_everywhere():
    job = _job(title="Data Analyst", description="Excel and reporting")
    match = score_job(job, {"must_have": ["python"]})
    assert match is None


def test_must_have_passes_when_found_in_description():
    job = _job(title="Data Analyst", description="Requires Python and SQL")
    match = score_job(job, {"must_have": ["python"]})
    assert match is not None


def test_word_boundary_no_false_positive():
    job = _job(title="Data Analyst", description="Experience with NoSQLite databases")
    match = score_job(job, {"must_have": ["sql"]})
    assert match is None


def test_nice_to_have_title_weighs_more_than_description():
    title_job = _job(title="Python Data Analyst", description="")
    desc_job = _job(title="Data Analyst", description="Python is a plus")

    profile = {"nice_to_have": {"python": 2}}
    title_match = score_job(title_job, profile)
    desc_match = score_job(desc_job, profile)

    assert title_match.score > desc_match.score
    assert "title: python" in title_match.reasons
    assert "description: python" in desc_match.reasons


def test_nice_to_have_no_match_scores_zero_without_other_bonuses():
    job = _job(title="Data Analyst", description="", published=None, remote=False)
    match = score_job(job, {"nice_to_have": {"python": 2}})
    assert match.score == 0.0
    assert match.reasons == []


def test_location_bonus_matches_country():
    job = _job(country="DE")
    match = score_job(job, {"locations": ["Germany"]})
    assert any(r.startswith("location:") for r in match.reasons)


def test_location_bonus_matches_remote():
    job = _job(remote=True)
    match = score_job(job, {"locations": ["Remote"]})
    assert "location: Remote" in match.reasons


def test_location_bonus_falls_back_to_city_substring():
    job = _job(location="Berlin, Germany", country=None)
    match = score_job(job, {"locations": ["Berlin"]})
    assert any(r.startswith("location:") for r in match.reasons)


def test_location_bonus_absent_when_no_match():
    job = _job(location="Munich", country="DE")
    match = score_job(job, {"locations": ["Spain"]})
    assert not any(r.startswith("location:") for r in match.reasons)


def test_remote_bonus_applied():
    job = _job(remote=True)
    match = score_job(job, {"remote_bonus": 5})
    assert "remote" in match.reasons


def test_recency_bonus_within_window():
    recent = datetime.now(timezone.utc).date().isoformat()
    job = _job(published=recent)
    match = score_job(job, {})
    assert any(r.startswith("posted within") for r in match.reasons)


def test_recency_bonus_absent_when_old():
    old = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
    job = _job(published=old)
    match = score_job(job, {})
    assert not any(r.startswith("posted within") for r in match.reasons)


def test_max_possible_scales_with_profile_size():
    job = _job(title="Python SQL Analyst", published=None)
    small_profile = {"nice_to_have": {"python": 2}}
    large_profile = {"nice_to_have": {"python": 2, "sql": 2, "docker": 2, "aws": 2}}

    small_match = score_job(job, small_profile)
    large_match = score_job(job, large_profile)

    # same absolute points earned (python+sql hit in both), but normalized
    # against a bigger ceiling in the larger profile -> lower score
    assert large_match.score < small_match.score
