import unittest

from lru_cache import LRUCache


class LRUCacheTests(unittest.TestCase):
    def test_hit_refreshes_recency_and_put_reports_eviction(self):
        cache = LRUCache[int, str](3)
        self.assertIsNone(cache.put(1, "one"))
        cache.put(2, "two")
        cache.put(3, "three")
        self.assertEqual(cache.get(1), ("one", True))
        self.assertEqual(cache.put(4, "four"), 2)
        self.assertEqual(cache.keys(), [3, 1, 4])
        self.assertEqual(cache.get(2), (None, False))

    def test_updates_are_most_recent_and_clear_empties(self):
        cache = LRUCache[int, str](2)
        cache.put(1, "old")
        cache.put(2, "two")
        cache.put(1, "new")
        self.assertEqual(cache.put(3, "three"), 2)
        self.assertEqual(cache.get(1), ("new", True))
        cache.clear()
        self.assertEqual(cache.keys(), [])


if __name__ == "__main__":
    unittest.main()