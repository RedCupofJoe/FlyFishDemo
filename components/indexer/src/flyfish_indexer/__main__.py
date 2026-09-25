"""Index every Markdown object under a trip prefix."""

from __future__ import annotations

import json
import os
from pathlib import Path

from flyfish_common.store import store_from_env
from flyfish_indexer.chunk import index_rows


def index_trip(store, trip_id: str, writer, pattern: str | None = None) -> int:
    prefix = f"trips/{trip_id}/"
    count = 0
    for key in store.list_keys(prefix):
        if not key.endswith(".md"):
            continue
        rows = index_rows(trip_id, key, store.get_text(key), pattern)
        for row in rows:
            writer(row)
            count += 1
    return count


def main() -> None:
    trip_id = os.environ.get("TRIP_ID", "")
    if not trip_id:
        raise SystemExit("Set TRIP_ID")
    store = store_from_env(Path("/data/artifacts"))
    pattern = os.environ.get("AUTORAG_PATTERN_ID") or None

    rows: list[dict] = []

    def writer(row: dict) -> None:
        rows.append(row)
        print(f"indexed {row['source_key']} {row['heading']}", flush=True)

    total = index_trip(store, trip_id, writer, pattern)
    store.put_text(f"trips/{trip_id}/index.json", json.dumps(rows, indent=2), "application/json")
    print(f"chunks {total}", flush=True)


if __name__ == "__main__":
    main()
