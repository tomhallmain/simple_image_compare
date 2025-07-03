import json
import os
import shutil
import sys

from utils.encryptor import encrypt_data_to_file, decrypt_data_from_file
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class AppInfoCache:
    CACHE_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "app_info_cache.enc")
    META_INFO_KEY = "info"
    DIRECTORIES_KEY = "directories"

    def __init__(self):
        self._cache = {AppInfoCache.META_INFO_KEY: {}, AppInfoCache.DIRECTORIES_KEY: {}}
        self.load()
        self.validate()

    def store(self):
        try:
            cache_data = json.dumps(self._cache).encode('utf-8')
            encrypt_data_to_file(cache_data, "simple_image_compare", "app_info_cache", AppInfoCache.CACHE_LOC)
        except Exception as e:
            logger.error(f"Error storing cache: {e}")
            raise e

    def load(self):
        try:
            shutil.copy2(AppInfoCache.CACHE_LOC, AppInfoCache.CACHE_LOC + ".bak") # overwrite backup
            old_json_loc = AppInfoCache.CACHE_LOC.replace(".enc", ".json")
            if os.path.exists(old_json_loc):
                logger.info(f"Removing old cache file: {old_json_loc}")
                # Get the old data first
                with open(old_json_loc, "r") as f:
                    self._cache = json.load(f)
                self.store()
                os.remove(old_json_loc)
            else:
                encrypted_data = decrypt_data_from_file(AppInfoCache.CACHE_LOC, "simple_image_compare", "app_info_cache")
                self._cache = json.loads(encrypted_data.decode('utf-8'))
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
                logger.info(f"Removed stale directory reference: {d}")

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

    def export_as_json(self, json_path=None):
        """Export the current cache as a JSON file (not encoded)."""
        if json_path is None:
            json_path = os.path.splitext(self.CACHE_LOC)[0] + ".json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
        return json_path


app_info_cache = AppInfoCache()
