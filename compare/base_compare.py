from glob import glob
import os
import random

import cv2

from compare.compare_args import CompareArgs
from utils.config import config


def gather_files(base_dir=".", exts=config.file_types, recursive=True):
    files = []
    recursive_str = "**/" if recursive else ""
    for ext in exts:
        pattern = os.path.join(base_dir, recursive_str + "*" + ext)
        files.extend(glob(pattern, recursive=recursive))
    return files


def round_up(number, to):
    if number % to == 0:
        return number
    else:
        return number - (number % to) + to


def safe_write(textfile, data):
    try:
        textfile.write(data)
    except UnicodeEncodeError as e:
        print(e)


def is_invalid_file(file_path, counter, run_search, inclusion_pattern):
    if file_path is None:
        return True
    elif run_search and counter == 0:
        return False
    elif inclusion_pattern is not None:
        return inclusion_pattern not in file_path
    else:
        return False


def get_valid_file(base_dir, input_filepath):
    if (not isinstance(input_filepath, str) or input_filepath is None
            or input_filepath.strip() == ""):
        return None
    if input_filepath.startswith('"') and input_filepath.endswith('"'):
        input_filepath = input_filepath[1:-1]
    elif input_filepath.startswith("'") and input_filepath.endswith("'"):
        input_filepath = input_filepath[1:-1]
    if os.path.exists(input_filepath):
        return input_filepath
    elif base_dir is not None and os.path.exists(os.path.join(base_dir, input_filepath)):
        return base_dir + "/" + input_filepath
    else:
        return None


class BaseCompare:
    def __init__(self, args=CompareArgs(), gather_files_func=gather_files):
        self.args = args
        self.files = []
        self.set_base_dir(self.args.base_dir)
        self.set_search_file_path(self.args.search_file_path)
        self.compare_faces = self.args.compare_faces
#        self.args.match_dims = match_dims
        self.verbose = self.args.verbose
        self.progress_listener = self.args.listener
        self._faceCascade = None
        if self.compare_faces:
            self._set_face_cascade()
        self.gather_files_func = gather_files_func

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
        self._files_found = []
        if self.gather_files_func:
            exts = config.file_types
            if self.args.include_gifs:
                exts.append(".gif")
            self.files = self.gather_files_func(
                base_dir=self.base_dir, exts=exts, recursive=self.args.recursive)
        else:
            raise Exception("No gather files function found.")
        self.files.sort()
        self.has_new_file_data = False
        self.max_files_processed = min(
            self.args.counter_limit, len(self.files))
        self.max_files_processed_even = round_up(self.max_files_processed, 200)

        if self.is_run_search:
            if self.search_file_path in self.files:
                self.files.remove(self.search_file_path)
            self.search_file_index = 0
            self.files.insert(self.search_file_index, self.search_file_path)

        if self.verbose:
            self.print_settings()

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

    def run_comparison(self):
        pass

    def find_similars_to_image(self, search_path, search_file_index):
        pass

    def remove_from_groups(self, removed_files=[]):
        pass

    def readd_files(self, filepaths=[]):
        pass
