# Mini DB

Mini DB is a small persistent key-value database built from Python's standard library. It stores integer keys and text values in fixed 4 KB pages, then makes each lookup visible in a local web interface: the Bloom filter check, B+ Tree path, cache decision, and disk page.

## Run it

Install Python 3.10 or newer. No pip packages are required.

```powershell
python app.py
```

Open [http://localhost:8000](http://localhost:8000). The server runs the 10,000-record benchmark at startup so the page can show measured local results. The persistent `mini-db.data` file is created beside `app.py` when the first record is written. Use **Reset** in the page to clear it.

Run the command-line example:

```powershell
python demo.py
```

Run all tests and the benchmark:

```powershell
python -m unittest discover -s tests -v
python benchmark.py
```

## Components

- `storage.py` writes one JSON record per 4 KB page. A four-byte length prefix frames the UTF-8 record; the remaining bytes are padding. Pages are numbered from zero. Deletes write a tombstone instead of reclaiming or shifting a page, so existing page references remain stable.
- `bplustree.py` maps integer keys to page numbers. Internal nodes route the search; leaves hold key/page pairs and link to their neighbors for ordered range scans. Splits, borrowing, and merges keep the tree balanced after inserts and deletes.
- `lru_cache.py` holds the three most recently used pages by default. A cache hit avoids another page read; a miss loads the page and may evict the least recently used page.
- `bloom_filter.py` uses two deterministic hashes and 32 bits to quickly reject definite misses before searching the tree. It never produces false negatives for inserted keys, but collisions can produce false positives. Bits are not cleared on delete, intentionally, so deleted keys can continue to pass the filter until the database is reset or restarted and its filter is rebuilt from live pages.
- `database.py` combines those structures and protects each public operation with a reentrant lock. The lock prevents threads from observing partially updated storage/index/cache state. The file is the source of truth: startup scans pages to rebuild the in-memory tree and Bloom filter.
- `app.py` serves the static page and JSON API with `http.server`. The benchmark panel uses real timings returned by `benchmark.py`, not sample values.
- `demo.py` is a small CLI walkthrough. `benchmark.py` compares a full scan of 10,000+ pages, B+ Tree lookup plus page read, and B+ Tree lookup with the three-page LRU cache. The cache measurement repeats a three-page working set so its locality benefit is observable.

## JSON API

- `GET /api/state` returns live keys, root separators, linked leaves, disk pages, Bloom bits, LRU contents, and benchmark results.
- `GET /api/get?key=N` returns the value and a trace with checked Bloom bits, tree path, page number, cache hit/miss, and any eviction.
- `POST /api/put` accepts `{"key": 7, "value": "text"}`.
- `POST /api/delete` accepts `{"key": 7}`.
- `GET /api/range?start=A&end=B` returns records in the inclusive key range.
- `POST /api/reset` clears the data file and in-memory structures; it is used by the Reset control.

The server binds to `127.0.0.1` and is intended for local educational use, not exposure to an untrusted network. Thread safety is within a single process; simultaneous independent server processes are not coordinated.

## Interview talking points

**30-second pitch:** Mini DB is a persistent key-value store I built to make storage and indexing behavior observable. Each record lives in a fixed-size page, and an in-memory B+ Tree maps keys to pages. A Bloom filter can reject definite misses, an LRU cache keeps recent pages close, and a small web UI animates each real lookup trace. The project includes range scans, deletion, restart recovery, thread-safety tests, and a benchmark that compares scanning with indexed access.

**Why is an index needed?** Without an index, finding one key requires checking pages until the record is found, which is $O(n)$. The B+ Tree directs the search through a small number of sorted nodes, giving $O(\log n)$ lookup and ordered range traversal.

**B+ Tree vs. binary tree?** A B+ Tree stores many separators per node, keeping its height small and reducing page visits. All records live in linked leaves, which also makes range scans efficient. A binary tree has only two branches per node and can become tall or unbalanced without additional balancing rules.

**Why LRU?** Recent pages are likely to be requested again. LRU keeps those pages in a bounded cache, and evicts the page that has gone unused longest when capacity is reached.

**Why can Bloom filters give false positives?** Different keys can hash to the same bit positions. Seeing both bits set means “possibly present,” not “definitely present”; the tree confirms the answer. A clear bit does prove absence.

**How is thread safety done?** A reentrant lock surrounds each public database operation, covering its storage, tree, Bloom-filter, and cache changes as one critical section. The cache and storage writer also guard their own internal state. The multithreaded test writes and reads disjoint keys concurrently and checks the final ordered results.