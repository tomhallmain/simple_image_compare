
from enum import Enum

class PrevalidationAction(Enum):
    SKIP = "SKIP"
    HIDE = "HIDE"
    NOTIFY = "NOTIFY"
    MOVE = "MOVE"
    COPY = "COPY"
    DELETE = "DELETE"

    def is_cache_type(self):
        # If the action is not one of these types, it should have been moved out of the directory.
        return self == PrevalidationAction.HIDE or self == PrevalidationAction.NOTIFY or self == PrevalidationAction.SKIP

    @staticmethod
    def get_action(action_name):
        for name, value in PrevalidationAction.__members__.items():
            if action_name.upper() == name:
                return value
        raise Exception("Invalid prevalidation action: " + action_name)



