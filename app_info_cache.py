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
        if not directory in self._cache:
            self._cache[directory] = {}
        self._cache[directory][key] = value

    def get(self, directory, key):
        directory = AppInfoCache.normalize_directory_key(directory)
        if not directory in self._cache or not key in self._cache[directory]:
            return None
        return self._cache[directory][key]

    @staticmethod
    def normalize_directory_key(directory):
        return os.path.normpath(os.path.abspath(directory))

app_info_cache = AppInfoCache()