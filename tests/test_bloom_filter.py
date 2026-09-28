import unittest

from bloom_filter import BloomFilter


class BloomFilterTests(unittest.TestCase):
    def test_inserted_keys_are_never_rejected(self):
        bloom = BloomFilter()
        for key in range(100):
            bloom.add(key)
        self.assertTrue(all(bloom.might_contain(key) for key in range(100)))
        self.assertEqual(len(bloom.bits()), 32)
        self.assertEqual(len(bloom.checked_bits(42)), 2)

    def test_clear_resets_all_bits(self):
        bloom = BloomFilter()
        bloom.add(21)
        bloom.clear()
        self.assertEqual(bloom.bits(), [0] * 32)
        self.assertFalse(bloom.might_contain(21))


if __name__ == "__main__":
    unittest.main()