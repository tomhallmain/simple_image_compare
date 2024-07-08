import json
import os
import sys

class AppInfoCache:
    CACHE_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "app_info_cache.json")
    META_INFO_KEY = "info"
    DIRECTORIES_KEY = "directories"

    def __init__(self):
        self._cache = {AppInfoCache.META_INFO_KEY: {}, AppInfoCache.DIRECTORIES_KEY: {}}
        self.load()
        self.validate()

    def store(self):
        with open(AppInfoCache.CACHE_LOC, "w") as f:
            json.dump(self._cache, f, indent=4)

    def load(self):
        try:
            with open(AppInfoCache.CACHE_LOC, "r") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            pass

    def validate(self):
        directory_info = self._get_directory_info()
        directories = list(directory_info.keys())
        for d in directories:
            if not os.path.isdir(d):
                # The external drive this reference is pointing to may not be mounted, might still be valid
                if sys.platform == "win32" and not d.startswith("C:\\"):
                    base_dir = os.path.split("\\")[0] + "\\"
                    if not os.path.isdir(base_dir):
                        continue
                del directory_info[d]
                print(f"Removed stale directory reference: {d}")

    def _get_directory_info(self):
        if AppInfoCache.DIRECTORIES_KEY not in self._cache:
            self._cache[AppInfoCache.DIRECTORIES_KEY] = {}
        return self._cache[AppInfoCache.DIRECTORIES_KEY]

    def set_meta(self, key, value):
        if AppInfoCache.META_INFO_KEY not in self._cache:
            self._cache[AppInfoCache.META_INFO_KEY] = {}
        self._cache[AppInfoCache.META_INFO_KEY][key] = value

    def get_meta(self, key, default_val=None):
        if AppInfoCache.META_INFO_KEY not in self._cache or key not in self._cache[AppInfoCache.META_INFO_KEY]:
            return default_val
        return self._cache[AppInfoCache.META_INFO_KEY][key]

    def set(self, directory, key, value):
        directory = AppInfoCache.normalize_directory_key(directory)
        if directory is None or directory.strip() == "":
            raise Exception(f"Invalid directory provided to app_info_cache.set(). key={key} value={value}")
        directory_info = self._get_directory_info()
        if directory not in directory_info:
            directory_info[directory] = {}
        directory_info[directory][key] = value

    def get(self, directory, key, default_val=None):
        directory = AppInfoCache.normalize_directory_key(directory)
        directory_info = self._get_directory_info()
        if directory not in directory_info or key not in directory_info[directory]:
            return default_val
        return directory_info[directory][key]

    @staticmethod
    def normalize_directory_key(directory):
        return os.path.normpath(os.path.abspath(directory))

app_info_cache = AppInfoCache()
