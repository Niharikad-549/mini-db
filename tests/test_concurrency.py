import tempfile
import threading
import unittest
from pathlib import Path

from database import Database


class DatabaseConcurrencyTests(unittest.TestCase):
    def test_concurrent_writes_and_reads_remain_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            with Database(Path(temporary) / "concurrent.data") as database:
                errors = []

                def write_partition(partition):
                    try:
                        for offset in range(100):
                            key = partition * 100 + offset
                            database.put(key, f"value-{key}")
                            self.assertEqual(database.get(key)[0], f"value-{key}")
                    except Exception as error:
                        errors.append(error)

                threads = [threading.Thread(target=write_partition, args=(partition,)) for partition in range(4)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()

                self.assertEqual(errors, [])
                self.assertEqual(database.state()["keys"], list(range(400)))
                result = database.range(95, 105)
                self.assertEqual(
                    [(item["key"], item["value"]) for item in result],
                    [(key, f"value-{key}") for key in range(95, 106)],
                )
                for item in result:
                    self.assertEqual(item["page_number"], database.tree.search(item["key"]))


if __name__ == "__main__":
    unittest.main()