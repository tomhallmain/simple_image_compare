import os
import pickle

class CompareResult:
    RESULT_FILENAME = "simple_image_compare_result.pkl"

    def __init__(self, base_dir, files):
        self.base_dir = base_dir
        self._dir_files_hash = CompareResult.hash_dir_files(files)
        self.file_groups = {}
        self.files_grouped = {}
        self.group_index = 0
        self.is_complete = False
        self.i = 1 # start at 1 because index 0 is identity comparison roll index

    def store(self):
        save_path = CompareResult.cache_path(self.base_dir)
        with open(save_path, "wb") as f:
            pickle.dump(self, f)
            print(f"Stored compare result: {save_path}")

    def equals_hash(self, files):
        return self._dir_files_hash == CompareResult.hash_dir_files(files)

    @staticmethod
    def cache_path(base_dir):
        return os.path.join(base_dir, CompareResult.RESULT_FILENAME)

    @staticmethod
    def hash_dir_files(files):
        hash_list = []
        for f in files:
            hash_list.append(hash(f))

    @staticmethod
    def load(base_dir, files, overwrite=False):
        if overwrite:
            return CompareResult(base_dir, files)
        cache_path = CompareResult.cache_path(base_dir)
        if not os.path.exists(cache_path):
            print(f"No checkpoint found for {base_dir} - creating new compare result cache.")
            return CompareResult(base_dir, files)
        cached = None
        try:
            with open(cache_path, "rb") as f:
                cached = pickle.load(f)
        except Exception:
            print("Failed to load compare result from base dir " + base_dir)
            return CompareResult(base_dir, files)
        if not cached.equals_hash(files):
            raise ValueError(f"{cache_path} does not match {files}")
        print(f"Loaded compare result: {cache_path}")
        return cached

