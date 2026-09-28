"""A small, thread-safe least-recently-used cache."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Generic, TypeVar


Key = TypeVar("Key")
Value = TypeVar("Value")


class LRUCache(Generic[Key, Value]):
    """Cache values by key and report the key displaced on insertion."""

    def __init__(self, capacity: int = 3) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._entries: OrderedDict[Key, Value] = OrderedDict()
        self._lock = RLock()

    def get(self, key: Key) -> tuple[Value | None, bool]:
        with self._lock:
            if key not in self._entries:
                return None, False
            self._entries.move_to_end(key)
            return self._entries[key], True

    def put(self, key: Key, value: Value) -> Key | None:
        with self._lock:
            self._entries.pop(key, None)
            self._entries[key] = value
            if len(self._entries) > self.capacity:
                evicted_key, _ = self._entries.popitem(last=False)
                return evicted_key
            return None

    def discard(self, key: Key) -> None:
        with self._lock:
            self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def items(self) -> list[tuple[Key, Value]]:
        with self._lock:
            return list(self._entries.items())

    def keys(self) -> list[Key]:
        with self._lock:
            return list(self._entries.keys())