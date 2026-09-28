"""A small B+ Tree with linked leaves and integer page-number values."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(eq=False)
class _Node:
    keys: list[int] = field(default_factory=list)
    values: list[int] = field(default_factory=list)
    children: list[_Node] = field(default_factory=list)
    parent: _Node | None = None
    next: _Node | None = None
    previous: _Node | None = None

    @property
    def is_leaf(self) -> bool:
        return not self.children


class BPlusTree:
    """Map integer keys to page numbers using a B+ Tree index.

    Leaves hold key/value pairs and are linked for efficient range scans.
    Internal keys are copies of the minimum key in each right-hand child.
    """

    def __init__(self, max_keys: int = 3) -> None:
        if max_keys < 3:
            raise ValueError("max_keys must be at least 3")
        self.max_keys = max_keys
        self.max_children = max_keys + 1
        self.root = _Node()

    def _find_leaf(self, key: int) -> tuple[_Node, list[dict[str, object]]]:
        node = self.root
        path: list[dict[str, object]] = []
        while not node.is_leaf:
            child_index = bisect_right(node.keys, key)
            path.append({"type": "internal", "keys": list(node.keys), "child": child_index})
            node = node.children[child_index]
        path.append({"type": "leaf", "keys": list(node.keys)})
        return node, path

    def search(self, key: int) -> int | None:
        leaf, _ = self._find_leaf(key)
        index = bisect_left(leaf.keys, key)
        if index < len(leaf.keys) and leaf.keys[index] == key:
            return leaf.values[index]
        return None

    def search_with_trace(self, key: int) -> tuple[int | None, list[dict[str, object]]]:
        leaf, path = self._find_leaf(key)
        index = bisect_left(leaf.keys, key)
        page_number = leaf.values[index] if index < len(leaf.keys) and leaf.keys[index] == key else None
        return page_number, path

    def insert(self, key: int, page_number: int) -> None:
        leaf, _ = self._find_leaf(key)
        index = bisect_left(leaf.keys, key)
        if index < len(leaf.keys) and leaf.keys[index] == key:
            leaf.values[index] = page_number
            return
        leaf.keys.insert(index, key)
        leaf.values.insert(index, page_number)
        if len(leaf.keys) > self.max_keys:
            split_index = (len(leaf.keys) + 1) // 2
            sibling = _Node(keys=leaf.keys[split_index:], values=leaf.values[split_index:])
            leaf.keys = leaf.keys[:split_index]
            leaf.values = leaf.values[:split_index]
            sibling.next = leaf.next
            sibling.previous = leaf
            if sibling.next is not None:
                sibling.next.previous = sibling
            leaf.next = sibling
            self._insert_sibling(leaf, sibling)

    def _insert_sibling(self, left: _Node, right: _Node) -> None:
        parent = left.parent
        if parent is None:
            self.root = _Node(children=[left, right])
            left.parent = self.root
            right.parent = self.root
            self._refresh(self.root)
            return
        index = parent.children.index(left) + 1
        parent.children.insert(index, right)
        right.parent = parent
        self._refresh(parent)
        if len(parent.children) > self.max_children:
            split_index = len(parent.children) // 2
            sibling = _Node(children=parent.children[split_index:])
            parent.children = parent.children[:split_index]
            for child in sibling.children:
                child.parent = sibling
            self._refresh(parent)
            self._refresh(sibling)
            self._insert_sibling(parent, sibling)

    @staticmethod
    def _subtree_min(node: _Node) -> int:
        while not node.is_leaf:
            node = node.children[0]
        return node.keys[0]

    def _refresh(self, node: _Node) -> None:
        if not node.is_leaf:
            node.keys = [self._subtree_min(child) for child in node.children[1:]]

    def delete(self, key: int) -> bool:
        leaf, _ = self._find_leaf(key)
        index = bisect_left(leaf.keys, key)
        if index == len(leaf.keys) or leaf.keys[index] != key:
            return False
        del leaf.keys[index]
        del leaf.values[index]
        if leaf is self.root:
            return True
        minimum = (self.max_keys + 1) // 2
        if len(leaf.keys) >= minimum:
            self._refresh_up(leaf.parent)
            return True
        self._rebalance_leaf(leaf)
        return True

    def _rebalance_leaf(self, leaf: _Node) -> None:
        parent = leaf.parent
        assert parent is not None
        index = parent.children.index(leaf)
        left = parent.children[index - 1] if index > 0 else None
        right = parent.children[index + 1] if index + 1 < len(parent.children) else None
        minimum = (self.max_keys + 1) // 2

        if left is not None and len(left.keys) > minimum:
            leaf.keys.insert(0, left.keys.pop())
            leaf.values.insert(0, left.values.pop())
        elif right is not None and len(right.keys) > minimum:
            leaf.keys.append(right.keys.pop(0))
            leaf.values.append(right.values.pop(0))
        elif left is not None:
            left.keys.extend(leaf.keys)
            left.values.extend(leaf.values)
            left.next = leaf.next
            if leaf.next is not None:
                leaf.next.previous = left
            parent.children.pop(index)
        else:
            assert right is not None
            leaf.keys.extend(right.keys)
            leaf.values.extend(right.values)
            leaf.next = right.next
            if right.next is not None:
                right.next.previous = leaf
            parent.children.pop(index + 1)

        self._refresh(parent)
        self._rebalance_internal(parent)

    def _rebalance_internal(self, node: _Node) -> None:
        if node is self.root:
            if not node.is_leaf and len(node.children) == 1:
                self.root = node.children[0]
                self.root.parent = None
            else:
                self._refresh(node)
            return

        minimum = (self.max_children + 1) // 2
        if len(node.children) >= minimum:
            self._refresh_up(node)
            return

        parent = node.parent
        assert parent is not None
        index = parent.children.index(node)
        left = parent.children[index - 1] if index > 0 else None
        right = parent.children[index + 1] if index + 1 < len(parent.children) else None

        if left is not None and len(left.children) > minimum:
            child = left.children.pop()
            node.children.insert(0, child)
            child.parent = node
            self._refresh(left)
            self._refresh(node)
        elif right is not None and len(right.children) > minimum:
            child = right.children.pop(0)
            node.children.append(child)
            child.parent = node
            self._refresh(right)
            self._refresh(node)
        elif left is not None:
            left.children.extend(node.children)
            for child in node.children:
                child.parent = left
            parent.children.pop(index)
            self._refresh(left)
        else:
            assert right is not None
            node.children.extend(right.children)
            for child in right.children:
                child.parent = node
            parent.children.pop(index + 1)
            self._refresh(node)

        self._refresh(parent)
        self._rebalance_internal(parent)

    def _refresh_up(self, node: _Node | None) -> None:
        while node is not None:
            self._refresh(node)
            node = node.parent

    def range_search(self, start: int, end: int) -> list[tuple[int, int]]:
        if end < start:
            return []
        leaf, _ = self._find_leaf(start)
        results: list[tuple[int, int]] = []
        while leaf is not None:
            for key, page_number in zip(leaf.keys, leaf.values):
                if key > end:
                    return results
                if key >= start:
                    results.append((key, page_number))
            leaf = leaf.next
        return results

    def items(self) -> Iterator[tuple[int, int]]:
        node = self.root
        while not node.is_leaf:
            node = node.children[0]
        while node is not None:
            yield from zip(node.keys, node.values)
            node = node.next

    def leaves(self) -> list[dict[str, object]]:
        node = self.root
        while not node.is_leaf:
            node = node.children[0]
        result = []
        while node is not None:
            result.append({"keys": list(node.keys), "pages": list(node.values)})
            node = node.next
        return result

    def root_keys(self) -> list[int]:
        return list(self.root.keys)