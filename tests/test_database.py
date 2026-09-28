import tempfile
import unittest
from pathlib import Path

from database import Database
from storage import PAGE_SIZE


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "records.data"
        self.database = Database(self.path)
        self.addCleanup(self.database.close)

    def tearDown(self):
        pass

    def test_persistence_update_delete_and_range(self):
        first_page = self.database.put(8, "eight")
        self.database.put(3, "three")
        self.database.put(8, "updated")
        self.assertEqual(self.path.stat().st_size, 2 * PAGE_SIZE)
        reopened = Database(self.path)
        self.addCleanup(reopened.close)
        self.assertEqual(reopened.get(8)[0], "updated")
        self.assertEqual(reopened.range(3, 8), [
            {"key": 3, "value": "three", "page_number": 1},
            {"key": 8, "value": "updated", "page_number": first_page},
        ])
        self.assertTrue(reopened.delete(3))
        self.assertFalse(reopened.delete(3))
        self.assertIsNone(reopened.get(3)[0])
        after_delete = Database(self.path)
        self.addCleanup(after_delete.close)
        self.assertEqual(after_delete.get(8)[0], "updated")
        self.assertEqual(after_delete.state()["keys"], [8])

    def test_trace_reports_bloom_tree_and_cache(self):
        page_number = self.database.put(31, "thirty-one")
        _, first_trace = self.database.get(31)
        self.assertTrue(first_trace["bloom"]["present"])
        self.assertTrue(first_trace["found_in_tree"])
        self.assertEqual(first_trace["page_number"], page_number)
        self.assertTrue(first_trace["cache_hit"])

    def test_reset_clears_all_components(self):
        self.database.put(1, "one")
        self.database.reset()
        self.assertEqual(self.database.state()["keys"], [])
        self.assertEqual(self.database.state()["page_count"], 0)

    def test_input_validation(self):
        with self.assertRaises(TypeError):
            self.database.put(True, "no")
        with self.assertRaises(TypeError):
            self.database.put(1, 2)


if __name__ == "__main__":
    unittest.main()