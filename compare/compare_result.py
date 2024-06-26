import os
import pickle

class CompareResult:
    RESULT_FILENAME = "simple_image_compare_result.pkl"

    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.file_groups = {}
        self.files_grouped = {}

    def store(self):
        save_path = CompareResult.cache_path(self.base_dir)
        with open(save_path, "wb") as f:
            pickle.dump(self, f):
            print(f"Stored compare result: {save_path}")

    @staticmethod
    def cache_path(base_dir):
        return os.path.join(base_dir, CompareResult.RESULT_FILENAME)

    @staticmethod
    def load(self, base_dir):
        try:
            with open(CompareResult.cache_path(self.base_dir), "rb") as f:
                return pickle.load(f)
        except Exception:
            print("Failed to load compare result from base dir " + base_dir)
            return CompareResult(base_dir)

