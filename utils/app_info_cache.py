import json
import os
import shutil
import sys

from utils.constants import AppInfo
from utils.encryptor import encrypt_data_to_file, decrypt_data_from_file
from utils.logging_setup import get_logger

logger = get_logger(__name__)


class AppInfoCache:
    CACHE_LOC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_info_cache.enc")
    JSON_LOC = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), "app_info_cache.json")
    META_INFO_KEY = "info"
    DIRECTORIES_KEY = "directories"

    def __init__(self):
        self._cache = {AppInfoCache.META_INFO_KEY: {}, AppInfoCache.DIRECTORIES_KEY: {}}
        self.load()
        self.validate()

    def store(self):
        try:
            cache_data = json.dumps(self._cache).encode('utf-8')
            encrypt_data_to_file(
                cache_data,
                AppInfo.SERVICE_NAME,
                AppInfo.APP_IDENTIFIER,
                AppInfoCache.CACHE_LOC
            )
        except Exception as e:
            logger.error(f"Error storing cache: {e}")
            raise e

    def _try_load_cache_from_file(self, path):
        """Attempt to load and decrypt the cache from the given file path. Raises on failure."""
        encrypted_data = decrypt_data_from_file(
            path,
            AppInfo.SERVICE_NAME,
            AppInfo.APP_IDENTIFIER
        )
        return json.loads(encrypted_data.decode('utf-8'))

    def load(self):
        try:
            if os.path.exists(AppInfoCache.JSON_LOC):
                logger.info(f"Removing old cache file: {AppInfoCache.JSON_LOC}")
                # Get the old data first
                with open(AppInfoCache.JSON_LOC, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
                self.store() # store encrypted cache
                os.remove(AppInfoCache.JSON_LOC)
                return

            # Try encrypted cache and backups in order
            cache_paths = [
                AppInfoCache.CACHE_LOC,
                AppInfoCache.CACHE_LOC + ".bak",
                AppInfoCache.CACHE_LOC + ".bak2"
            ]
            any_exist = any(os.path.exists(path) for path in cache_paths)
            if not any_exist:
                logger.info(f"No cache file found at {AppInfoCache.CACHE_LOC}, creating new cache")
                return

            for path in cache_paths:
                if os.path.exists(path):
                    try:
                        self._cache = self._try_load_cache_from_file(path)
                        # Only shift backups if we loaded from the main file
                        if path == AppInfoCache.CACHE_LOC:
                            backup_loc = AppInfoCache.CACHE_LOC + ".bak"
                            backup_loc2 = AppInfoCache.CACHE_LOC + ".bak2"
                            text = f"Loaded cache from {AppInfoCache.CACHE_LOC}, shifted backups to {backup_loc}"
                            if os.path.exists(backup_loc):
                                shutil.copy2(backup_loc, backup_loc2)
                                text += f" and {backup_loc2}"
                            shutil.copy2(AppInfoCache.CACHE_LOC, backup_loc)
                            logger.info(text)
                        else:
                            logger.warning(f"Loaded cache from backup: {path}")
                        return
                    except Exception as e:
                        logger.error(f"Failed to load cache from {path}: {e}")
                        continue
            # If we get here, all attempts failed (but at least one file existed)
            raise Exception(f"Failed to load cache from all locations: {cache_paths}")
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            raise e

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
        """Export the current cache as a JSON file (not encrypted)."""
        if json_path is None:
            json_path = AppInfoCache.JSON_LOC
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
        return json_path


app_info_cache = AppInfoCache()
