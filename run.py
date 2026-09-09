import time
from datetime import datetime, timezone

import yaml

import store
from sources import Arbeitnow, Arbeitsagentur, Query


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    conn = store.init(config["db_path"])

    ba = Arbeitsagentur(config["fetch"]["arbeitsagentur"])
    an = Arbeitnow(config["fetch"]["arbeitnow"])
    sources = [ba, an]

    total_fetched = 0
    total_new = 0
    for source in sources:
        for s in config["searches"]:
            query = Query(was=s["was"], wo=s["wo"], umkreis=s.get("umkreis", 0))
            jobs = source.fetch(query)
            new_count = store.upsert(conn, jobs)
            total_fetched += len(jobs)
            total_new += new_count
            print(f"  [{source.name}] {s['was']!r} in {s['wo']}: fetched {len(jobs)}, new {new_count}")

    pending = store.needs_description(conn)
    sleep_seconds = config["fetch"]["arbeitsagentur"].get("sleep_seconds", 0.5)
    filled = 0
    skipped = 0
    for job_id, external_id, source_name in pending:
        if source_name != ba.name:
            continue
        desc = ba.fetch_description(external_id)
        if desc:
            store.set_description(conn, job_id, desc)
            filled += 1
        else:
            skipped += 1
        time.sleep(sleep_seconds)

    today = datetime.now(timezone.utc).date().isoformat()
    new_today = store.get_new(conn, today)

    print(f"\nfetched {total_fetched} postings, {total_new} new to the store")
    print(f"descriptions: {filled} filled, {skipped} skipped (404 / expired)")
    print(f"new today ({today}): {len(new_today)}")

    conn.close()


if __name__ == "__main__":
    main()
