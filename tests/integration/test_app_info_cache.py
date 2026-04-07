"""
Integration tests for AppInfoCache.

Uses real store()/load() I/O against the per-test temp directory
provided by the isolated_singletons autouse fixture in tests/conftest.py.
No mocking of encryption or file operations.
"""

import pytest
from utils.app_info_cache import AppInfoCache


@pytest.fixture
def cache():
    """Fresh AppInfoCache instance using the test temp dir set by isolated_singletons."""
    return AppInfoCache()


class TestGetSet:
    def test_set_and_get_roundtrip(self, cache, tmp_path):
        cache.set(str(tmp_path), "color", "#ff0000")
        assert cache.get(str(tmp_path), "color") == "#ff0000"

    def test_get_missing_key_returns_default(self, cache, tmp_path):
        assert cache.get(str(tmp_path), "nonexistent") is None
        assert cache.get(str(tmp_path), "nonexistent", default_val="x") == "x"

    def test_set_invalid_directory_raises(self, cache):
        with pytest.raises(Exception):
            cache.set("", "key", "value")

    def test_set_overwrites_existing_value(self, cache, tmp_path):
        cache.set(str(tmp_path), "k", "first")
        cache.set(str(tmp_path), "k", "second")
        assert cache.get(str(tmp_path), "k") == "second"

    def test_normalize_directory_key_consistent(self, cache, tmp_path):
        path = str(tmp_path)
        cache.set(path, "k", "v")
        # Lookup with trailing sep should still work after normalization
        assert cache.get(path.rstrip("/\\"), "k") == "v"


class TestMeta:
    def test_set_meta_and_get_meta(self, cache):
        cache.set_meta("test_key", "test_value")
        assert cache.get_meta("test_key") == "test_value"

    def test_get_meta_missing_returns_default(self, cache):
        assert cache.get_meta("__no_such_key__") is None
        assert cache.get_meta("__no_such_key__", default_val=42) == 42

    def test_set_meta_overwrites(self, cache):
        cache.set_meta("k", "old")
        cache.set_meta("k", "new")
        assert cache.get_meta("k") == "new"


class TestStorePersistence:
    def test_store_and_reload_preserves_meta(self, cache):
        cache.set_meta("persist_key", "persist_value")
        cache.store()
        reloaded = AppInfoCache()
        assert reloaded.get_meta("persist_key") == "persist_value"

    def test_store_and_reload_preserves_directory_entry(self, cache, tmp_path):
        cache.set(str(tmp_path), "my_key", "my_value")
        cache.store()
        reloaded = AppInfoCache()
        assert reloaded.get(str(tmp_path), "my_key") == "my_value"


class TestClearDirectoryCache:
    def test_clear_removes_directory_entry(self, cache, tmp_path):
        cache.set(str(tmp_path), "k", "v")
        cache.clear_directory_cache(str(tmp_path))
        assert cache.get(str(tmp_path), "k") is None

    def test_clear_removes_from_secondary_base_dirs(self, cache, tmp_path):
        path = str(tmp_path)
        cache.set_meta("secondary_base_dirs", [path, "/other"])
        cache.clear_directory_cache(path)
        assert path not in cache.get_meta("secondary_base_dirs", default_val=[])

    def test_clear_resets_base_dir_meta_if_matches(self, cache, tmp_path):
        path = str(tmp_path)
        cache.set_meta("base_dir", path)
        cache.clear_directory_cache(path)
        assert cache.get_meta("base_dir") == ""


class TestDirectoryColor:
    def test_set_and_get_directory_color(self, cache, tmp_path):
        cache.set_directory_color(str(tmp_path), "#aabbcc")
        assert cache.get_directory_color(str(tmp_path)) == "#aabbcc"

    def test_clear_directory_color(self, cache, tmp_path):
        cache.set_directory_color(str(tmp_path), "#aabbcc")
        cache.set_directory_color(str(tmp_path), None)
        assert cache.get_directory_color(str(tmp_path)) is None
