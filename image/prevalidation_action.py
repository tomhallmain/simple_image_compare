
from enum import Enum
from utils.translations import I18N

_ = I18N._


class PrevalidationAction(Enum):
    SKIP = "SKIP"
    HIDE = "HIDE"
    NOTIFY = "NOTIFY"
    MOVE = "MOVE"
    COPY = "COPY"
    DELETE = "DELETE"
    ADD_MARK = "ADD_MARK"

    def is_cache_type(self):
        # If the action is not one of these types, it should have been moved out of the directory.
        return (self == PrevalidationAction.HIDE or self == PrevalidationAction.NOTIFY 
            or self == PrevalidationAction.SKIP or self == PrevalidationAction.ADD_MARK)

    def get_translation(self):
        if self == PrevalidationAction.HIDE:
            return _("Hide")
        elif self == PrevalidationAction.NOTIFY:
            return _("Notify")
        elif self == PrevalidationAction.SKIP:
            return _("Skip")
        elif self == PrevalidationAction.MOVE:
            return _("Move")
        elif self == PrevalidationAction.COPY:
            return _("Copy")
        elif self == PrevalidationAction.DELETE:
            return _("Delete")
        elif self == PrevalidationAction.ADD_MARK:
            return _("Add Mark")
        raise Exception("Prevalidation action translation not found: " + str(self))

    @staticmethod
    def get_action(action_name):
        for name, value in PrevalidationAction.__members__.items():
            if action_name.upper() == name.upper() or action_name == value.get_translation():
                return value
        raise Exception("Invalid prevalidation action: " + action_name)



