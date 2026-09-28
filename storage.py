"""Fixed-size page storage for the mini database."""

from __future__ import annotations

import json
import struct
from pathlib import Path
from threading import RLock
from typing import Iterator


PAGE_SIZE = 4096
_LENGTH_SIZE = 4


class PageStorage:
    """Store one JSON record in each fixed 4 KB page."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._writer = None
        self._lock = RLock()

    @property
    def page_count(self) -> int:
        with self._lock:
            if self._writer is not None:
                self._writer.flush()
            if not self.path.exists():
                return 0
            return self.path.stat().st_size // PAGE_SIZE

    def read_page(self, page_number: int) -> dict[str, object]:
        if page_number < 0 or page_number >= self.page_count:
            raise IndexError(f"Page {page_number} does not exist")
        with self.path.open("rb") as data_file:
            data_file.seek(page_number * PAGE_SIZE)
            raw_page = data_file.read(PAGE_SIZE)
        return self.decode_page(raw_page)

    def write_page(self, page_number: int, record: dict[str, object]) -> None:
        with self._lock:
            if page_number < 0 or page_number > self.page_count:
                raise IndexError("Pages must be written in order")
            encoded = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(encoded) + _LENGTH_SIZE > PAGE_SIZE:
                raise ValueError(f"Record exceeds the {PAGE_SIZE}-byte page size")
            raw_page = struct.pack(">I", len(encoded)) + encoded
            raw_page += bytes(PAGE_SIZE - len(raw_page))
            if self._writer is None:
                self._writer = self.path.open("r+b" if self.path.exists() else "w+b")
            self._writer.seek(page_number * PAGE_SIZE)
            self._writer.write(raw_page)
            self._writer.flush()

    @staticmethod
    def decode_page(raw_page: bytes) -> dict[str, object]:
        if len(raw_page) != PAGE_SIZE:
            raise ValueError("A page must contain exactly 4096 bytes")
        length = struct.unpack(">I", raw_page[:_LENGTH_SIZE])[0]
        if length > PAGE_SIZE - _LENGTH_SIZE:
            raise ValueError("Page contains an invalid record length")
        record = json.loads(raw_page[_LENGTH_SIZE : _LENGTH_SIZE + length].decode("utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Page record must be a JSON object")
        return record

    def scan_pages(self) -> Iterator[tuple[int, dict[str, object]]]:
        """Read pages sequentially, yielding each page number and record."""
        if not self.path.exists():
            return
        with self.path.open("rb") as data_file:
            page_number = 0
            while raw_page := data_file.read(PAGE_SIZE):
                if len(raw_page) != PAGE_SIZE:
                    raise ValueError("The data file ends with a partial page")
                yield page_number, self.decode_page(raw_page)
                page_number += 1

    def read_all_bytes(self) -> bytes:
        if not self.path.exists():
            return b""
        return self.path.read_bytes()

    def clear(self) -> None:
        with self._lock:
            if self._writer is not None:
                self._writer.close()
                self._writer = None
            self.path.write_bytes(b"")

    def close(self) -> None:
        with self._lock:
            if self._writer is not None:
                self._writer.close()
                self._writer = None