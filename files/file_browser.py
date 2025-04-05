import glob
import json
import os
from random import shuffle, choice
import re
import threading
from time import sleep
from typing import List

from files.sortable_file import SortableFile
from utils.config import config
from utils.constants import Sort, SortBy, Direction
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._



class FileBrowser:
    have_confirmed_directories = []

    def __init__(self, directory=".", recursive=False, filter=None, sort_by=SortBy.NAME):
        self.directory = directory
        self.recursive = recursive
        self.filter = filter
        self._files_cache = {}
        self._files = []
        self._new_files = []
        self.filepaths = []
        self.sort_by = sort_by
        self.sort = Sort.ASC
        self.file_cursor = -1
        self.cursor_lock = threading.Lock()
        self.checking_files = False
        self.use_file_paths_json = config.use_file_paths_json

    def has_files(self):
        return len(self._files) > 0

    def has_file(self, _file):
        return _file in self.filepaths

    def count(self):
        return len(self._files)

    def is_slow_total_files(self, threshold=2000):
        factor = 5 if Utils.is_external_drive(self.directory) else 1
        return factor * len(self._files) > threshold

    def has_confirmed_dir(self):
        return self.directory in FileBrowser.have_confirmed_directories

    def set_dir_confirmed(self):
        if not self.has_confirmed_dir():
            FileBrowser.have_confirmed_directories.append(self.directory)

    def set_filter(self, filter):
        if config.debug:
            Utils.log_debug(f"File browser set filter: {filter}")
        self.filter = filter

    def set_recursive(self, recursive):
        if config.debug:
            Utils.log_debug(f"File browser set recursive: {recursive}")
        self.recursive = recursive
        self.refresh()

    def is_recursive(self):
        return self.recursive

    def get_cursor(self):
        with self.cursor_lock:
            return self.file_cursor

    def refresh(self, refresh_cursor=True, file_check=False, removed_files=[], direction=Direction.FORWARD):
        last_files = self.get_files() if file_check else []
        if config.use_file_paths_json:
            self.update_json_for_removed_files(removed_files)
        if refresh_cursor:
            with self.cursor_lock:
                self.file_cursor = direction.get_correction(backward_value=1)
        current_file = self.current_file() if file_check else None
        self.filepaths = []
        self._get_sortable_files()
        files = self.get_files()
        self.checking_files = len(files) > 0 and len(files) < config.file_check_skip_if_n_files_over # Avoid rechecking in directories with many files
        if file_check and current_file and os.path.isfile(current_file):
            with self.cursor_lock:
                self.file_cursor = files.index(current_file)
                if len(removed_files) > 0:
                    if self.file_cursor > -1:
                        self.file_cursor += direction.get_correction()
            self._new_files = list(set(files) - set(last_files))
        elif not refresh_cursor:
            with self.cursor_lock:
                if len(files) - 1 < self.file_cursor:
                    self.file_cursor = direction.get_correction()
                else:
                    self.file_cursor += direction.get_correction()
        return files

    def update_cursor_to_new_images(self):
        if len(self._new_files) == 0:
            return False
        with self.cursor_lock:
            self.file_cursor = self.filepaths.index(self._new_files[0]) - 1
        return True

    def set_directory(self, directory):
        self.directory = directory
        self.checking_files = True
        self._files_cache = {}
        Utils.log(f"Setting base directory: {directory}")
        return self.refresh()

    def get_sort_by(self):
        return self.sort_by

    def set_sort_by(self, sort_by):
        self.sort_by = sort_by
        if self.sort_by == SortBy.RANDOMIZE:
            self.sort = Sort.RANDOM
        self.refresh()
        return self.get_files()

    def set_sort(self, sort):
        self.sort = sort
        if self.sort == SortBy.RELATED_IMAGE:
            for f, sf in self._files_cache.items():
                sf.set_related_image_path()
        return self.get_files()

    def current_file(self):
        if self.has_files():
            try:
                cursor = 0
                with self.cursor_lock:
                    cursor = self.file_cursor
                return self.get_files()[cursor]
            except Exception:
                with self.cursor_lock:
                    self.file_cursor = 0
                    return self.get_files()[self.file_cursor]
        else:
            return None

    def previous_file(self):
        files = self.get_files()
        if len(files) == 0:
            recursive_str = "" if self.recursive else _(" (try setting recursive to True)")
            raise Exception(_("No files found for current browsing settings.") + recursive_str)
        with self.cursor_lock:
            if self.file_cursor == 0:
                self.file_cursor = len(files) - 1
            else:
                self.file_cursor -= 1
            return files[self.file_cursor]

    def next_file(self):
        files = self.get_files()
        if len(files) == 0:
            recursive_str = "" if self.recursive else _(" (try setting recursive to True)")
            raise Exception(_("No files found for current browsing settings.") + recursive_str)
        with self.cursor_lock:
            if len(files) > self.file_cursor + 1:
                self.file_cursor += 1
            else:
                self.file_cursor = 0
        return files[self.file_cursor]

    def last_file(self):
        files = self.get_files()
        with self.cursor_lock:
            self.file_cursor = len(files) - 1
        return files[self.file_cursor]

    def load_file_paths_json(self):
        Utils.log("Loading external file paths from JSON: " + config.file_paths_json_path)
        with open(config.file_paths_json_path, "r") as f:
            return json.load(f)

    def update_json_for_removed_files(self, removed_file_paths=[]):
        if len(removed_file_paths) == 0:
            return

        files = list(self.get_files())
        for removed_filepath in removed_file_paths:
            files.remove(removed_filepath)

        with open(config.file_paths_json_path,"w") as f:
            json.dump(files, f, indent=4)
            Utils.log("JSON file updated: " + config.file_paths_json_path)

    def get_index_details(self):
        files = self.get_files()
        return _("FILE_BROWSER_INDEX_DETAILS").format(self.file_cursor+1, len(files), self.sort_by.get_text(), self.sort.get_text())

    def go_to_file(self, filepath):
        files = self.get_files()
        if filepath in files:
            self.file_cursor = files.index(filepath)

    def random_file(self):
        files = self.get_files()
        random_file = choice(files)
        self.file_cursor = files.index(random_file)
        return random_file

    def select_series(self, start_file, end_file):
        files = self.get_files()
        selected = []
        if start_file in files and end_file in files:
            start_index = files.index(start_file)
            end_index = files.index(end_file)
            if start_index > end_index:
                selected.extend(files[end_index:start_index+1])
            else:
                selected.extend(files[start_index:end_index+1])
        return selected

    def find(self, search_text=None, retry_with_delay=0, exact_match=False):
        if not search_text or search_text.strip() == "":
            raise Exception(_("Search text provided to file_browser.find() was invalid."))
        files = self.get_files_with_retry(retry_with_delay)
        # First try to match filename
        if search_text in files:
            self.file_cursor = files.index(search_text)
            if config.debug:
                Utils.log_debug(f"Index of {search_text}: {self.file_cursor}")
            return search_text
        filenames = [os.path.basename(f) for f in files]
        if search_text in filenames:
            self.file_cursor = filenames.index(search_text)
            if config.debug:
                Utils.log_debug(f"Index of {search_text}: {self.file_cursor}")
            return files[self.file_cursor]
        if exact_match:
            return None
        search_text = search_text.lower()
        # If that fails, match string to the start of file name
        for i in range(len(filenames)):
            filename = filenames[i]
            if filename.lower().startswith(search_text):
                if config.debug:
                    Utils.log_debug(f"Index of {filename}: {i}")
                self.file_cursor = i
                return files[self.file_cursor]
        # Finally try to match string anywhere within file name
        for i in range(len(filenames)):
            filename = files[i]
            if search_text in filename:
                if config.debug:
                    Utils.log_debug(f"Index of {filename}: {i}")
                self.file_cursor = i
                return files[self.file_cursor]
        return None

    def page_down(self, half_length=False):
        paging_length = self._get_paging_length(half_length=half_length)
        test_cursor = self.file_cursor + paging_length
        if test_cursor > len(self._files):
            test_cursor = 1
        with self.cursor_lock:
            self.file_cursor = test_cursor - 1
        return self.next_file()

    def page_up(self, half_length=False):
        paging_length = self._get_paging_length(half_length=half_length)
        test_cursor = self.file_cursor - paging_length
        if test_cursor < 0:
            test_cursor = -1
        with self.cursor_lock:
            self.file_cursor = test_cursor + 1
        return self.previous_file()

    def _get_paging_length(self, half_length=False):
        divisor = 20 if half_length else 10
        paging_length = int(len(self._files) / divisor)
        if paging_length > 200:
            return 200
        if paging_length == 0:
            return 1
        return paging_length

    def _get_sortable_files(self) -> List[SortableFile]:
        self._files = []
        if not self.use_file_paths_json and not os.path.exists(self.directory):
            return self._files

        files = []
        self._gather_files(files)

        # NOTE using a cache may result in incorrect sorting on refresh if files were renamed to the same as a previous file
        def cache_fileinfo(f):
            sortable_file = SortableFile(f)
            self._files_cache[f] = sortable_file
            return sortable_file
        self._files = [self._files_cache[f] if f in self._files_cache else cache_fileinfo(f) for f in files]
        return self._files

    def get_files(self) -> List[str]:
        if self.filepaths is None or len(self.filepaths) == 0:
            self.filepaths = self.get_sorted_filepaths(self._files)
        return self.filepaths

    def get_files_with_retry(self, retry_with_delay=0):
        files = self.get_files()
        if len(files) == 0 and retry_with_delay > 0:
            if retry_with_delay > 3:
                return files
            Utils.log_yellow(f"No files found, sleeping for {retry_with_delay} seconds and trying again...")
            sleep(retry_with_delay)
            return self.get_files_with_retry(retry_with_delay=retry_with_delay+1)
        return files

    def get_sorted_filepaths(self, sortable_files):
        if self.sort == Sort.RANDOM:
            sortable_files = list(sortable_files)
            shuffle(sortable_files)  # TODO technically should be caching the random sort state somehow
        else:
            reverse = self.sort == Sort.DESC

            if self.sort_by == SortBy.FULL_PATH:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
            elif self.sort_by == SortBy.NAME:
                sortable_files = Utils.alphanumeric_sort(sortable_files, text_lambda=lambda sf: sf.basename.lower(), reverse=reverse)
            elif self.sort_by == SortBy.CREATION_TIME:
                sortable_files.sort(key=lambda sf: sf.ctime, reverse=reverse)
            elif self.sort_by == SortBy.MODIFY_TIME:
                sortable_files.sort(key=lambda sf: sf.mtime, reverse=reverse)
            elif self.sort_by == SortBy.TYPE:
                # Sort by full path first, then by extension
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.extension.lower(), reverse=reverse)
            elif self.sort_by == SortBy.SIZE:
                # Sort by full path first, then by size
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.size, reverse=reverse)
            elif self.sort_by == SortBy.NAME_LENGTH:
                # Sort by full path first, then by name length
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.name_length, reverse=reverse)
            elif self.sort_by == SortBy.IMAGE_PIXELS:
                # Sort by full path first, then by total pixels
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.get_image_pixels(), reverse=reverse)
            elif self.sort_by == SortBy.IMAGE_HEIGHT:
                # Sort by full path first, then by height
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.get_image_height(), reverse=reverse)
            elif self.sort_by == SortBy.IMAGE_WIDTH:
                # Sort by full path first, then by width
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=reverse)
                sortable_files.sort(key=lambda sf: sf.get_image_width(), reverse=reverse)
            elif self.sort_by == SortBy.RELATED_IMAGE:
                sortable_files.sort(key=lambda sf: sf.get_related_image_or_self(), reverse=reverse)

        # After sorting, extract the file path only
        filepaths = [sf.full_file_path for sf in sortable_files]
        return filepaths

    def _gather_files(self, files=None):
        allowed_extensions = config.file_types
        if files is None:  # This is not the standard use case, only used in methods where we don't care about sorting
            self.filepaths.clear()
            files = self.filepaths

        if self.filter is not None and self.filter != "":
            if self.use_file_paths_json:
                filepaths = self.load_file_paths_json()
                filtered_files = [f for f in filepaths if re.search(self.filter, f)]
            else:
                pattern = "**/" + self.filter if self.recursive else self.filter
                if "*" not in pattern or (pattern.startswith("**") and not pattern.endswith("*")):
                    pattern += "*"
                recursive = self.recursive or self.filter.startswith("**/")
                filtered_files = glob.glob(os.path.join(self.directory, pattern), recursive=recursive)
            for f in filtered_files:
                for ext in allowed_extensions:
                    if f.lower().endswith(ext):
                        files.append(f)
        else:
            if self.use_file_paths_json:
                filepaths = self.load_file_paths_json()
            _ = "**/" if self.recursive else ""
            for ext in allowed_extensions:
                if self.use_file_paths_json:
                    files.extend([f for f in filepaths if f.lower().endswith(ext)])
                else:
                    files.extend(glob.glob(os.path.join(self.directory, _ + "*" + ext), recursive=self.recursive))
