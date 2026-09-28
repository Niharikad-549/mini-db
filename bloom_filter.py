"""A 32-bit Bloom filter with two deterministic integer hash functions."""


class BloomFilter:
    """Quickly reject keys that definitely are not present.

    Deletion intentionally does not clear bits. A later lookup may therefore
    pass the filter even though the tree no longer contains that key.
    """

    BIT_COUNT = 32

    def __init__(self) -> None:
        self._bits = 0

    @staticmethod
    def _hashes(key: int) -> tuple[int, int]:
        first = ((key * 0x9E3779B1) ^ (key >> 16)) & 0xFFFFFFFF
        second = ((key * 0x85EBCA77) ^ (key >> 13) ^ 0xC2B2AE3D) & 0xFFFFFFFF
        return first % BloomFilter.BIT_COUNT, second % BloomFilter.BIT_COUNT

    def add(self, key: int) -> None:
        for bit in self._hashes(key):
            self._bits |= 1 << bit

    def might_contain(self, key: int) -> bool:
        return all(self._bits & (1 << bit) for bit in self._hashes(key))

    def checked_bits(self, key: int) -> list[int]:
        return list(self._hashes(key))

    def bits(self) -> list[int]:
        return [(self._bits >> bit) & 1 for bit in range(self.BIT_COUNT)]

    def clear(self) -> None:
        self._bits = 0