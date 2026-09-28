import random
import unittest

from bplustree import BPlusTree


class BPlusTreeTests(unittest.TestCase):
    def test_insert_search_update_and_range(self):
        tree = BPlusTree()
        for key in range(100):
            tree.insert(key, key + 1000)
        tree.insert(42, 7)
        self.assertEqual(tree.search(42), 7)
        self.assertEqual(tree.search(-1), None)
        self.assertEqual(tree.range_search(10, 15), [(key, key + 1000) for key in range(10, 16)])
        self.assertEqual([key for key, _ in tree.items()], list(range(100)))

    def test_random_deletions_preserve_tree_and_leaf_links(self):
        tree = BPlusTree()
        expected = {key: key * 2 for key in range(250)}
        keys = list(expected)
        random.Random(19).shuffle(keys)
        for key, value in expected.items():
            tree.insert(key, value)
        for key in keys:
            self.assertTrue(tree.delete(key))
            expected.pop(key)
            self.assertEqual(list(tree.items()), sorted(expected.items()))
            self.assertEqual(tree.range_search(-1, 1000), sorted(expected.items()))
        self.assertEqual(tree.root_keys(), [])
        self.assertFalse(tree.delete(12))

    def test_mixed_operations_match_dictionary(self):
        tree = BPlusTree()
        expected = {}
        randomizer = random.Random(7)
        for _ in range(1500):
            key = randomizer.randrange(180)
            if randomizer.random() < 0.65:
                page = randomizer.randrange(10_000)
                tree.insert(key, page)
                expected[key] = page
            else:
                self.assertEqual(tree.delete(key), key in expected)
                expected.pop(key, None)
            self.assertEqual(list(tree.items()), sorted(expected.items()))


if __name__ == "__main__":
    unittest.main()