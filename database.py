"""Thread-safe key-value database composed from the educational components."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from bloom_filter import BloomFilter
from bplustree import BPlusTree
from lru_cache import LRUCache
from storage import PageStorage


class Database:
    """Persist integer keys and text values in fixed-size disk pages."""

    def __init__(self, data_path: str | Path = "mini-db.data", cache_capacity: int = 3) -> None:
        self.storage = PageStorage(data_path)
        self.tree = BPlusTree(max_keys=3)
        self.cache: LRUCache[int, dict[str, object]] = LRUCache(cache_capacity)
        self.bloom = BloomFilter()
        self._lock = RLock()
        self._rebuild_indexes()

    def _rebuild_indexes(self) -> None:
        for page_number, record in self.storage.scan_pages():
            if record.get("deleted"):
                continue
            key = int(record["key"])
            self.tree.insert(key, page_number)
            self.bloom.add(key)

    @staticmethod
    def _validate_key(key: int) -> None:
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeError("Keys must be integers")

    def put(self, key: int, value: str) -> int:
        self._validate_key(key)
        if not isinstance(value, str):
            raise TypeError("Values must be text")
        with self._lock:
            page_number = self.tree.search(key)
            if page_number is None:
                page_number = self.storage.page_count
            record = {"key": key, "value": value, "deleted": False}
            self.storage.write_page(page_number, record)
            self.tree.insert(key, page_number)
            self.bloom.add(key)
            self.cache.put(page_number, record)
            return page_number

    def _read_page(self, page_number: int) -> tuple[dict[str, object], bool, int | None]:
        record, hit = self.cache.get(page_number)
        if hit:
            assert record is not None
            return record, True, None
        record = self.storage.read_page(page_number)
        evicted_page = self.cache.put(page_number, record)
        return record, False, evicted_page

    def get(self, key: int) -> tuple[str | None, dict[str, Any]]:
        self._validate_key(key)
        with self._lock:
            checked_bits = self.bloom.checked_bits(key)
            bloom_result = self.bloom.might_contain(key)
            trace: dict[str, Any] = {
                "bloom": {"checked_bits": checked_bits, "present": bloom_result, "bits": self.bloom.bits()},
                "tree_path": [],
                "page_number": None,
                "cache_hit": False,
                "evicted_page": None,
                "cache_pages": self.cache.keys(),
                "page": None,
                "found_in_tree": False,
            }
            if not bloom_result:
                return None, trace

            page_number, path = self.tree.search_with_trace(key)
            trace["tree_path"] = path
            trace["found_in_tree"] = page_number is not None
            trace["page_number"] = page_number
            if page_number is None:
                return None, trace

            record, cache_hit, evicted_page = self._read_page(page_number)
            trace.update(
                cache_hit=cache_hit,
                evicted_page=evicted_page,
                cache_pages=self.cache.keys(),
                page=record,
            )
            return str(record["value"]), trace

    def delete(self, key: int) -> bool:
        self._validate_key(key)
        with self._lock:
            page_number = self.tree.search(key)
            if page_number is None:
                return False
            self.storage.write_page(page_number, {"key": key, "value": "", "deleted": True})
            self.tree.delete(key)
            self.cache.discard(page_number)
            # Bloom bits are deliberately retained; this can cause false positives.
            return True

    def range(self, start: int, end: int) -> list[dict[str, object]]:
        self._validate_key(start)
        self._validate_key(end)
        with self._lock:
            result = []
            for key, page_number in self.tree.range_search(start, end):
                record, _, _ = self._read_page(page_number)
                result.append({"key": key, "value": record["value"], "page_number": page_number})
            return result

    def state(self) -> dict[str, object]:
        with self._lock:
            pages = [
                {"page_number": number, **record}
                for number, record in self.storage.scan_pages()
            ]
            return {
                "keys": [key for key, _ in self.tree.items()],
                "root_keys": self.tree.root_keys(),
                "leaves": self.tree.leaves(),
                "pages": pages,
                "bloom_bits": self.bloom.bits(),
                "cache_pages": self.cache.keys(),
                "cache_capacity": self.cache.capacity,
                "page_count": self.storage.page_count,
            }

    def reset(self) -> None:
        with self._lock:
            self.storage.clear()
            self.tree = BPlusTree(max_keys=3)
            self.bloom.clear()
            self.cache.clear()

    def close(self) -> None:
        self.storage.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()