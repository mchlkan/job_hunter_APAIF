import os

import store
from sources import Job


def _job(**overrides):
    defaults = dict(
        id="abc123",
        source="arbeitsagentur",
        external_id="ext1",
        title="Data Analyst",
        company="Acme GmbH",
        location="Berlin",
        country="DE",
        remote=False,
        published="2026-01-01",
        url="https://example.com/job",
        description="",
        raw="{}",
        fetched_at="2026-01-01T00:00:00+00:00",
    )
    defaults.update(overrides)
    return Job(**defaults)


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
