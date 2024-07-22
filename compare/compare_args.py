

from utils.config import config
from utils.constants import Mode

class CompareArgs:
    def __init__(self, base_dir=".", listener=None, mode=Mode.GROUP, recursive=True, searching_image=False,
                 search_file_path=None, search_text=None, search_text_negative=None, find_duplicates=False,
                 counter_limit=config.file_counter_limit, compare_threshold=config.embedding_similarity_threshold,
                 compare_faces=False, inclusion_pattern=None, overwrite=False, store_checkpoints=config.store_checkpoints):
        self.base_dir = base_dir
        self.listener = listener
        self.mode = mode
        self.recursive = recursive
        self.searching_image = searching_image
        self.search_file_path = search_file_path
        self.negative_search_file_path = None
        self.search_text = search_text
        self.search_text_negative = search_text_negative
        self.find_duplicates = find_duplicates
        self.counter_limit = counter_limit
        self.threshold = compare_threshold
        self.compare_faces = compare_faces
        self.inclusion_pattern = inclusion_pattern
        self.overwrite = overwrite
        self.store_checkpoints = store_checkpoints
        self.include_gifs = False
        self.match_dims = False
        self.verbose = True

    def _is_new_data_request_required(self, other):
        return (self.threshold != other.threshold
                or self.counter_limit != other.counter_limit
                or self.inclusion_pattern != other.inclusion_pattern
                or self.recursive != other.recursive
                or (not self.overwrite and other.overwrite))
