from glob import glob
import os
import random
import sys

import cv2

from compare.compare_args import CompareArgs
from compare.compare_data import CompareData
from compare.compare_result import CompareResult
from image.frame_cache import FrameCache
from utils.config import config
from utils.constants import CompareMode
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._


def gather_files(base_dir=".", exts=config.image_types, recursive=True, include_videos=False, include_gifs=False, include_pdfs=False):
    files = []
    recursive_str = "**/" if recursive else ""
    exts = exts[:]
    
    # Add video types if enabled (excluding GIFs)
    if include_videos:
        for ext in config.video_types:
            if ext != '.gif' and ext not in exts:
                exts.append(ext)
    else:
        exts = [e for e in exts if e not in config.video_types or e == '.gif']
    
    # Add GIF if enabled
    if include_gifs and '.gif' not in exts:
        exts.append('.gif')
    elif not include_gifs and '.gif' in exts:
        exts.remove('.gif')
    
    # Add PDF if enabled
    if include_pdfs and '.pdf' not in exts:
        exts.append('.pdf')
    elif not include_pdfs and '.pdf' in exts:
        exts.remove('.pdf')
    
    for ext in exts:
        pattern = os.path.join(base_dir, recursive_str + "*" + ext)
        files.extend(glob(pattern, recursive=recursive))
    return files


class BaseCompare:
    def __init__(self, args=CompareArgs(), gather_files_func=gather_files):
        self.args = args
        self.files = []
        self.set_base_dir(self.args.base_dir)
        self.set_search_file_path(self.args.search_file_path)
        self.compare_faces = self.args.compare_faces
        # self.args.match_dims = match_dims
        self.verbose = self.args.verbose
        self.progress_listener = self.args.listener
        self._faceCascade = None
        if self.compare_faces:
            self._set_face_cascade()
        self.gather_files_func = gather_files_func
        self.compare_result = CompareResult(base_dir=self.args.base_dir)

    @staticmethod
    def calculate_chunk_size(embeddings, max_mem_gb=None):
        """
        Calculate the number of rows (M) to process per chunk.
        :param embeddings: N x D numpy array of embeddings.
        :param max_mem_gb: Maximum memory to allocate for a chunk (e.g., 4 GB).
        """
        if max_mem_gb is None or max_mem_gb < 0:
            max_mem_gb = Utils.calculate_available_ram() - 1.0
        n, d = embeddings.shape
        bytes_per_row = d * embeddings.dtype.itemsize  # e.g., 512 * 4 bytes (float32)
        max_rows_per_chunk = int((max_mem_gb * 1e9) / (n * bytes_per_row))
        return max(1, max_rows_per_chunk)  # Ensure at least 1 row per chunk

    def get_similarity_threshold(self):
        return -1.0 # overridden method

    def set_similarity_threshold(self, threshold):
        return None

    def set_base_dir(self, base_dir):
        '''
        Set the base directory and prepare cache file references.
        '''
        self.base_dir = base_dir
        if self.args.compare_mode == CompareMode.COLOR_MATCHING:
            self.compare_data = CompareData(
                base_dir=base_dir, mode=self.args.compare_mode, use_thumb=self.use_thumb)
        else:
            self.compare_data = CompareData(
                base_dir=base_dir, mode=self.args.compare_mode)
        self.compare_result = CompareResult(base_dir=base_dir)

    def set_search_file_path(self, search_file_path):
        '''
        Set the search file path. If it is already in the found data, move the
        reference to it to the first index in the list.
        '''
        self.search_file_path = search_file_path
        self.is_run_search = search_file_path is not None
        if self.is_run_search and self.files is not None:
            if self.search_file_path in self.files:
                self.files.remove(self.search_file_path)
            self.search_file_index = 0
            self.files.insert(self.search_file_index, self.search_file_path)

    def get_files(self):
        '''
        Get all image files in the base dir as requested by the parameters.

        To override the default file inclusion behavior, pass a gather_files_func to the Compare object.
        '''
        if self.gather_files_func:
            exts = config.image_types
            if self.args.include_gifs and ".gif" not in exts:
                exts.append(".gif")
            self.files = self.gather_files_func(
                base_dir=self.base_dir, exts=exts, recursive=self.args.recursive, include_videos=self.args.include_videos, include_gifs=self.args.include_gifs, include_pdfs=self.args.include_pdfs)
        else:
            raise Exception("No gather files function found.")
        self.files.sort()
        self.compare_data.has_new_file_data = False
        self.max_files_processed = min(
            self.args.counter_limit, len(self.files))
        self.max_files_processed_even = Utils.round_up(
            self.max_files_processed, 200)

        if self.is_run_search:
            if self.search_file_path in self.files:
                self.files.remove(self.search_file_path)
            self.search_file_index = 0
            self.files.insert(self.search_file_index, self.search_file_path)

        if self.verbose:
            self.print_settings()

    def get_image_path(self, path: str) -> str:
        """
        Get the image path for a file, using FrameCache if needed.
        Returns the original path if no frame extraction is needed.
        """
        return FrameCache.get_image_path(path)

    def get_data(self):
        pass

    def _handle_progress(self, counter, total, gathering_data=True):
        percent_complete = counter / total * 100
        if percent_complete % 10 == 0 or counter % 500 == 0:
            if self.verbose:
                desc1 = "data gathered" if gathering_data else "compared"
                print(str(int(percent_complete)) + "% " + desc1)
            else:
                print(".", end="", flush=True)
            if self.progress_listener and sys.platform != "darwin":
                # TODO there is a bug with updating master here on OSX for some reason.
                desc2 = _("Image data collection") if gathering_data else _(
                    "Image comparison")
                self.progress_listener.update(desc2, percent_complete)

    def print_settings(self):
        pass

    def _set_face_cascade(self):
        '''
        Load the face recognition model if compare_faces option was requested.
        '''
        cascPath = ""
        for minor_version in range(10, 5, -1):
            cascPath = "/usr/local/lib/python3." + \
                str(minor_version) + \
                "/site-packages/cv2/data/haarcascade_frontalface_default.xml"
            if os.path.exists(cascPath):
                break
        if not os.path.exists(cascPath):
            print("WARNING: Face cascade model not found (cv2 package,"
                  + " Python version 3.6 or greater expected)")
            print("Run with flag --faces=False to avoid this warning.")
            self.compare_faces = False
        else:
            self._faceCascade = cv2.CascadeClassifier(cascPath)

    def _get_faces_count(self, filepath):
        '''
        Try to get the number of faces in the image using the face model.
        '''
        n_faces = random.random() * 10000 + 6  # Set to a value unlikely to match
        try:
            gray = cv2.imread(filepath, 0)
            faces = self._faceCascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            n_faces = len(faces)
        except Exception as e:
            if self.verbose:
                print(e)
        return n_faces

    def run(self):
        pass

    def run_search(self):
        pass

    def run_comparison(self, store_checkpoints=False):
        pass

    def find_similars_to_image(self, search_path, search_file_index):
        pass

    def remove_from_groups(self, removed_files=[]):
        pass

    def readd_files(self, filepaths=[]):
        pass
