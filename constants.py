from enum import Enum


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


