from datetime import datetime
import os
from typing import List
import glob
from enum import Enum
from random import shuffle

class SortableFile:
    def __init__(self, full_file_path):
        self.full_file_path = full_file_path
        self.basename = os.path.basename(full_file_path)
        self.root, self.extension = os.path.splitext(self.basename)
        self.creation_time = datetime.fromtimestamp(os.path.getctime(full_file_path))
        self.size = os.path.getsize(full_file_path)

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
    def __init__(self, directory=".", recursive=False, filter=None):
        self.directory = directory
        self.recursive = recursive
        self.filter = filter
        self._files = []
        self._new_files = []
        self.filepaths = []
        self.sort_by = SortBy.NAME
        self.sort = Sort.ASC
        self.file_cursor = -1
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
            self.file_cursor = -1
        current_file = self.current_file() if file_check else None
        self.filepaths = []
        self._get_sortable_files()
        files = self.get_files()
        self.checking_files = len(files) > 0 and len(files) < 5000 # Avoid rechecking in directories with many files
        if file_check and current_file:
            self.file_cursor = files.index(current_file)
            if self.file_cursor > -1:
                self.file_cursor -= 1
            self._new_files = list(set(files) - set(last_files))
        elif not refresh_cursor:
            if len(files) - 1 <= self.file_cursor:
                self.file_cursor = -1
            else:
                self.file_cursor -= 1
        return files

    def update_cursor_to_new_images(self):
        if len(self._new_files) == 0:
            return
        self.file_cursor = self.filepaths.index(self._new_files[0]) - 1

    def set_directory(self, directory):
        self.directory = directory
        self.checking_files = True
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
                return self.get_files()[self.file_cursor]
            except Exception:
                self.file_cursor = 0
                return self.get_files()[self.file_cursor]
        else:
            return None

    def previous_file(self):
        files = self.get_files()
        if len(files) == 0:
            recursive_str = "" if self.recursive else " (try setting recursive to True)"
            raise Exception("No files found for current browsing settings." + recursive_str)
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
        if len(files) > self.file_cursor + 1:
            self.file_cursor += 1
        else:
            self.file_cursor = 0
        return files[self.file_cursor]

    def _get_sortable_files(self) -> List[SortableFile]:
        if not os.path.exists(self.directory):
            self._files = []
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
        self._files = [SortableFile(f) for f in files]
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
                sortable_files.sort(key=lambda sf: sf.basename.lower(), reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.basename.lower())
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
                sortable_files.sort(key=sf.size, reverse=True)
            elif self.sort == Sort.ASC:
                sortable_files.sort(key=lambda sf: sf.full_file_path.lower())
                sortable_files.sort(key=sf.size)


        # After sorting, extract the file path only
        filepaths = [sf.full_file_path for sf in sortable_files]
        return filepaths
