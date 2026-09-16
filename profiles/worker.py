import json
import os
import shutil
import sys
from dataclasses import asdict

# Allow `python profiles/worker.py`, not just `python -m profiles.worker`, by
# putting the project root (this file's parent) on sys.path for `import store`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

import store
from profiles.parser import parse_cv

UPLOADS_DIR = "data/cv_uploads"
PROCESSED_DIR = "data/cv_uploads/processed"
PROFILES_DIR = "data/profiles"
CONFIG_PATH = "config.yaml"


def update_profile_block(config_path: str, candidate, default_weight: int = 2) -> None:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    profile = config.get("profile", {}) or {}
    nice_to_have = profile.get("nice_to_have", {}) or {}

    for skill in candidate.skills:
        key = skill.lower()
        if key not in nice_to_have:
            nice_to_have[key] = default_weight

    profile["nice_to_have"] = nice_to_have
    profile.setdefault("must_have", [])
    profile.setdefault("exclude", [])
    profile.setdefault("locations", [])
    profile.setdefault("remote_bonus", 5)
    profile["active_candidate_id"] = candidate.id
    profile["active_candidate_name"] = candidate.name

    config["profile"] = profile
    config.setdefault("alert_threshold", 40)

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)


def main():
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(PROFILES_DIR, exist_ok=True)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    conn = store.init(config.get("db_path", "data/jobs.db"))

    pdf_files = [
        f for f in os.listdir(UPLOADS_DIR)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(UPLOADS_DIR, f))
    ]

    parsed = 0
    last_candidate = None
    for filename in pdf_files:
        pdf_path = os.path.join(UPLOADS_DIR, filename)
        candidate = parse_cv(pdf_path)
        store.upsert_candidate(conn, candidate)

        profile_path = os.path.join(PROFILES_DIR, f"{candidate.id}.json")
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(asdict(candidate), f, ensure_ascii=False, indent=2)

        shutil.move(pdf_path, os.path.join(PROCESSED_DIR, filename))
        parsed += 1
        last_candidate = candidate
        print(f"  parsed {filename!r}: {candidate.name!r}, {len(candidate.skills)} skills, "
              f"{len(candidate.experience)} experience entries")

    if last_candidate:
        update_profile_block(CONFIG_PATH, last_candidate)
        print(f"\nconfig.yaml profile.nice_to_have updated from {last_candidate.source_file!r} "
              f"({last_candidate.name or last_candidate.id}) — active profile is now this candidate. "
              f"must_have was NOT changed (edit manually).")

    print(f"\nfound {len(pdf_files)} pdf(s), parsed {parsed}")

    conn.close()


if __name__ == "__main__":
    main()
