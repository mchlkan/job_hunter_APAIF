import store


def _job(id, title, company="Acme", location="Berlin", source="arbeitsagentur",
         remote=False, score=None, published="2026-01-01"):
    return type("Job", (), dict(
        id=id, source=source, external_id=id, title=title, company=company,
        location=location, remote=remote, published=published, url=None,
        description=None, raw="{}", score=score,
    ))()


def _seed(conn, jobs):
    store.upsert(conn, jobs)
    for job in jobs:
        if getattr(job, "score", None) is not None:
            conn.execute("UPDATE jobs SET score = ? WHERE id = ?", (job.score, job.id))
    conn.commit()


def test_list_jobs_filters_by_source(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    _seed(conn, [
        _job("a", "Data Analyst", source="arbeitsagentur"),
        _job("b", "Data Analyst", source="eures"),
    ])
    rows = store.list_jobs(conn, source="eures")
    assert [r["id"] for r in rows] == ["b"]


def test_list_jobs_filters_by_remote(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    _seed(conn, [
        _job("a", "Remote Analyst", remote=True),
        _job("b", "Onsite Analyst", remote=False),
    ])
    rows = store.list_jobs(conn, remote=True)
    assert [r["id"] for r in rows] == ["a"]


def test_list_jobs_filters_by_query_matches_title_or_company(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    _seed(conn, [
        _job("a", "Data Analyst", company="Acme"),
        _job("b", "Business Analyst", company="Widgets"),
    ])
    assert [r["id"] for r in store.list_jobs(conn, q="Data")] == ["a"]
    assert [r["id"] for r in store.list_jobs(conn, q="Widgets")] == ["b"]


def test_list_jobs_orders_scored_first_then_unscored(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    _seed(conn, [
        _job("low", "Job", score=10),
        _job("unscored", "Job", score=None),
        _job("high", "Job", score=90),
    ])
    rows = store.list_jobs(conn)
    assert [r["id"] for r in rows] == ["high", "low", "unscored"]


def test_list_jobs_min_score_excludes_unscored(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    _seed(conn, [
        _job("low", "Job", score=10),
        _job("unscored", "Job", score=None),
        _job("high", "Job", score=90),
    ])
    rows = store.list_jobs(conn, min_score=40)
    assert [r["id"] for r in rows] == ["high"]
