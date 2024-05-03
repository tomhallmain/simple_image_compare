from enum import Enum


class Mode(Enum):
    BROWSE = 1
    SEARCH = 2
    GROUP = 3
    DUPLICATES = 4

    def readable_str(self):
        if self == Mode.BROWSE:
            return "Browsing Mode"
        if self == Mode.SEARCH:
            return "Searching Mode"
        if self == Mode.GROUP:
            return "Group Comparison Mode"
        if self == Mode.DUPLICATES:
            return "Duplicate Detection Mode"

class CompareMode(Enum):
    COLOR_MATCHING = 1
    CLIP_EMBEDDING = 2

    def readable_str(self):
        if self == CompareMode.COLOR_MATCHING:
            return "Compare Colors"
        if self == CompareMode.CLIP_EMBEDDING:
            return "Compare CLIP"

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


