from enum import Enum


class Mode(Enum):
    BROWSE = "Browsing Mode"
    SEARCH = "Searching Mode"
    GROUP = "Group Comparison Mode"
    DUPLICATES = "Duplicate Detection Mode"

    def __str__(self):
        return self.value

class CompareMode(Enum):
    COLOR_MATCHING = "Color Matching"
    CLIP_EMBEDDING = "CLIP Embedding"

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in CompareMode.__members__.items():
            if str(value) == name:
                return value
        raise Exception(f"Not a valid prompt mode: {name}")

    @staticmethod
    def members():
        return [str(value) for key, value in CompareMode.__members__.items()]

    def threshold_str(self):
        if self == CompareMode.COLOR_MATCHING:
            return "Color diff threshold"
        if self == CompareMode.CLIP_EMBEDDING:
            return "Embedding similarity threshold"
    
    def threshold_vals(self):
        if self == CompareMode.COLOR_MATCHING:
            return [str(i) for i in list(range(31))]
        if self == CompareMode.CLIP_EMBEDDING:
            return [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.98, 0.99]

class SortBy(Enum):
    NAME = "Name"
    FULL_PATH = "Full Path"
    CREATION_TIME = "Creation Time"
    MODIFY_TIME = "Modify Time"
    TYPE = "Type"
    SIZE = "Size"
    NAME_LENGTH = "Name Length"
    RANDOMIZE = "Random"

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in SortBy.__members__.items():
            if str(value) == name:
                return value
        raise Exception(f"Not a valid prompt mode: {name}")

    @staticmethod
    def members():
        return [str(value) for key, value in SortBy.__members__.items()]

class Sort(Enum):
    ASC = "ascending"
    DESC = "descending"
    RANDOM = "random"

    def __str__(self):
        return self.value


