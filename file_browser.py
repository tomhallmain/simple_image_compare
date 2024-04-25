from datetime import datetime
import os
from typing import List
import glob
from enum import Enum
from random import shuffle
import threading

from utils import alphanumeric_sort


class SortableFile:
    def __init__(self, full_file_path):
        self.full_file_path = full_file_path
        self.basename = os.path.basename(full_file_path)
        self.root, self.extension = os.path.splitext(self.basename)
        self.creation_time = datetime.fromtimestamp(os.path.getctime(full_file_path))
        self.size = os.path.getsize(full_file_path)
        self.tags = self.get_tags()

    def get_tags(self):
        tags = []

        try:
            pass
        except Exception:
            pass

        return tags

    def __eq__(self, other):
        if not isinstance(other, SortableFile):
            return False
        return (
            self.full_file_path == other.full_file_path
            and self.creation_time == other.creation_time
            and self.size == other.size
            )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.full_file_path, self.creation_time, self.size))

class SortBy(Enum):
    NAME = 0
    FULL_PATH = 1
    CREATION_TIME = 2
    TYPE = 3
    SIZE = 4
    RANDOMIZE = 5

class Sort(Enum):
    ASC = 1
    DESC = 2
    RANDOM = 3


# TODO on refresh, find the newly added files and set them in a list on this object, then enable slideshow for these files in app.py

class FileBrowser:
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

    def has_files(self):
        return len(self._files) > 0

    def set_recursive(self, recursive):
        self.recursive = recursive
        self.refresh()

    def toggle_recursive(self):
        self.set_recursive(not self.recursive)

    def refresh(self, refresh_cursor=True, file_check=False):
        last_files = self.get_files() if file_check else []
        if refresh_cursor:
            with self.cursor_lock:
                self.file_cursor = -1
        current_file = self.current_file() if file_check else None
        self.filepaths = []
        self._get_sortable_files()
        files = self.get_files()
        self.checking_files = len(files) > 0 and len(files) < 5000 # Avoid rechecking in directories with many files
        if file_check and current_file and os.path.isfile(current_file):
            with self.cursor_lock:
                self.file_cursor = files.index(current_file)
                if self.file_cursor > -1:
                    self.file_cursor -= 1
            self._new_files = list(set(files) - set(last_files))
        elif not refresh_cursor:
            with self.cursor_lock:
                if len(files) - 1 <= self.file_cursor:
                    self.file_cursor = -1
                else:
                    self.file_cursor -= 1
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
        return self.refresh()

    def set_sort_by(self, sort_by):
        self.sort_by = sort_by
        if self.sort_by == SortBy.RANDOMIZE:
            self.sort = Sort.RANDOM
        return self.get_files()

    def set_sort(self, sort):
        self.sort = sort
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
            recursive_str = "" if self.recursive else " (try setting recursive to True)"
            raise Exception("No files found for current browsing settings." + recursive_str)
        with self.cursor_lock:
            if self.file_cursor == 0:
                self.file_cursor = len(files) - 1
            else:
                self.file_cursor -= 1
            return files[self.file_cursor]

    def next_file(self):
        files = self.get_files()
        if len(files) == 0:
            recursive_str = "" if self.recursive else " (try setting recursive to True)"
            raise Exception("No files found for current browsing settings." + recursive_str)
        with self.cursor_lock:
            if len(files) > self.file_cursor + 1:
                self.file_cursor += 1
            else:
                self.file_cursor = 0
            return files[self.file_cursor]

    def go_to_file(self, filepath):
        files = self.get_files()
        if filepath in files:
            self.file_cursor = files.index(filepath)

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

    def page_down(self):
        paging_length = self._get_paging_length()
        test_cursor = self.file_cursor + paging_length
        if test_cursor > len(self._files):
            test_cursor = 1
        with self.cursor_lock:
            self.file_cursor = test_cursor - 1
        return self.next_file()

    def page_up(self):
        paging_length = self._get_paging_length()
        test_cursor = self.file_cursor - paging_length
        if test_cursor < 0:
            test_cursor = -1
        with self.cursor_lock:
            self.file_cursor = test_cursor + 1
        return self.previous_file()

    def _get_paging_length(self):
        tenth_of_total_count = int(len(self._files) / 10)
        if tenth_of_total_count > 200:
            return 200
        if tenth_of_total_count == 0:
            return 1
        return tenth_of_total_count

    def _get_sortable_files(self) -> List[SortableFile]:
        self._files = []
        if not os.path.exists(self.directory):
            return self._files

        files = []
        allowed_extensions = [".jpg", ".jpeg", ".png", ".tiff", ".webp"]

        if self.filter and self.filter != "":
            pattern = "**/" + self.filter if self.recursive else self.filter
            filtered_files = glob.glob(os.path.join(self.directory, pattern), recursive=self.recursive)
            for file in filtered_files:
                for ext in allowed_extensions:
                    if file.endswith(ext):
                        files.append(file)
        else:
            _ = "**/" if self.recursive else ""
            for ext in allowed_extensions:
                files.extend(glob.glob(os.path.join(self.directory, _ + "*" + ext), recursive=self.recursive))

        # NOTE using a cache may result in incorrect sorting if files were renamed to the same as a previous file
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

    def get_sorted_filepaths(self, sortable_files):
        if self.sort == Sort.RANDOM:
            shuffle(sortable_files) # TODO technically should be caching the random sort state somehow
        elif self.sort_by == SortBy.FULL_PATH:
            if self.sort == Sort.DESC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower())
        elif self.sort_by == SortBy.NAME:
            if self.sort == Sort.DESC:
                sortable_files = alphanumeric_sort(sortable_files, text_lambda=lambda sf: sf.basename.lower(), reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files = alphanumeric_sort(sortable_files, text_lambda=lambda sf: sf.basename.lower())
        elif self.sort_by == SortBy.CREATION_TIME:  
            if self.sort == Sort.DESC:
                sortable_files.sort(key=lambda sf: sf.creation_time, reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.creation_time)  
        elif self.sort_by == SortBy.TYPE:
            # Sort by full path first, then by extension
            if self.sort == Sort.DESC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=True)
                sortable_files.sort(key=lambda sf: sf.extension.lower(), reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower())
                sortable_files.sort(key=lambda sf: sf.extension.lower())
        elif self.sort_by == SortBy.SIZE:
            # Sort by full path first, then by extension
            if self.sort == Sort.DESC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower(), reverse=True)
                sortable_files.sort(key=lambda sf: sf.size, reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower())
                sortable_files.sort(key=lambda sf: sf.size)


        # After sorting, extract the file path only
        filepaths = [sf.full_file_path for sf in sortable_files]
        return filepaths
