"""
Unit tests for lib/safelist.py.
Tests cover all three list variants in both single- and multi-threaded scenarios.
"""

import threading
import pytest

from lib.safelist import safelist, DirtyList, SafeWriteList, SafeReadWriteList


class TestSafelistFactory:
    def test_dirty_mode(self):
        assert isinstance(safelist("dirty"), DirtyList)

    def test_safe_write_mode(self):
        assert isinstance(safelist("safe_write"), SafeWriteList)

    def test_safe_readwrite_mode(self):
        assert isinstance(safelist("safe_readwrite"), SafeReadWriteList)

    def test_invalid_mode_raises(self):
        with pytest.raises(ValueError):
            safelist("invalid")


class TestDirtyList:
    def test_push_and_get(self):
        lst = DirtyList()
        lst.push("a")
        assert lst.get(0) == "a"

    def test_modify(self):
        lst = DirtyList()
        lst.push("a")
        lst.modify(0, "b")
        assert lst.get(0) == "b"

    def test_multiple_pushes(self):
        lst = DirtyList()
        for i in range(5):
            lst.push(i)
        assert lst.get(4) == 4

    def test_repr(self):
        assert repr(DirtyList()) == "python list"


class TestSafeWriteList:
    def test_push_and_get(self):
        lst = SafeWriteList()
        lst.push(42)
        assert lst.get(0) == 42

    def test_modify(self):
        lst = SafeWriteList()
        lst.push(1)
        lst.modify(0, 99)
        assert lst.get(0) == 99

    def test_concurrent_pushes_no_data_loss(self):
        lst = SafeWriteList()
        n = 100
        threads = [threading.Thread(target=lst.push, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All items pushed — collect them all
        items = [lst.get(i) for i in range(n)]
        assert sorted(items) == list(range(n))


class TestSafeReadWriteList:
    def test_push_and_get(self):
        lst = SafeReadWriteList()
        lst.push("x")
        assert lst.get(0) == "x"

    def test_modify(self):
        lst = SafeReadWriteList()
        lst.push(10)
        lst.modify(0, 20)
        assert lst.get(0) == 20

    def test_sort(self):
        lst = SafeReadWriteList()
        for v in [3, 1, 2]:
            lst.push(v)
        lst.sort()
        assert lst.get(0) == 1
        assert lst.get(1) == 2
        assert lst.get(2) == 3

    def test_sort_with_key(self):
        lst = SafeReadWriteList()
        for v in ["banana", "apple", "cherry"]:
            lst.push(v)
        lst.sort(key=lambda x: x)
        assert lst.get(0) == "apple"

    def test_sort_reverse(self):
        lst = SafeReadWriteList()
        for v in [1, 3, 2]:
            lst.push(v)
        lst.sort(reverse=True)
        assert lst.get(0) == 3

    def test_concurrent_reads_and_writes(self):
        lst = SafeReadWriteList()
        for i in range(10):
            lst.push(i)

        errors = []

        def reader():
            try:
                for i in range(10):
                    _ = lst.get(i)
            except Exception as e:
                errors.append(e)

        def writer():
            try:
                for i in range(10):
                    lst.modify(i, i * 2)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        threads += [threading.Thread(target=writer) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent access: {errors}"
