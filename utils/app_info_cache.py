import json
import os

class AppInfoCache:
    CACHE_LOC = "app_info_cache.json"

    def __init__(self):
        self._cache = {}
        self.load()

    def store(self):
        with open(self.CACHE_LOC, "w") as f:
            json.dump(self._cache, f, indent=4)

    def load(self):
        try:
            with open(self.CACHE_LOC, "r") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            pass

    def set(self, directory, key, value):
        directory = AppInfoCache.normalize_directory_key(directory)
        if directory is None or directory.strip() == "":
            raise Exception(f"Invalid directory provided to app_info_cache.set(). key={key} value={value}")
        if not directory in self._cache:
            self._cache[directory] = {}
        self._cache[directory][key] = value

    def get(self, directory, key, default_val=None):
        directory = AppInfoCache.normalize_directory_key(directory)
        if not directory in self._cache or not key in self._cache[directory]:
            return default_val
        return self._cache[directory][key]

    @staticmethod
    def normalize_directory_key(directory):
        return os.path.normpath(os.path.abspath(directory))

app_info_cache = AppInfoCache()
