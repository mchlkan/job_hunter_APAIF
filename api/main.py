import json
import os
import sys
from typing import Optional

# Allow `python -m uvicorn api.main:app` from the project root, and also
# `python api/main.py` directly, without needing the package installed.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import store
from profiles.worker import UPLOADS_DIR, process_pdf, update_profile_block

CONFIG_PATH = "config.yaml"

app = FastAPI(title="job-hunter dashboard API")

# The frontend is a separate server (vite dev on :8080, or the built Node
# server in production — see frosted-editorial-job-app-source/), not served
# by this app, so cross-origin requests need explicit allowance. Comma-separated
# so a real deployment can override it without a code change — stripped per
# entry since CORS does an exact string match and a stray space after the
# comma (a natural way to type the list) would otherwise silently reject it.
_allowed_origins = [
    origin.strip() for origin in os.environ.get(
        "FRONTEND_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_conn():
    config = load_config()
    return store.init(config.get("db_path", "data/jobs.db"))


def job_to_dict(row, full: bool = False) -> dict:
    d = {
        "id": row["id"],
        "source": row["source"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "remote": bool(row["remote"]),
        "published": row["published"],
        "url": row["url"],
        "score": row["score"],
        "first_seen": row["first_seen"],
    }
    if full:
        d["description"] = row["description"]
    else:
        d["has_description"] = row["description"] is not None
    return d


def candidate_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "source_file": row["source_file"],
        "skills": json.loads(row["skills"] or "[]"),
        "roles": json.loads(row["roles"] or "[]"),
        "experience": json.loads(row["experience"] or "[]"),
        "education": json.loads(row["education"] or "[]"),
        "parsed_at": row["parsed_at"],
    }


@app.get("/api/jobs")
def list_jobs(
    source: Optional[str] = None,
    remote: Optional[bool] = None,
    q: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 200,
):
    conn = get_conn()
    try:
        rows = store.list_jobs(conn, source=source, remote=remote, q=q, min_score=min_score, limit=limit)
        return {"jobs": [job_to_dict(r) for r in rows], "count": len(rows)}
    finally:
        conn.close()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="job not found")
        return job_to_dict(row, full=True)
    finally:
        conn.close()


@app.get("/api/stats")
def stats():
    conn = get_conn()
    try:
        total = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        scored = conn.execute("SELECT COUNT(*) AS c FROM jobs WHERE score IS NOT NULL").fetchone()["c"]
        by_source = {
            r["source"]: r["c"]
            for r in conn.execute("SELECT source, COUNT(*) AS c FROM jobs GROUP BY source")
        }
        return {"total_jobs": total, "scored_jobs": scored, "by_source": by_source}
    finally:
        conn.close()


@app.get("/api/candidate")
def active_candidate():
    config = load_config()
    candidate_id = (config.get("profile") or {}).get("active_candidate_id")
    if not candidate_id:
        raise HTTPException(status_code=404, detail="no active candidate — upload a CV first")

    conn = get_conn()
    try:
        row = store.get_candidate(conn, candidate_id)
        if row is None:
            raise HTTPException(status_code=404, detail="active candidate not found in store")
        return candidate_to_dict(row)
    finally:
        conn.close()


@app.get("/api/profile")
def profile():
    config = load_config()
    p = config.get("profile") or {}
    return {
        "must_have": p.get("must_have", []),
        "nice_to_have": p.get("nice_to_have", {}),
        "locations": p.get("locations", []),
        "remote_bonus": p.get("remote_bonus", 0),
        "alert_threshold": config.get("alert_threshold", 40),
        "active_candidate_id": p.get("active_candidate_id"),
        "active_candidate_name": p.get("active_candidate_name"),
    }


@app.post("/api/cv")
async def upload_cv(file: UploadFile):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only PDF CVs are supported")

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    dest_path = os.path.join(UPLOADS_DIR, file.filename)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    conn = get_conn()
    try:
        candidate = process_pdf(conn, dest_path)
        update_profile_block(CONFIG_PATH, candidate)
        return candidate_to_dict(store.get_candidate(conn, candidate.id))
    finally:
        conn.close()
