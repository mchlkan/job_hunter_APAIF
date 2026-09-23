import store
from conftest import make_job as _job


def test_set_score_persists_score_and_reasons(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [_job()])

    store.set_score(conn, "abc123", 42.5, ["title: python", "remote"])

    row = conn.execute("SELECT * FROM jobs WHERE id = ?", ("abc123",)).fetchone()
    assert row["score"] == 42.5
    assert store.get_match_reasons(row) == ["title: python", "remote"]


def test_set_score_defaults_to_empty_reasons(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [_job()])

    store.set_score(conn, "abc123", 0.0)

    row = conn.execute("SELECT * FROM jobs WHERE id = ?", ("abc123",)).fetchone()
    assert store.get_match_reasons(row) == []


def test_country_and_match_reasons_migration_on_existing_db(tmp_path):
    db_path = str(tmp_path / "jobs.db")
    conn = store.init(db_path)
    conn.close()

    # simulate an older DB created before country/match_reasons existed
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("ALTER TABLE jobs RENAME TO jobs_new")
    conn.execute("""
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY, source TEXT, external_id TEXT, title TEXT,
            company TEXT, location TEXT, remote INTEGER, published TEXT,
            url TEXT, description TEXT, raw TEXT, dedup_key TEXT, score REAL,
            first_seen TEXT, last_seen TEXT, notified INTEGER
        )
    """)
    conn.execute("DROP TABLE jobs_new")
    conn.commit()
    conn.close()

    conn = store.init(db_path)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert "country" in cols
    assert "match_reasons" in cols


def test_list_jobs_filters_by_source(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [
        _job(id="a", title="Data Analyst", source="arbeitsagentur"),
        _job(id="b", title="Data Analyst", source="eures"),
    ])
    rows = store.list_jobs(conn, source="eures")
    assert [r["id"] for r in rows] == ["b"]


def test_list_jobs_filters_by_remote(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [
        _job(id="a", title="Remote Analyst", remote=True),
        _job(id="b", title="Onsite Analyst", remote=False),
    ])
    rows = store.list_jobs(conn, remote=True)
    assert [r["id"] for r in rows] == ["a"]


def test_list_jobs_filters_by_query_matches_title_or_company(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [
        _job(id="a", title="Data Analyst", company="Acme"),
        _job(id="b", title="Business Analyst", company="Widgets"),
    ])
    assert [r["id"] for r in store.list_jobs(conn, q="Data")] == ["a"]
    assert [r["id"] for r in store.list_jobs(conn, q="Widgets")] == ["b"]


def test_list_jobs_orders_scored_first_then_unscored(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [
        _job(id="low", title="Job"),
        _job(id="unscored", title="Job"),
        _job(id="high", title="Job"),
    ])
    store.set_score(conn, "low", 10)
    store.set_score(conn, "high", 90)

    rows = store.list_jobs(conn)
    assert [r["id"] for r in rows] == ["high", "low", "unscored"]


def test_list_jobs_min_score_excludes_unscored(tmp_path):
    conn = store.init(str(tmp_path / "jobs.db"))
    store.upsert(conn, [
        _job(id="low", title="Job"),
        _job(id="unscored", title="Job"),
        _job(id="high", title="Job"),
    ])
    store.set_score(conn, "low", 10)
    store.set_score(conn, "high", 90)

    rows = store.list_jobs(conn, min_score=40)
    assert [r["id"] for r in rows] == ["high"]
