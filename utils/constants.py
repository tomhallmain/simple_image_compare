from enum import Enum

from utils.translations import I18N
_ = I18N._


class Mode(Enum):
    BROWSE = _("Browsing Mode")
    SEARCH = _("Searching Mode")
    GROUP = _("Group Comparison Mode")
    DUPLICATES = _("Duplicate Detection Mode")

    # NOTE need this method because this class is initialized before the config
    # locale overwrites the default I18N settings.
    def get_text(self):
        if self == Mode.BROWSE:
            return _("Browsing Mode")
        elif self == Mode.SEARCH:
            return _("Searching Mode")
        elif self == Mode.GROUP:
            return _("Group Comparison Mode")
        elif self == Mode.DUPLICATES:
            return _("Duplicate Detection Mode")
        raise Exception("Unhandled Mode text: " + str(self))

    def __str__(self):
        return self.value


class CompareMode(Enum):
    COLOR_MATCHING = _("Color Matching")
    CLIP_EMBEDDING = _("CLIP Embedding")
#    PROMPTS = _("Prompts")

    def get_text(self):
        if self == CompareMode.COLOR_MATCHING:
            return _("Color Matching")
        elif self == CompareMode.CLIP_EMBEDDING:
            return _("CLIP Embedding")
        raise Exception("Unhandled Compare Mode text: " + str(self))

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in CompareMode.__members__.items():
            if value.get_text() == name or value.value == name:
                return value
        raise Exception(f"Not a valid compare mode: {name}")

    @staticmethod
    def members():
        return [value.get_text() for key, value in CompareMode.__members__.items()]

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
    RELATED_IMAGE = _("Related Image")
    RANDOMIZE = _("Random")

    def get_text(self):
        if self == SortBy.NAME:
            return _("Name")
        elif self == SortBy.FULL_PATH:
            return _("Full Path")
        elif self == SortBy.CREATION_TIME:
            return _("Creation Time")
        elif self == SortBy.MODIFY_TIME:
            return _("Modify Time")
        elif self == SortBy.TYPE:
            return _("Type")
        elif self == SortBy.SIZE:
            return _("Size")
        elif self == SortBy.NAME_LENGTH:
            return _("Name Length")
        elif self == SortBy.RELATED_IMAGE:
            return _("Related Image")
        elif self == SortBy.RANDOMIZE:
            return _("Random")
        raise Exception("Unhandled Sort By text: " + str(self))

    def __str__(self):
        return self.value

    @staticmethod
    def get(name):
        for key, value in SortBy.__members__.items():
            if str(value.value) == name or value.get_text() == name:
                return value
        raise Exception(f"Not a valid sort by: {name}")

    @staticmethod
    def members():
        return [value.get_text() for key, value in SortBy.__members__.items()]


class Sort(Enum):
    ASC = _("ascending")
    DESC = _("descending")
    RANDOM = _("random")

    def get_text(self):
        return _(self.value)

    def __str__(self):
        return self.value


class ImageGenerationType(Enum):
    REDO_PROMPT = "redo_prompt"
    CONTROL_NET = "control_net"
    IP_ADAPTER = "ip_adapter"
    RENOISER = "renoiser"
    LAST_SETTINGS = "last_settings"
    CANCEL = "cancel"
    REVERT_TO_SIMPLE_GEN = "revert_to_simple_gen"

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


class Direction(Enum):
    FORWARD = "forward"
    BACKWARD = "back"

    def get_correction(self, backward_value=0):
        return backward_value if self == Direction.BACKWARD else -1

