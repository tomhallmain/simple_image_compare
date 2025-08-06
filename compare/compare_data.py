import os
import pickle

from utils.constants import CompareMode
from utils.logging_setup import get_logger

logger = get_logger("compare_data")


class CompareData:

    EMBEDDINGS_DATA = "image_embeddings.pkl"
    EMBEDDINGS_SIGLIP_DATA = "image_embeddings_siglip.pkl"
    EMBEDDINGS_FLAVA_DATA = "image_embeddings_flava.pkl"
    EMBEDDINGS_ALIGN_DATA = "image_embeddings_align.pkl"
    EMBEDDINGS_XVLM_DATA = "image_embeddings_xvlm.pkl"
    EMBEDDINGS_LAION_DATA = "image_embeddings_laion.pkl"
    THUMB_COLORS_DATA = "image_thumb_colors.pkl"
    TOP_COLORS_DATA = "image_top_colors.pkl"
    FACES_DATA = "image_faces.pkl"

    def __init__(self, base_dir=".", mode=CompareMode.CLIP_EMBEDDING, use_thumb=False):
        self.base_dir = base_dir
        self.has_new_file_data = False
        self.files_found = []
        self.n_files_found = 0
        self.file_data_dict = {}
        self.file_faces_dict = {}
        self._file_faces_filepath = os.path.join(
            base_dir, CompareData.FACES_DATA)
        if mode == CompareMode.COLOR_MATCHING:
            if use_thumb:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.THUMB_COLORS_DATA)
            else:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.TOP_COLORS_DATA)
        elif mode.is_embedding():
            if mode == CompareMode.SIGLIP_EMBEDDING:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_SIGLIP_DATA)
            elif mode == CompareMode.FLAVA_EMBEDDING:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_FLAVA_DATA)
            elif mode == CompareMode.ALIGN_EMBEDDING:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_ALIGN_DATA)
            elif mode == CompareMode.XVLM_EMBEDDING:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_XVLM_DATA)
            elif mode == CompareMode.LAION_EMBEDDING:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_LAION_DATA)
            else:
                self._file_data_filepath = os.path.join(
                    base_dir, CompareData.EMBEDDINGS_DATA)
        else:
            raise Exception("Invalid mode")

    def load_data(self, overwrite=False, compare_faces=False):
        if overwrite or not os.path.exists(self._file_data_filepath):
            if not os.path.exists(self._file_data_filepath):
                logger.info("Image data not found so creating new cache"
                      + " - this may take a while.")
            elif overwrite:
                logger.info("Overwriting image data caches - this may take a while.")
            self.file_data_dict = {}
            self.file_faces_dict = {}
        else:
            with open(self._file_data_filepath, "rb") as f:
                self.file_data_dict = pickle.load(f)
            if compare_faces:
                with open(self._file_faces_filepath, "rb") as f:
                    self.file_faces_dict = pickle.load(f)
            else:
                self.file_faces_dict = {}

    def save_data(self, overwrite=False, verbose=False, compare_faces=False):
        if self.has_new_file_data or overwrite:
            with open(self._file_data_filepath, "wb") as store:
                pickle.dump(self.file_data_dict, store)
            if compare_faces:
                with open(self._file_faces_filepath, "wb") as store:
                    pickle.dump(self.file_faces_dict, store)
            self.file_data_dict = None
            self.file_faces_dict = None
            if verbose:
                if overwrite:
                    logger.info("Overwrote any pre-existing image data at:")
                else:
                    logger.info("Updated image data saved to: ")
                logger.info(self._file_data_filepath)
                if compare_faces:
                    logger.info(self._file_faces_filepath)

        self.n_files_found = len(self.files_found)

        if self.n_files_found == 0:
            raise AssertionError("No image data found for comparison with"
                                 + " current params - checked"
                                 + " in base dir = \"" + self.base_dir + "\"")
        elif verbose:
            logger.info("Data from " + str(self.n_files_found)
                  + " files compiled for comparison.")
