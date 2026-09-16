import json
import os
import shutil

import yaml

import store
from profiles import worker
from profiles.parser import Candidate, Experience


def _setup_project(tmp_path, monkeypatch, sample_cv_pdf):
    monkeypatch.chdir(tmp_path)
    os.makedirs("data", exist_ok=True)
    with open("data/skills.json", "w", encoding="utf-8") as f:
        json.dump(["Python", "SQL", "Docker", "Machine Learning"], f)
    with open("data/roles.json", "w", encoding="utf-8") as f:
        json.dump(["Data Scientist", "Backend Engineer"], f)

    config = {
        "searches": [{"was": "Data Analyst", "wo": "Berlin", "umkreis": 30}],
        "fetch": {"size": 100},
        "db_path": "data/jobs.db",
    }
    with open("config.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f)

    os.makedirs("data/cv_uploads", exist_ok=True)
    shutil.copy(sample_cv_pdf, "data/cv_uploads/cv.pdf")

    return config


def test_scan_processes_new_pdf_once(tmp_path, monkeypatch, sample_cv_pdf):
    _setup_project(tmp_path, monkeypatch, sample_cv_pdf)

    worker.main()

    assert not os.path.exists("data/cv_uploads/cv.pdf")
    assert os.path.exists("data/cv_uploads/processed/cv.pdf")

    conn = store.init("data/jobs.db")
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1
    conn.close()

    worker.main()  # second run: nothing left to process

    conn = store.init("data/jobs.db")
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1
    conn.close()


def _make_candidate(candidate_id="abc123def456", skills=None):
    return Candidate(
        id=candidate_id,
        source_file="cv.pdf",
        name="Jane Doe",
        skills=skills or ["Python"],
        roles=["Data Scientist"],
        experience=[Experience(title="Data Scientist", company="Acme", date_range="2020-2021", description="")],
        education=["BSc"],
        raw_text="Jane Doe ... Python ...",
        parsed_at="2026-01-01T00:00:00+00:00",
    )


def test_upsert_candidate_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = store.init("jobs.db")
    candidate = _make_candidate()

    store.upsert_candidate(conn, candidate)
    row1 = store.get_candidate(conn, candidate.id)

    store.upsert_candidate(conn, candidate)
    row2 = store.get_candidate(conn, candidate.id)

    first_seen_idx, last_seen_idx = 9, 10
    assert row1[first_seen_idx] == row2[first_seen_idx]
    assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 1
    conn.close()


def test_json_export_written(tmp_path, monkeypatch, sample_cv_pdf):
    _setup_project(tmp_path, monkeypatch, sample_cv_pdf)

    worker.main()

    files = os.listdir("data/profiles")
    assert len(files) == 1

    with open(os.path.join("data/profiles", files[0]), encoding="utf-8") as f:
        exported = json.load(f)
    assert "Python" in exported["skills"]
    assert "SQL" in exported["skills"]


def test_update_profile_block_preserves_manual_must_have(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = {
        "searches": [{"was": "x", "wo": "y", "umkreis": 10}],
        "fetch": {"size": 100},
        "profile": {"must_have": ["python"], "nice_to_have": {"sql": 9}},
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f)

    candidate = _make_candidate(skills=["SQL", "Docker"])
    worker.update_profile_block(str(config_path), candidate)

    with open(config_path, encoding="utf-8") as f:
        updated = yaml.safe_load(f)

    assert updated["profile"]["must_have"] == ["python"]
    assert updated["profile"]["nice_to_have"]["sql"] == 9
    assert updated["profile"]["nice_to_have"]["docker"] == 2


def test_update_profile_block_preserves_searches_and_fetch(tmp_path):
    config_path = tmp_path / "config.yaml"
    config = {
        "searches": [{"was": "x", "wo": "y", "umkreis": 10}],
        "fetch": {"size": 100, "sleep_seconds": 0.5},
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f)

    candidate = _make_candidate()
    worker.update_profile_block(str(config_path), candidate)

    with open(config_path, encoding="utf-8") as f:
        updated = yaml.safe_load(f)

    assert updated["searches"] == config["searches"]
    assert updated["fetch"] == config["fetch"]
