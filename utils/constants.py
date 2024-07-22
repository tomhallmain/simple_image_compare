from enum import Enum

from utils.translations import I18N
_ = I18N._


class Mode(Enum):
    BROWSE = _("Browsing Mode")
    SEARCH = _("Searching Mode")
    GROUP = _("Group Comparison Mode")
    DUPLICATES = _("Duplicate Detection Mode")

    def __str__(self):
        return self.value

class CompareMode(Enum):
    COLOR_MATCHING = _("Color Matching")
    CLIP_EMBEDDING = _("CLIP Embedding")
#    PROMPTS = _("Prompts")

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
            return _("Color diff threshold")
        if self == CompareMode.CLIP_EMBEDDING:
            return _("Embedding similarity threshold")
    
    def threshold_vals(self):
        if self == CompareMode.COLOR_MATCHING:
            return [str(i) for i in list(range(31))]
        if self == CompareMode.CLIP_EMBEDDING:
            return [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.98, 0.99]

class SortBy(Enum):
    NAME = _("Name")
    FULL_PATH = _("Full Path")
    CREATION_TIME = _("Creation Time")
    MODIFY_TIME = _("Modify Time")
    TYPE = _("Type")
    SIZE = _("Size")
    NAME_LENGTH = _("Name Length")
    RANDOMIZE = _("Random")

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
    ASC = _("ascending")
    DESC = _("descending")
    RANDOM = _("random")

    def __str__(self):
        return self.value



class ImageGenerationType(Enum):
    REDO_PROMPT= "redo_prompt"
    CONTROL_NET = "control_net"
    IP_ADAPTER = "ip_adapter"
    RENOISER = "renoiser"

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in ImageGenerationType.__members__.items():
            if str(value) == name:
                return value
        raise Exception(f"Not a valid prompt mode: {name}")

    @staticmethod
    def members():
        return [str(value) for key, value in ImageGenerationType.__members__.items()]
