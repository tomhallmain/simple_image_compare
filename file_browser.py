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

class SortBy(Enum):
    NAME = 0
    FULL_PATH = 1
    CREATION_TIME = 2
    TYPE = 3

class Sort(Enum):
    ASC = 1
    DESC = 2
    RANDOM = 3
    

class FileBrowser:
    def __init__(self, directory=".", recursive=True, filter=None):
        self.directory = directory
        self.recursive = recursive
        self.filter = filter
        self._files = []
        self.filepaths = []
        self.sort_by = SortBy.NAME
        self.sort = Sort.ASC
        self.file_cursor = -1
    
    def refresh(self):
        self.file_cursor = -1
        self.filepaths = []
        self._get_sortable_files()
        return self.get_files()

    def set_directory(self, directory):
        self.directory = directory
        return self.refresh()

    def set_sort_by(self, sort_by):
        self.sort_by = sort_by
        return self.get_files()

    def set_sort(self, sort):
        self.sort = sort
        return self.get_files()

    def previous_file(self):
        files = self.get_files()
        if len(files) == 0:
            raise Exception("No files found for current browsing settings.")
        if self.file_cursor == 0:
            self.file_cursor = len(files) - 1
        else:
            self.file_cursor -= 1
        return files[self.file_cursor]

    def next_file(self):
        files = self.get_files()
        if len(files) == 0:
            raise Exception("No files found for current browsing settings.")
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
            shuffle(sortable_files)
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

        # After sorting, extract the file path only
        filepaths = [sf.full_file_path for sf in sortable_files]
        return filepaths