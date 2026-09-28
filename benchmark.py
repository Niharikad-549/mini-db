"""Compare a full page scan, B+ Tree lookups, and B+ Tree plus LRU cache."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

from database import Database
from storage import PAGE_SIZE, PageStorage


def run_benchmark(records: int = 10_000) -> dict[str, Any]:
    """Run identical lookups against three real storage/index strategies."""
    if records < 10_000:
        raise ValueError("The benchmark requires at least 10,000 records")

    with tempfile.TemporaryDirectory(prefix="mini-db-benchmark-") as temporary, Database(
        Path(temporary) / "benchmark.data", cache_capacity=3
    ) as database:
        data_path = Path(temporary) / "benchmark.data"
        for key in range(records):
            database.put(key, f"value-{key}")

        query_keys = [key for _ in range(40) for key in (17, records // 2, records - 19)]
        storage = PageStorage(data_path)
        all_pages = storage.read_all_bytes()

        scan_start = perf_counter()
        for target in query_keys:
            for offset in range(0, len(all_pages), PAGE_SIZE):
                page = storage.decode_page(all_pages[offset : offset + PAGE_SIZE])
                if page.get("key") == target and not page.get("deleted"):
                    break
        scan_seconds = perf_counter() - scan_start

        tree_start = perf_counter()
        for target in query_keys:
            page_number = database.tree.search(target)
            if page_number is None:
                raise AssertionError("Benchmark key was missing from the B+ Tree")
            database.storage.read_page(page_number)
        tree_seconds = perf_counter() - tree_start

        database.cache.clear()
        cached_start = perf_counter()
        for target in query_keys:
            value, _ = database.get(target)
            if value != f"value-{target}":
                raise AssertionError("Cached lookup returned the wrong value")
        cached_seconds = perf_counter() - cached_start

    query_count = len(query_keys)
    timings = {"full_scan": scan_seconds, "bplus_tree": tree_seconds, "tree_and_cache": cached_seconds}
    return {
        "records": records,
        "queries": query_count,
        "milliseconds_per_lookup": {
            name: seconds * 1000 / query_count for name, seconds in timings.items()
        },
        "speedup_vs_scan": {
            name: scan_seconds / seconds if seconds else 0.0 for name, seconds in timings.items()
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=10_000)
    arguments = parser.parse_args()
    result = run_benchmark(arguments.records)
    print(f"Mini DB benchmark: {result['records']:,} records, {result['queries']:,} lookups")
    print(f"{'Strategy':<24} {'Mean lookup (ms)':>18} {'Speedup':>12}")
    for name, milliseconds in result["milliseconds_per_lookup"].items():
        print(f"{name:<24} {milliseconds:>18.4f} {result['speedup_vs_scan'][name]:>11.2f}x")
    print("\nRaw results:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()