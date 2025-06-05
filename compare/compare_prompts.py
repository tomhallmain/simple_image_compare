import os

import numpy as np

from compare.base_compare_embedding import BaseCompareEmbedding, gather_files
from compare.compare_args import CompareArgs
from compare.compare_result import CompareResult
from compare.model import text_embeddings_siglip
from image.image_data_extractor import ImageDataExtractor
from utils.config import config
from utils.constants import CompareMode
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._


# TODO enable comparisons between images on the basis of positive and negative prompts, to allow for searching prompts by text

class ComparePrompts(BaseCompareEmbedding):
    COMPARE_MODE = CompareMode.PROMPTS
    SEARCH_OUTPUT_FILE = "simple_image_compare_search_output.txt"
    GROUPS_OUTPUT_FILE = "simple_image_compare_file_groups_output.txt"
    PROMPTS_DATA = "image_prompts.pkl"
    THRESHHOLD_POTENTIAL_DUPLICATE = 0.95  # High similarity threshold for prompts
    THRESHHOLD_PROBABLE_MATCH = 0.85
    THRESHHOLD_GROUP_CUTOFF = 0.75
    TEXT_EMBEDDING_CACHE = {}
    MULTI_EMBEDDING_CACHE = {}  # keys are tuples of the filename + any text embedding search combination, values are combined similarity

    def __init__(self, args=CompareArgs(), gather_files_func=gather_files):
        super().__init__(args, gather_files_func)
        self._file_embeddings = np.empty((0, 1024 if config.siglip_enable_large_model else 768))
        self._file_faces = np.empty((0))
        self.threshold_duplicate = ComparePrompts.THRESHHOLD_POTENTIAL_DUPLICATE
        self.threshold_probable_match = ComparePrompts.THRESHHOLD_PROBABLE_MATCH
        self.threshold_group_cutoff = ComparePrompts.THRESHHOLD_GROUP_CUTOFF
        self.text_embeddings_func = text_embeddings_siglip
        self.text_embedding_cache = ComparePrompts.TEXT_EMBEDDING_CACHE
        self.multi_embedding_cache = ComparePrompts.MULTI_EMBEDDING_CACHE
        self.image_data_extractor = ImageDataExtractor()
        self._probable_duplicates = []
        self.settings_updated = False

    def set_base_dir(self, base_dir):
        '''
        Set the base directory and prepare cache file references.
        '''
        self.base_dir = base_dir
        self.search_output_path = os.path.join(base_dir, ComparePrompts.SEARCH_OUTPUT_FILE)
        self.groups_output_path = os.path.join(base_dir, ComparePrompts.GROUPS_OUTPUT_FILE)
        self._file_colors_filepath = os.path.join(base_dir, ComparePrompts.PROMPTS_DATA)

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
            exts = config.image_types
            if self.args.include_gifs:
                exts.append(".gif")
            self.files = self.gather_files_func(base_dir=self.base_dir, exts=exts, recursive=self.args.recursive)
        else:
            raise Exception("No gather files function found.")
        self.files.sort()
        self.has_new_file_data = False
        self.max_files_processed = min(self.args.counter_limit, len(self.files))
        self.max_files_processed_even = Utils.round_up(self.max_files_processed, 200)

        if self.is_run_search:
            if self.search_file_path in self.files:
                self.files.remove(self.search_file_path)
            self.search_file_index = 0
            self.files.insert(self.search_file_index, self.search_file_path)

        if self.verbose:
            self.print_settings()

    def print_settings(self):
        print("\n\n|--------------------------------------------------------------------|")
        print(" CONFIGURATION SETTINGS:")
        print(f" run search: {self.is_run_search}")
        if self.is_run_search:
            print(f" search_file_path: {self.search_file_path}")
        print(f" comparison files base directory: {self.base_dir}")
        print(f" max file process limit: {self.args.counter_limit}")
        print(f" max files processable for base dir: {self.max_files_processed}")
        print(f" recursive: {self.args.recursive}")
        print(f" file glob pattern: {self.args.inclusion_pattern}")
        print(f" include gifs: {self.args.include_gifs}")
        print(f" file colors filepath: {self._file_colors_filepath}")
        print(f" overwrite image data: {self.args.overwrite}")
        print("|--------------------------------------------------------------------|\n\n")

    def _extract_prompt_from_image(self, image_path):
        """
        Extract prompt data from image metadata using ImageDataExtractor.
        Returns tuple of (positive_prompt, negative_prompt) or (None, None) if no prompts found.
        """
        try:
            positive, negative, _, _ = self.image_data_extractor.get_image_prompts_and_models(image_path)
            if positive != "(Unable to parse image prompt information for this file.)" and positive != "(No prompt found for this file.)":
                return positive, negative
            return None, None
        except Exception as e:
            if self.verbose:
                print(f"Error extracting prompt from {image_path}: {e}")
            return None, None

    def get_data(self):
        '''
        For all the found files in the base directory, either load the cached
        prompt data or extract new data and add it to the cache.
        '''
        self.compare_data.load_data(overwrite=self.args.overwrite)

        if self.verbose:
            print("Gathering prompt data...")
        else:
            print("Gathering prompt data", end="", flush=True)

        counter = 0

        for f in self.files:
            if Utils.is_invalid_file(f, counter, self.is_run_search, self.args.inclusion_pattern):
                continue

            if counter > self.args.counter_limit:
                break

            if f in self.compare_data.file_data_dict:
                prompts = self.compare_data.file_data_dict[f]
            else:
                positive_prompt, negative_prompt = self._extract_prompt_from_image(f)
                if positive_prompt is None and negative_prompt is None:
                    # Skip files only if both prompts are None
                    continue
                prompts = (positive_prompt, negative_prompt)
                self.compare_data.file_data_dict[f] = prompts
                self.compare_data.has_new_file_data = True

            counter += 1
            # Convert prompts to embeddings using text embedding model
            try:
                # Always generate embeddings for both positive and negative prompts
                positive_embedding = self.text_embeddings_func(prompts[0] if prompts[0] is not None else "")
                negative_embedding = self.text_embeddings_func(prompts[1] if prompts[1] is not None else "")
                # Always subtract negative from positive (weighted)
                prompt_embedding = positive_embedding - (0.5 * negative_embedding)
                
                self._file_embeddings = np.vstack((self._file_embeddings, [prompt_embedding]))
                self.compare_data.files_found.append(f)
                self._handle_progress(counter, self.max_files_processed_even)
            except Exception as e:
                if self.verbose:
                    print(f"Error generating embedding for prompt in {f}: {e}")
                continue

        # Save prompt data
        self.compare_data.save_data(self.args.overwrite, verbose=self.verbose)

    def _compute_embedding_diff(self, base_array, compare_array, return_scores=False):
        '''
        Compute similarity between prompt embeddings.
        '''
        similarities = np.dot(base_array, compare_array.T)
        if return_scores:
            return similarities > self.threshold_duplicate, similarities
        return similarities > self.threshold_duplicate

    def find_similars_to_image(self, search_path, search_file_index):
        '''
        Search for images with similar prompts to the provided image.
        '''
        files_grouped = {}
        _files_found = list(self.compare_data.files_found)

        if self.verbose:
            print("Identifying similar prompt files...")
        _files_found.pop(search_file_index)
        search_file_embedding = self._file_embeddings[search_file_index]
        file_embeddings = np.delete(self._file_embeddings, search_file_index, 0)
        embedding_similars = self._compute_embedding_diff(
            file_embeddings, search_file_embedding, True)

        similars = np.nonzero(embedding_similars[0])

        if config.search_only_return_closest:
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = embedding_similars[1][_index]
        else:
            temp = {}
            count = 0
            for i in range(len(_files_found)):
                temp[_files_found[i]] = embedding_similars[1][i]
            for file, similarity in dict(sorted(temp.items(), key=lambda item: item[1], reverse=True)).items():
                if count == config.max_search_results:
                    break
                files_grouped[file] = similarity
                count += 1

        # Sort results by decreasing similarity score
        self.compare_result.files_grouped = dict(
            sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))
        self.compare_result.finalize_search_result(
            self.search_file_path, verbose=self.verbose, is_embedding=True,
            threshold_duplicate=self.threshold_duplicate,
            threshold_related=self.threshold_probable_match)
        return {0: files_grouped}

    def _run_search_on_path(self, search_file_path):
        '''
        Prepare and begin a search for a provided image file path.
        '''
        if (search_file_path is None or search_file_path == ""
                or search_file_path == self.base_dir):
            while search_file_path is None:
                search_file_path = input(
                    "\nEnter a new file path to search for similars "
                    + "(enter \"exit\" or press Ctrl-C to quit): \n\n  > ")
                if search_file_path is not None and search_file_path == "exit":
                    break
                search_file_path = Utils.get_valid_file(self.base_dir, search_file_path)
                if search_file_path is None:
                    print("Invalid filepath provided.")
                else:
                    print("")

        # Gather new image data if it was not in the initial list

        if search_file_path not in self._files_found:
            if self.verbose:
                print("Filepath not found in initial list - gathering new file data")
            try:
                image = Utils.get_image_array(search_file_path)
            except OSError as e:
                if self.verbose:
                    print(f"{search_file_path} - {e}")
                raise AssertionError(
                    "Encountered an error accessing the provided file path in the file system.")

            try:
                colors = self.color_getter(image, self.modifier)
            except ValueError as e:
                if self.verbose:
                    print(e)
                raise AssertionError(
                    "Encountered an error gathering colors from the file provided.")
            self._file_colors = np.insert(self._file_colors, 0, [colors], 0)
            self._files_found.insert(0, search_file_path)

        files_grouped = self.find_similars_to_image(
            search_file_path, self._files_found.index(search_file_path))
        search_file_path = None
        return files_grouped

    def run_search(self):
        return self._run_search_on_path(self.search_file_path)

    def run_comparison(self, store_checkpoints=False):
        '''
        Compare all found prompt embeddings to each other.
        '''
        overwrite = self.args.overwrite or not store_checkpoints
        self.compare_result = CompareResult.load(
            self.base_dir, self.compare_data.files_found, overwrite=overwrite)
        if self.compare_result.is_complete:
            return (self.compare_result.files_grouped, self.compare_result.file_groups)

        n_files_found_even = Utils.round_up(self.compare_data.n_files_found, 5)
        if self.compare_result.i > 1:
            self._handle_progress(self.compare_result.i, n_files_found_even, gathering_data=False)

        if self.compare_data.n_files_found > 5000:
            print("\nWARNING: Large image file set found, comparison between all"
                  + " images may take a while.\n")
        if self.verbose:
            print("Identifying groups of similar prompt files...")
        else:
            print("Identifying groups of similar prompt files", end="", flush=True)

        for i in range(self.compare_data.n_files_found):
            if i == 0:  # Skip self-comparison
                continue
            if store_checkpoints:
                if i < self.compare_result.i:
                    continue
                if i % 250 == 0 and i != len(self.compare_data.files_found) and i > self.compare_result.i:
                    self.compare_result.store()
                self.compare_result.i = i
            self._handle_progress(i, n_files_found_even, gathering_data=False)

            compare_file_embeddings = np.roll(self._file_embeddings, i, 0)
            embedding_similars = self._compute_embedding_diff(
                self._file_embeddings, compare_file_embeddings, True)
            similars = np.nonzero(embedding_similars[0])

            for base_index in similars[0]:
                diff_index = ((base_index - i) % self.compare_data.n_files_found)
                similarity = embedding_similars[1][base_index]
                f1_grouped = base_index in self.compare_result.files_grouped
                f2_grouped = diff_index in self.compare_result.files_grouped

                if similarity > self.threshold_duplicate:
                    base_file = self.compare_data.files_found[base_index]
                    diff_file = self.compare_data.files_found[diff_index]
                    if ((base_file, diff_file) not in self._probable_duplicates
                            and (diff_file, base_file) not in self._probable_duplicates):
                        self._probable_duplicates.append((base_file, diff_file))

                if not f1_grouped and not f2_grouped:
                    self.compare_result.files_grouped[base_index] = (
                        self.compare_result.group_index, similarity)
                    self.compare_result.files_grouped[diff_index] = (
                        self.compare_result.group_index, similarity)
                    self.compare_result.group_index += 1
                elif f1_grouped:
                    existing_group_index, previous_similarity = self.compare_result.files_grouped[base_index]
                    if similarity - previous_similarity > self.threshold_group_cutoff:
                        self.compare_result.files_grouped[base_index] = (
                            self.compare_result.group_index, similarity)
                        self.compare_result.files_grouped[diff_index] = (
                            self.compare_result.group_index, similarity)
                        self.compare_result.group_index += 1
                    else:
                        self.compare_result.files_grouped[diff_index] = (
                            existing_group_index, similarity)
                else:
                    existing_group_index, previous_similarity = self.compare_result.files_grouped[diff_index]
                    if similarity - previous_similarity > self.threshold_group_cutoff:
                        self.compare_result.files_grouped[base_index] = (
                            self.compare_result.group_index, similarity)
                        self.compare_result.files_grouped[diff_index] = (
                            self.compare_result.group_index, similarity)
                        self.compare_result.group_index += 1
                    else:
                        self.compare_result.files_grouped[base_index] = (
                            existing_group_index, similarity)

        # Validate indices before accessing files_found
        return_current_results, should_restart = self._validate_checkpoint_data()
        if should_restart:
            return self.run_comparison(store_checkpoints=store_checkpoints)
        if return_current_results:
            return (self.compare_result.files_grouped, self.compare_result.file_groups)

        for file_index in self.compare_result.files_grouped:
            _file = self.compare_data.files_found[file_index]
            group_index, similarity = self.compare_result.files_grouped[file_index]
            if group_index in self.compare_result.file_groups:
                file_group = self.compare_result.file_groups[group_index]
            else:
                file_group = {}
            file_group[_file] = similarity
            self.compare_result.file_groups[group_index] = file_group

        self.compare_result.finalize_group_result()
        return (self.compare_result.files_grouped, self.compare_result.file_groups)

    def run(self, store_checkpoints=False):
        '''
        Runs the specified operation on this Compare.
        '''
        if self.is_run_search:
            return self.run_search()
        else:
            return self.run_comparison(store_checkpoints=store_checkpoints)

    def get_probable_duplicates(self):
        return self._probable_duplicates
    
    def remove_from_groups(self, removed_files=[]):
        # TODO technically it would be better to refresh the file and data lists every time a compare is done
        remove_indexes = []
        for f in removed_files:
            if f in self.compare_data.files_found:
                remove_indexes.append(self.compare_data.files_found.index(f))
        remove_indexes.sort()

        if len(self._file_embeddings) > 0:
            self._file_embeddings = np.delete(self._file_embeddings, remove_indexes, axis=0)

        for f in removed_files:
            if f in self.compare_data.files_found:
                self.compare_data.files_found.remove(f)

    @staticmethod
    def is_related(image1, image2):
        # TODO implement this method for this compare mode
        return False


