import re
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
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
"""


def _slug(value: str) -> str:
    value = (value or "").lower()
    for junk in ["(m/w/d)", "(m/f/d)", "(w/m/d)", "(f/m/d)", "m/w/d", "m/f/d", "w/m/d",
                 "f/m/d", "*innen", "(all genders)", "(all gender)"]:
        value = value.replace(junk, "")
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def dedup_key(company: str, title: str, location: str) -> str:
    return f"{_slug(company)}|{_slug(title)}|{_slug(location)}"


def init(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def upsert(conn: sqlite3.Connection, jobs: list) -> int:
    now = datetime.now(timezone.utc).isoformat()
    new_count = 0
    for job in jobs:
        key = dedup_key(job.company, job.title, job.location)
        cur = conn.execute("SELECT id FROM jobs WHERE id = ?", (job.id,))
        exists = cur.fetchone() is not None
        if not exists:
            new_count += 1
        conn.execute(
            """
            INSERT INTO jobs (id, source, external_id, title, company, location, remote,
                               published, url, description, raw, dedup_key, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                last_seen = excluded.last_seen,
                title = excluded.title,
                company = excluded.company,
                location = excluded.location,
                remote = excluded.remote,
                published = excluded.published,
                url = excluded.url,
                raw = excluded.raw,
                dedup_key = excluded.dedup_key
            """,
            (job.id, job.source, job.external_id, job.title, job.company, job.location,
             int(job.remote), job.published, job.url, job.description, job.raw, key, now, now),
        )
    conn.commit()
    return new_count


def get_new(conn: sqlite3.Connection, day: str) -> list:
    cur = conn.execute("SELECT * FROM jobs WHERE date(first_seen) = date(?)", (day,))
    return cur.fetchall()


def needs_description(conn: sqlite3.Connection) -> list:
    cur = conn.execute("SELECT id, external_id, source FROM jobs WHERE description IS NULL")
    return cur.fetchall()


def set_description(conn: sqlite3.Connection, job_id: str, description: str) -> None:
    conn.execute("UPDATE jobs SET description = ? WHERE id = ?", (description, job_id))
    conn.commit()
