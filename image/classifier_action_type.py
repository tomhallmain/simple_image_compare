
from enum import Enum
from utils.translations import I18N

_ = I18N._


class ClassifierActionType(Enum):
    SKIP = "SKIP"
    HIDE = "HIDE"
    NOTIFY = "NOTIFY"
    MOVE = "MOVE"
    COPY = "COPY"
    DELETE = "DELETE"
    ADD_MARK = "ADD_MARK"

    def is_cache_type(self):
        # If the action is not one of these types, it should have been moved out of the directory.
        return (self == ClassifierActionType.HIDE or self == ClassifierActionType.NOTIFY 
            or self == ClassifierActionType.SKIP or self == ClassifierActionType.ADD_MARK)

    def get_translation(self):
        if self == ClassifierActionType.HIDE:
            return _("Hide")
        elif self == ClassifierActionType.NOTIFY:
            return _("Notify")
        elif self == ClassifierActionType.SKIP:
            return _("Skip")
        elif self == ClassifierActionType.MOVE:
            return _("Move")
        elif self == ClassifierActionType.COPY:
            return _("Copy")
        elif self == ClassifierActionType.DELETE:
            return _("Delete")
        elif self == ClassifierActionType.ADD_MARK:
            return _("Add Mark")
        raise Exception("Prevalidation action translation not found: " + str(self))

    @staticmethod
    def get_action(action_name):
        for name, value in ClassifierActionType.__members__.items():
            if action_name.upper() == name.upper() or action_name == value.get_translation():
                return value
        raise Exception("Invalid prevalidation action: " + action_name)



