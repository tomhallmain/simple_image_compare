import os
import pickle

import numpy as np

from compare.compare import gather_files, get_valid_file, is_invalid_file, round_up
from compare.compare_result import CompareResult
from utils.config import config
from utils.constants import CompareMode


# TODO enable comparisons between images on the basis of positive and negative prompts, to allow for searching prompts by text

class ComparePrompts:
    COMPARE_MODE = CompareMode.PROMPTS
    SEARCH_OUTPUT_FILE = "simple_image_compare_search_output.txt"
    GROUPS_OUTPUT_FILE = "simple_image_compare_file_groups_output.txt"
    PROMPTS_DATA = "image_prompts.pkl"
    THRESHHOLD_POTENTIAL_DUPLICATE = 50
    THRESHHOLD_GROUP_CUTOFF = 4500

    def __init__(self, base_dir=".", recursive=True, search_file_path=None, counter_limit=30000,
                 inclusion_pattern=None, overwrite=False, verbose=False, gather_files_func=gather_files,
                 include_gifs=False, match_dims=False, progress_listener=None):
        self.files = []
        self.recursive = recursive
        self.set_base_dir(base_dir)
        self.set_search_file_path(search_file_path)
        self.counter_limit = counter_limit
        self.inclusion_pattern = inclusion_pattern
        self.include_gifs = include_gifs
        self.match_dims = match_dims
        self.overwrite = overwrite
        self.verbose = verbose
        self.progress_listener = progress_listener
        self._faceCascade = None
        self._file_prompts = np.empty((0, 1))
        self.settings_updated = False
        self.gather_files_func = gather_files_func
        self._probable_duplicates = []

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
            if self.include_gifs:
                exts.append(".gif")
            self.files = self.gather_files_func(base_dir=self.base_dir, exts=exts, recursive=self.recursive)
        else:
            raise Exception("No gather files function found.")
        self.files.sort()
        self.has_new_file_data = False
        self.max_files_processed = min(self.counter_limit, len(self.files))
        self.max_files_processed_even = round_up(self.max_files_processed, 200)

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
        print(f" max file process limit: {self.counter_limit}")
        print(f" max files processable for base dir: {self.max_files_processed}")
        print(f" recursive: {self.recursive}")
        print(f" file glob pattern: {self.inclusion_pattern}")
        print(f" include gifs: {self.include_gifs}")
        print(f" file colors filepath: {self._file_colors_filepath}")
        print(f" overwrite image data: {self.overwrite}")
        print("|--------------------------------------------------------------------|\n\n")

    def get_data(self):
        '''
        For all the found files in the base directory, either load the cached
        image data or extract new data and add it to the cache.
        '''
        if self.overwrite or not os.path.exists(self._file_colors_filepath):
            if not os.path.exists(self._file_colors_filepath):
                print("Image data not found so creating new cache"
                      + " - this may take a while.")
            elif self.overwrite:
                print("Overwriting image data caches - this may take a while.")
            self._file_colors_dict = {}
        else:
            with open(self._file_colors_filepath, "rb") as f:
                self._file_colors_dict = pickle.load(f)

        # Gather image file data from directory

        if self.verbose:
            print("Gathering image data...")
        else:
            print("Gathering image data", end="", flush=True)

        counter = 0

        for f in self.files:
            if is_invalid_file(f, counter, self.is_run_search, self.inclusion_pattern):
                continue

            if counter > self.counter_limit:
                break

            if f in self._file_colors_dict:
                colors = self._file_colors_dict[f]
            else:
                try:
                    image = get_image_array(f)
                except OSError as e:
                    print(f"{f} - {e}")
                    continue
                except ValueError:
                    continue
                except SyntaxError as e:
                    if self.verbose:
                        print(f"{f} - {e}")
                    # i.e. broken PNG file (bad header checksum in b'tEXt')
                    continue

                if f in self._file_colors_dict:
                    colors = self._file_colors_dict[f]
                else:
                    try:
                        colors = self.color_getter(image, self.modifier)
                    except ValueError as e:
                        if self.verbose:
                            print(e)
                            print(f)
                        continue
                    self._file_colors_dict[f] = colors
                self.has_new_file_data = True

            counter += 1
            self._file_colors = np.append(self._file_colors, [colors], 0)
            self._files_found.append(f)

            percent_complete = counter / self.max_files_processed_even * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(str(int(percent_complete)) + "% data gathered")
                else:
                    print(".", end="", flush=True)
                if self.progress_listener:
                    self.progress_listener.update("Image data collection", percent_complete)

        # Save image file data

        if self.has_new_file_data or self.overwrite:
            with open(self._file_colors_filepath, "wb") as store:
                pickle.dump(self._file_colors_dict, store)
            self._file_colors_dict = None
            if self.verbose:
                if self.overwrite:
                    print("Overwrote any pre-existing image data at:")
                else:
                    print("Updated image data saved to: ")
                print(self._file_colors_filepath)

        self._n_files_found = len(self._files_found)

        if self._n_files_found == 0:
            raise AssertionError("No image data found for comparison with"
                                 + " current params - checked"
                                 + " in base dir = \"" + self.base_dir + "\"")
        elif self.verbose:
            print("Data from " + str(self._n_files_found)
                  + " files compiled for comparison.")

    def _compute_color_diff(self, base_array, compare_array,
                            return_diff_scores=False):
        '''
        Perform an elementwise diff between two image color arrays using the
        selected color difference algorithm.
        '''
        lab_diff_squares = np.square(base_array - compare_array)
        deltaE_cie76s = np.sqrt(np.sum(lab_diff_squares, 2)).astype(int)
        similars = np.apply_along_axis(
            self.color_diff_alg, 1, deltaE_cie76s < self.color_diff_threshold,
            self.colors_below_threshold)
        if return_diff_scores:
            return similars, np.sum(deltaE_cie76s, axis=1)
        else:
            return similars

    def find_similars_to_image(self, search_path, search_file_index):
        '''
        Search the numpy array of all known image arrays for similar
        characteristics to the provide image.
        '''
        files_grouped = {}
        _files_found = list(self._files_found)

        if self.verbose:
            print("Identifying similar image files...")
        _files_found.pop(search_file_index)
        search_file_colors = self._file_colors[search_file_index]
        file_colors = np.delete(self._file_colors, search_file_index, 0)
        color_similars = self._compute_color_diff(
            file_colors, search_file_colors, True)
        similars = np.nonzero(color_similars[0])

        if config.search_only_return_closest:
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = color_similars[1][_index]
        else:
            temp = {}
            count = 0
            for i in range(len(_files_found)):
                temp[_files_found[i]] = color_similars[1][i]
            for file, difference in dict(sorted(temp.items(), key=lambda item: item[1])).items():
                if count == config.max_search_results:
                    break
                files_grouped[file] = difference
                count += 1
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))

        # Sort results by increasing difference score
        files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))

        if len(files_grouped) > 0:
            with open(self.search_output_path, "w") as textfile:
                header = f"Possibly related images to \"{search_path}\":\n"
                textfile.write(header)
                if self.verbose:
                    print(header)
                for f in files_grouped:
                    diff_score = int(files_grouped[f])
                    if not f == search_path:
                        if diff_score < ComparePrompts.THRESHHOLD_POTENTIAL_DUPLICATE:
                            line = "DUPLICATE: " + f
                        elif diff_score < 1000:
                            line = "PROBABLE MATCH: " + f
                        else:
                            similarity_score = str(round(1000/diff_score, 4))
                            line = f + " - similarity: " + similarity_score
                        safe_write(textfile, line + "\n")
                        if self.verbose:
                            print(line)
            if self.verbose:
                print("\nThis output data saved to file at "
                      + self.search_output_path)
        elif self.verbose:
            print("No similar images to \"" + self.search_file_path
                  + "\" identified with current params.")
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
                search_file_path = get_valid_file(self.base_dir, search_file_path)
                if search_file_path is None:
                    print("Invalid filepath provided.")
                else:
                    print("")

        # Gather new image data if it was not in the initial list

        if search_file_path not in self._files_found:
            if self.verbose:
                print("Filepath not found in initial list - gathering new file data")
            try:
                image = get_image_array(search_file_path)
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
        Compare all found image arrays to each other by starting with the
        base numpy array containing all image data and moving each array to
        the next index.

        For example, if there are three images [X, Y, Z], there are two steps:
            Step 1: [X, Y, Z] -> [Z, X, Y] (elementwise comparison)
            Step 2: [X, Y, Z] -> [Y, Z, X] (elementwise comparison)
            ^ At this point, all arrays have been compared.
        
        files_grouped - Keys are the file indexes, values are tuple of the group index and diff score.
        file_groups - Keys are the group indexes, values are dicts with keys as the file in the group, values the diff score
        '''
        overwrite = self.overwrite or not store_checkpoints
        compare_result = CompareResult.load(self.base_dir, self._files_found, overwrite=overwrite)
        if compare_result.is_complete:
            return (compare_result.files_grouped, compare_result.file_groups)
        n_files_found_even = round_up(self._n_files_found, 5)

        if self._n_files_found > 5000:
            print("\nWARNING: Large image file set found, comparison between all"
                  + " images may take a while.\n")
        if self.verbose:
            print("Identifying groups of similar image files...")
        else:
            print("Identifying groups of similar image files", end="", flush=True)

        for i in range(len(self._files_found)):
            if i == 0:  # At this roll index the data would compare to itself
                continue
            if store_checkpoints:
                if i < compare_result.i:
                    continue
                if i % 250 == 0 and i != len(self._files_found) and i > compare_result.i:
                    compare_result.store()
                compare_result.i = i
            percent_complete = (i / n_files_found_even) * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(f"{int(percent_complete)}% compared")
                else:
                    print(".", end="", flush=True)
                if self.progress_listener:
                    self.progress_listener.update("Image comparison", percent_complete)

            compare_file_colors = np.roll(self._file_colors, i, 0)
            color_similars = self._compute_color_diff(
                self._file_colors, compare_file_colors, True)
            similars = np.nonzero(color_similars[0])

            for base_index in similars[0]:
                diff_index = ((base_index - i) % self._n_files_found)
                diff_score = color_similars[1][base_index]
                f1_grouped = base_index in compare_result.files_grouped
                f2_grouped = diff_index in compare_result.files_grouped

                if diff_score < ComparePrompts.THRESHHOLD_POTENTIAL_DUPLICATE:
                    base_file = self._files_found[base_index]
                    diff_file = self._files_found[diff_index]
                    if ((base_file, diff_file) not in self._probable_duplicates
                            and (diff_file, base_file) not in self._probable_duplicates):
                        self._probable_duplicates.append((base_file, diff_file))

                if not f1_grouped and not f2_grouped:
                    compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                    compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                    compare_result.group_index += 1
                    continue
                elif f1_grouped:
                    existing_group_index, previous_diff_score = compare_result.files_grouped[base_index]
                    if previous_diff_score - ComparePrompts.THRESHHOLD_GROUP_CUTOFF > diff_score:
#                        print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                        compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                        compare_result.group_index += 1
                    else:
                        compare_result.files_grouped[diff_index] = (
                            existing_group_index, diff_score)
                else:
                    existing_group_index, previous_diff_score = compare_result.files_grouped[diff_index]
                    if previous_diff_score - ComparePrompts.THRESHHOLD_GROUP_CUTOFF > diff_score:
#                        print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                        compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                        compare_result.group_index += 1
                    else:
                        compare_result.files_grouped[base_index] = (existing_group_index, diff_score)

        for file_index in compare_result.files_grouped:
            _file = self._files_found[file_index]
            group_index, diff_score = compare_result.files_grouped[file_index]
            if group_index in compare_result.file_groups:
                file_group = compare_result.file_groups[group_index]
            else:
                file_group = {}
            file_group[_file] = diff_score
            compare_result.file_groups[group_index] = file_group

        if not self.verbose:
            print("")
        group_counter = 0
        group_print_cutoff = 5
        to_print_etc = True

        if len(compare_result.files_grouped) > 0:
            print("")

            # TODO calculate group similarities and mark duplicates separately in this case

            with open(self.groups_output_path, "w") as textfile:
                for group_index in self._sort_groups(compare_result.file_groups):
                    group = compare_result.file_groups[group_index]
                    if len(group) < 2:
                        continue
                        # Technically this means losing some possible associations.
                        # TODO handle stranded group members
                    group_counter += 1
                    textfile.write("Group " + str(group_counter) + "\n")
                    if group_counter <= group_print_cutoff:
                        print("Group " + str(group_counter))
                    elif to_print_etc:
                        print("(etc.)")
                        to_print_etc = False
                    for f in sorted(group, key=lambda f: group[f]):
                        safe_write(textfile, f + "\n")
                        if group_counter <= group_print_cutoff:
                            print(f)

            print("\nFound " + str(group_counter)
                  + " image groups with current parameters.")
            print("\nPrinted up to first " + str(group_print_cutoff)
                  + " groups identified. All group data saved to file at "
                  + self.groups_output_path)
            if store_checkpoints:
                compare_result.is_complete = True
                compare_result.store()
        else:
            print("No similar images identified with current params.")
        return (compare_result.files_grouped, compare_result.file_groups)

    def run(self, store_checkpoints=False):
        '''
        Runs the specified operation on this Compare.
        '''
        if self.is_run_search:
            return self.run_search()
        else:
            return self.run_comparison(store_checkpoints=store_checkpoints)

    def _sort_groups(self, file_groups):
        return sorted(file_groups,
                      key=lambda group_index: len(file_groups[group_index]))

    def get_probable_duplicates(self):
        return self._probable_duplicates
    
    def remove_from_groups(self, removed_files=[]):
        # TODO technically it would be better to refresh the file and data lists every time a compare is done
        remove_indexes = []
        for f in removed_files:
            if f in self._files_found:
                remove_indexes.append(self._files_found.index(f))
        remove_indexes.sort()

        if len(self._file_colors) > 0:
            self._file_colors = np.delete(self._file_colors, remove_indexes, axis=0)
        if len(self._file_faces) > 0:
            self._file_faces = np.delete(self._file_faces, remove_indexes, axis=0)

        for f in removed_files:
            if f in self._files_found:
                self._files_found.remove(f)

    @staticmethod
    def is_related(image1, image2):
        # TODO implement this method for this compare mode
        return False


