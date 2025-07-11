from enum import Enum

from utils.translations import I18N
_ = I18N._


class AppInfo:
    SERVICE_NAME = "MyPersonalApplicationsService"
    APP_IDENTIFIER = "simple_image_compare"


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
    SIGLIP_EMBEDDING = _("SigLIP Embedding")
    FLAVA_EMBEDDING = _("FLAVA Embedding")
    ALIGN_EMBEDDING = _("ALIGN Embedding")
    XVLM_EMBEDDING = _("X-VLM Embedding")
#    PROMPTS = _("Prompts")

    def get_text(self):
        if self == CompareMode.COLOR_MATCHING:
            return _("Color Matching")
        elif self == CompareMode.CLIP_EMBEDDING:
            return _("CLIP Embedding")
        elif self == CompareMode.SIGLIP_EMBEDDING:
            return _("SigLIP Embedding")
        elif self == CompareMode.FLAVA_EMBEDDING:
            return _("FLAVA Embedding")
        elif self == CompareMode.ALIGN_EMBEDDING:
            return _("ALIGN Embedding")
        elif self == CompareMode.XVLM_EMBEDDING:
            return _("X-VLM Embedding")
#        elif self == CompareMode.PROMPTS:
#            return _("Prompts")
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
        if self.is_embedding():
            return _("Embedding similarity threshold")
        raise Exception("Unhandled Compare Mode text: " + str(self))

    def threshold_vals(self):
        if self == CompareMode.COLOR_MATCHING:
            return [str(i) for i in list(range(31))]
        if self.is_embedding():
            return [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.925, 0.95, 0.98, 0.99]

    def is_embedding(self):
        return self != CompareMode.COLOR_MATCHING

    def embedding_modes():
        return [mode for mode in CompareMode if mode.is_embedding()]


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
    IMAGE_PIXELS = _("Image Pixels")
    IMAGE_HEIGHT = _("Image Height")
    IMAGE_WIDTH = _("Image Width")

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
        elif self == SortBy.IMAGE_PIXELS:
            return _("Image Pixels")
        elif self == SortBy.IMAGE_HEIGHT:
            return _("Image Height")
        elif self == SortBy.IMAGE_WIDTH:
            return _("Image Width")
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


class CompareMediaType(Enum):
    """Enumeration of supported media types for comparison."""
    IMAGE = "image"
    GIF = "gif"
    VIDEO = "video"
    PDF = "pdf"
    SVG = "svg"
    HTML = "html"

    def get_translation(self):
        """Get the translated string for this media type."""
        if self == CompareMediaType.IMAGE:
            return _("Image")
        elif self == CompareMediaType.GIF:
            return _("GIF")
        elif self == CompareMediaType.VIDEO:
            return _("Video")
        elif self == CompareMediaType.PDF:
            return _("PDF")
        elif self == CompareMediaType.SVG:
            return _("SVG")
        elif self == CompareMediaType.HTML:
            return _("HTML")
        raise Exception("Unhandled media type translation: " + str(self))


class ActionType(Enum):
    """Enumeration of supported action types for notifications."""
    MOVE_FILE = "move_file"
    COPY_FILE = "copy_file"
    REMOVE_FILE = "remove_file"
    MARK_FILE = "mark_file"
    UNMARK_FILE = "unmark_file"
    SEARCH_FILE = "search_file"
    COMPARE_FILES = "compare_files"
    GENERATE_IMAGE = "generate_image"
    CHANGE_DIRECTORY = "change_directory"
    SYSTEM = "system"  # For general system notifications

    def get_translation(self):
        """Get the translated string for this action type."""
        if self == ActionType.MOVE_FILE:
            return _("Moved files")
        elif self == ActionType.COPY_FILE:
            return _("Copied files")
        elif self == ActionType.REMOVE_FILE:
            return _("Removed files")
        elif self == ActionType.MARK_FILE:
            return _("Marked files")
        elif self == ActionType.UNMARK_FILE:
            return _("Unmarked files")
        elif self == ActionType.SEARCH_FILE:
            return _("Searched files")
        elif self == ActionType.COMPARE_FILES:
            return _("Compared files")
        elif self == ActionType.GENERATE_IMAGE:
            return _("Generated images")
        elif self == ActionType.CHANGE_DIRECTORY:
            return _("Changed directory")
        elif self == ActionType.SYSTEM:
            return _("System")
        raise Exception("Unhandled action type translation: " + str(self))


class ProtectedActions(Enum):
    """Enumeration of actions that can be password protected."""
    RUN_COMPARES = "run_compares"
    RUN_SEARCH = "run_search"
    RUN_SEARCH_PRESET = "run_search_preset"
    VIEW_MEDIA_DETAILS = "view_media_details"
    VIEW_RECENT_DIRECTORIES = "view_recent_directories"
    VIEW_FILE_ACTIONS = "view_file_actions"
    RUN_FILE_ACTIONS = "run_file_actions"
    EDIT_PREVALIDATIONS = "edit_prevalidations"
    RUN_PREVALIDATIONS = "run_prevalidations"
    RUN_IMAGE_GENERATION = "run_image_generation"
    RUN_REFACDIR = "run_refacdir"
    DELETE_MEDIA = "delete_media"
    CONFIGURE_MEDIA_TYPES = "configure_media_types"
    START_APPLICATION = "start_application"
    ACCESS_ADMIN = "access_admin"
    
    @staticmethod
    def get_action(action_name: str):
        """Get the ProtectedActions enum value for a given action name."""
        try:
            return ProtectedActions(action_name.lower().replace(" ", "_"))
        except ValueError:
            return None

    def get_description(self):
        """Get the user-friendly description for this action."""
        descriptions = {
            ProtectedActions.RUN_COMPARES: _("Run Compares"),
            ProtectedActions.RUN_SEARCH: _("Run Search"),
            ProtectedActions.RUN_SEARCH_PRESET: _("Run Search Preset"),
            ProtectedActions.VIEW_MEDIA_DETAILS: _("View Media Details"),
            ProtectedActions.VIEW_RECENT_DIRECTORIES: _("View Recent Directories"),
            ProtectedActions.VIEW_FILE_ACTIONS: _("View File Actions"),
            ProtectedActions.RUN_FILE_ACTIONS: _("Run File Actions"),
            ProtectedActions.EDIT_PREVALIDATIONS: _("Edit Prevalidations"),
            ProtectedActions.RUN_PREVALIDATIONS: _("Run Prevalidations"),
            ProtectedActions.RUN_IMAGE_GENERATION: _("Run Image Generation"),
            ProtectedActions.RUN_REFACDIR: _("Run RefacDir"),
            ProtectedActions.DELETE_MEDIA: _("Delete Media"),
            ProtectedActions.CONFIGURE_MEDIA_TYPES: _("Configure Media Types"),
            ProtectedActions.START_APPLICATION: _("Start Application"),
            ProtectedActions.ACCESS_ADMIN: _("Access Password Administration")
        }
        return descriptions.get(self, self.value)
