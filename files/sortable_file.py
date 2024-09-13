from datetime import datetime
import os

from image.image_data_extractor import image_data_extractor


class SortableFile:
    def __init__(self, full_file_path):
        self.full_file_path = full_file_path
        self.basename = os.path.basename(full_file_path)
        self.name_length = len(self.basename)
        self.root, self.extension = os.path.splitext(self.basename)
        self.related_image_path = None
        try:
            stat_obj = os.stat(full_file_path)
            self.ctime = datetime.fromtimestamp(stat_obj.st_ctime)
            self.mtime = datetime.fromtimestamp(stat_obj.st_mtime)
            self.size = stat_obj.st_size
        except Exception:
            self.ctime = datetime.fromtimestamp(0)
            self.mtime = datetime.fromtimestamp(0)
            self.size = 0
        self.tags = self.get_tags()

    def get_tags(self):
        tags = []

        # TODO
        # try:
        #     pass
        # except Exception:
        #     pass

        return tags

    def set_related_image_path(self):
        self.related_image_path = image_data_extractor.get_related_image_path(self.full_file_path)
        if self.related_image_path is None:
            self.related_image_path = ""

    def get_related_image_or_self(self):
        if self.related_image_path is None:
            self.set_related_image_path()
            return self.get_related_image_or_self()
        elif len(self.related_image_path) > 0:
            return self.related_image_path
        else:
            return self.full_file_path

    def __eq__(self, other):
        if not isinstance(other, SortableFile):
            return False
        return (
            self.full_file_path == other.full_file_path
            and self.ctime == other.ctime
            and self.mtime == other.mtime
            and self.size == other.size
            )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.full_file_path, self.ctime, self.mtime, self.size))