from collections import Counter
import getopt
import os
import pickle
import sys

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from skimage.color import rgb2lab
# from imutils import face_utils

from compare.base_compare import BaseCompare, gather_files, round_up, get_valid_file, is_invalid_file, safe_write
from compare.compare_args import CompareArgs
from compare.compare_result import CompareResult
from utils.config import config
from utils.constants import CompareMode
from utils.translations import I18N

_ = I18N._


def usage():
    print("  Option                 Function                                 Default")
    print("      --dir=dirpath      Set base directory                       .      ")
    print("      --counter=int      Set counter cutoff for processing files  10000  ")
    print("      --faces=bool       Set use strict face matching             True   ")
    print("  -h, --help             Print help                                      ")
    print("      --include=pattern  File inclusion pattern                          ")
    print("      --search=filepath  Search for similar files to file         None   ")
    print("      --use_thumb=bool   Set compare thumbs or color averages     True   ")
    print("  -o, --overwrite        Overwrite saved image data               False  ")
    print("      --threshold=int    Color diff threshold                     15     ")
    print("  -v                     Verbose                                         ")


def get_median_values(ndarray1d):
    medians = []
    for i in range(0, 3):
        if len(ndarray1d) == 0:
            return medians
        medians.append(np.median(ndarray1d))
        ndarray1d = np.take(ndarray1d, np.nonzero(ndarray1d != medians[i])[0])
    return medians


def RGB2HEX(color):
    return "#{:02x}{:02x}{:02x}".format(
        int(color[0]), int(color[1]), int(color[2]))


def get_image_thumb_colors(image, thumb_dim):
    '''
    Normalize and reduce the size of the image array, and return the colors in LAB
    '''
    modified_image = cv2.resize(
        image, (thumb_dim, thumb_dim), interpolation=cv2.INTER_AREA)
    modified_image = modified_image.reshape(
        modified_image.shape[0]*modified_image.shape[1], 3)
    return rgb2lab(np.uint8(modified_image))


def get_image_colors(image, clf, show_chart=False):
    '''
    Get the set of the most significant colors in the image array
    '''
    modified_image = cv2.resize(
        image, (300, 300), interpolation=cv2.INTER_AREA)
    modified_image = modified_image.reshape(
        modified_image.shape[0]*modified_image.shape[1], 3)
    labels = clf.fit_predict(modified_image)
    counts = Counter(labels)
    center_colors = clf.cluster_centers_
    ordered_colors = [center_colors[i] for i in counts.keys()]
    lab_colors = [rgb2lab(np.uint8(np.asarray(ordered_colors[i])))
                  for i in counts.keys()]
    if show_chart:
        hex_colors = [RGB2HEX(ordered_colors[i]) for i in counts.keys()]
        plt.figure(figsize=(8, 6))
        plt.pie(counts.values(), labels=hex_colors, colors=hex_colors)
    return lab_colors


# TODO improve this comparison alg for non-thumb case


def is_any_x_true_weighted(bool_list, x_threshold):
    '''
    Given a list of boolean values. return 1 (true) only if ... ?
    '''
    count_true = 1
    _count = 0

    for i in range(len(bool_list)):
        if _count == x_threshold and count_true > x_threshold:
            return 1
        if _count > x_threshold and count_true + 1 > x_threshold:
            return 1

    return 0


def is_any_x_true_consecutive(bool_list, x_threshold):
    '''
    Given a list of boolean values, return 1 (true) only if at least
    x_threshold of them are consecutively true.
    '''
    count_true = 1
    prior_bool = False
    consecutive_count_true = 1
    consecutive_runs_true = 0
    consecutive_threshold = 10
    consecutive_run_threshold = 10

    for _bool in bool_list:
        if _bool:
            count_true += 1
            if prior_bool:
                consecutive_count_true += 1
                if consecutive_count_true > consecutive_threshold:
                    consecutive_runs_true += 1
        prior_bool = _bool
        if (count_true > x_threshold
                and consecutive_runs_true > consecutive_run_threshold):
            return 1

    return 0


def get_image_array(filepath):
    '''
    If this is a GIF file, return the array from the first frame only.

    If the image is grayscale, raise a ValueError. If the image has more
    dimensions than standard RGB, reshape it to RGB.
    '''
    image = imageio.imread(filepath)
    image_shape = np.shape(image)
    if (len(image_shape) < 3 or image_shape[0] < 1 or image_shape[1] < 1
            or image_shape[2] < 1):
        raise ValueError
    if image_shape[2] > 3:
        image = image[:, :, 0:3]
    return image


class Compare(BaseCompare):
    COMPARE_MODE = CompareMode.COLOR_MATCHING
    SEARCH_OUTPUT_FILE = "simple_image_compare_search_output.txt"
    GROUPS_OUTPUT_FILE = "simple_image_compare_file_groups_output.txt"
    FACES_DATA = "image_faces.pkl"
    THUMB_COLORS_DATA = "image_thumb_colors.pkl"
    TOP_COLORS_DATA = "image_top_colors.pkl"
    THRESHHOLD_POTENTIAL_DUPLICATE = 50
    THRESHHOLD_GROUP_CUTOFF = 4500

    def __init__(self, args=CompareArgs(), use_thumb=True, gather_files_func=gather_files):
        super().__init__(args, gather_files)
        self.use_thumb = use_thumb
        self.compare_faces = self.args.compare_faces
        if self.use_thumb:
            self.thumb_dim = 15
            self.n_colors = self.thumb_dim ** 2
            self.colors_below_threshold = int(self.n_colors / 2)
            self.color_diff_threshold = self.args.threshold
            if self.color_diff_threshold is None:
                self.color_diff_threshold = 15
            self.modifier = self.thumb_dim
            self.color_getter = get_image_thumb_colors
            self.color_diff_alg = is_any_x_true_consecutive
        else:
            self.n_colors = 8
            self.colors_below_threshold = int(self.n_colors * 4 / 8)
            self.color_diff_threshold = self.args.threshold
            if self.color_diff_threshold is None:
                self.color_diff_threshold = 15
            self.modifier = KMeans(n_clusters=self.n_colors)
            self.color_getter = get_image_colors
            self.color_diff_alg = is_any_x_true_weighted
        self._file_colors = np.empty((0, self.n_colors, 3))
        self._file_faces = np.empty((0))
        self.settings_updated = False
        self._probable_duplicates = []

    def set_base_dir(self, base_dir):
        '''
        Set the base directory and prepare cache file references.
        '''
        self.base_dir = base_dir
        self.search_output_path = os.path.join(base_dir, Compare.SEARCH_OUTPUT_FILE)
        self.groups_output_path = os.path.join(base_dir, Compare.GROUPS_OUTPUT_FILE)
        self._file_faces_filepath = os.path.join(base_dir, Compare.FACES_DATA)
        if self.use_thumb:
            self._file_colors_filepath = os.path.join(base_dir, Compare.THUMB_COLORS_DATA)
        else:
            self._file_colors_filepath = os.path.join(base_dir, Compare.TOP_COLORS_DATA)

    def print_settings(self):
        print("\n\n|--------------------------------------------------------------------|")
        print(" CONFIGURATION SETTINGS:")
        print(f" run search: {self.is_run_search}")
        if self.is_run_search:
            print(f" search_file_path: {self.search_file_path}")
        print(f" comparison files base directory: {self.base_dir}")
        print(f" compare faces: {self.compare_faces}")
        print(f" use thumb: {self.use_thumb}")
        print(f" max file process limit: {self.args.counter_limit}")
        print(f" max files processable for base dir: {self.max_files_processed}")
        print(f" recursive: {self.args.recursive}")
        print(f" file glob pattern: {self.args.inclusion_pattern}")
        print(f" include gifs: {self.args.include_gifs}")
        print(f" n colors: {self.n_colors}")
        print(f" colors below threshold: {self.colors_below_threshold}")
        print(f" color diff threshold: {self.color_diff_threshold}")
        print(f" file colors filepath: {self._file_colors_filepath}")
        print(f" modifier: {self.modifier}")
        print(f" color getter: {self.color_getter}")
        print(f" color diff alg: {self.color_diff_alg}")
        print(f" overwrite image data: {self.args.overwrite}")
        print("|--------------------------------------------------------------------|\n\n")

    def get_data(self):
        '''
        For all the found files in the base directory, either load the cached
        image data or extract new data and add it to the cache.
        '''
        if self.args.overwrite or not os.path.exists(self._file_colors_filepath):
            if not os.path.exists(self._file_colors_filepath):
                print("Image data not found so creating new cache"
                      + " - this may take a while.")
            elif self.args.overwrite:
                print("Overwriting image data caches - this may take a while.")
            self._file_colors_dict = {}
            self._file_faces_dict = {}
        else:
            with open(self._file_colors_filepath, "rb") as f:
                self._file_colors_dict = pickle.load(f)
            if self.compare_faces:
                with open(self._file_faces_filepath, "rb") as f:
                    self._file_faces_dict = pickle.load(f)
            else:
                self._file_faces_dict = {}

        # Gather image file data from directory

        if self.verbose:
            print("Gathering image data...")
        else:
            print("Gathering image data", end="", flush=True)

        counter = 0

        for f in self.files:
            if is_invalid_file(f, counter, self.is_run_search, self.args.inclusion_pattern):
                continue

            if counter > self.args.counter_limit:
                break

            if f in self._file_colors_dict:
                colors = self._file_colors_dict[f]
                if self.compare_faces and f in self._file_faces_dict:
                    n_faces = self._file_faces_dict[f]
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
                if self.compare_faces:
                    if f in self._file_faces_dict:
                        n_faces = self._file_faces_dict[f]
                    else:
                        n_faces = self._get_faces_count(f)
                        self._file_faces_dict[f] = n_faces
                self.has_new_file_data = True

            counter += 1
            self._file_colors = np.append(self._file_colors, [colors], 0)
            if self.compare_faces:
                self._file_faces = np.append(self._file_faces, [n_faces], 0)
            self._files_found.append(f)

            percent_complete = counter / self.max_files_processed_even * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(str(int(percent_complete)) + "% data gathered")
                else:
                    print(".", end="", flush=True)
                if self.progress_listener:
                    self.progress_listener.update(_("Image data collection"), percent_complete)

        # Save image file data

        if self.has_new_file_data or self.args.overwrite:
            with open(self._file_colors_filepath, "wb") as store:
                pickle.dump(self._file_colors_dict, store)
            if self._faceCascade:
                with open(self._file_faces_filepath, "wb") as store:
                    pickle.dump(self._file_faces_dict, store)
            self._file_colors_dict = None
            self._file_faces_dict = None
            if self.verbose:
                if self.args.overwrite:
                    print("Overwrote any pre-existing image data at:")
                else:
                    print("Updated image data saved to: ")
                print(self._file_colors_filepath)
                if self.compare_faces:
                    print(self._file_faces_filepath)

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

        if self.compare_faces:
            search_file_faces = self._file_faces[search_file_index]
            file_faces = np.delete(self._file_faces, search_file_index)
            face_comparisons = file_faces - search_file_faces
            face_similars = face_comparisons == 0
            similars = np.nonzero(color_similars[0] * face_similars)
        else:
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
                        if diff_score < Compare.THRESHHOLD_POTENTIAL_DUPLICATE:
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
            n_faces = self._get_faces_count(search_file_path)
            self._file_colors = np.insert(self._file_colors, 0, [colors], 0)
            self._file_faces = np.insert(self._file_faces, 0, [n_faces], 0)
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
        overwrite = self.args.overwrite or not store_checkpoints
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
                    self.progress_listener.update(_("Image comparison"), percent_complete)

            compare_file_colors = np.roll(self._file_colors, i, 0)
            color_similars = self._compute_color_diff(
                self._file_colors, compare_file_colors, True)

            if self.compare_faces:
                compare_file_faces = np.roll(self._file_faces, i, 0)
                face_comparisons = self._file_faces - compare_file_faces
                face_similars = face_comparisons == 0
                similars = np.nonzero(color_similars[0] * face_similars)
            else:
                similars = np.nonzero(color_similars[0])

            for base_index in similars[0]:
                diff_index = ((base_index - i) % self._n_files_found)
                diff_score = color_similars[1][base_index]
                f1_grouped = base_index in compare_result.files_grouped
                f2_grouped = diff_index in compare_result.files_grouped

                if diff_score < Compare.THRESHHOLD_POTENTIAL_DUPLICATE:
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
                    if previous_diff_score - Compare.THRESHHOLD_GROUP_CUTOFF > diff_score:
#                        print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                        compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                        compare_result.group_index += 1
                    else:
                        compare_result.files_grouped[diff_index] = (
                            existing_group_index, diff_score)
                else:
                    existing_group_index, previous_diff_score = compare_result.files_grouped[diff_index]
                    if previous_diff_score - Compare.THRESHHOLD_GROUP_CUTOFF > diff_score:
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


if __name__ == "__main__":
    base_dir = "."
    search_output_path = "simple_image_compare_search_output.txt"
    groups_output_path = "simple_image_compare_file_groups_output.txt"
    run_search = False
    overwrite = False
    search_file_index = None
    search_file_path = None
    verbose = False
    compare_faces = True
    include_gifs = False
    use_thumb = True
    counter_limit = 10000
    inclusion_pattern = None
    color_diff_threshold = None
    search_output_path = os.path.join(base_dir, search_output_path)
    groups_output_path = os.path.join(base_dir, groups_output_path)

    try:
        opts, args = getopt.getopt(sys.argv[1:], "bcfist:hov", [
            "help",  "overwrite", "dir=", "counter=", "faces=", "include=",
            "search=", "use_thumb=", "threshold="])
    except getopt.GetoptError as err:
        print(err)
        usage()
        sys.exit(2)

    for o, a in opts:
        try:
            if o == "-v":
                verbose = True
            elif o in ("-h", "--help"):
                usage()
                sys.exit()
            elif o == "--counter":
                counter_limit = int(a)
            elif o == "--dir":
                base_dir = a
                if not os.path.exists(base_dir) or not os.path.isdir(base_dir):
                    assert False, "Invalid directory: " + base_dir
            elif o == "--gifs":
                include_gifs = True
            elif o == "--include":
                inclusion_pattern = a
            elif o == "--faces":
                compare_faces = a == "True" or a == "true" or a == "t"
            elif o in ("-o", "--overwrite"):
                overwrite = True
                confirm = input("Confirm overwriting image data (y/n): ")
                if confirm != "y" and confirm != "Y":
                    print("No change made.")
                    exit()
            elif o == "--search":
                search_file_path = get_valid_file(base_dir, a)
                run_search = True
                if search_file_path is None:
                    assert False, "Search file provided \"" + str(a) \
                        + "\" is invalid - please ensure \"dir\" is passed first" \
                        + " if not providing full file path."
            elif o == "--threshold":
                color_diff_threshold = int(a)
            elif o == "--use_thumb":
                use_thumb = a != "False" and a != "false" and a != "f"
            else:
                assert False, "unhandled option " + o
        except Exception as e:
            print(e)
            print("")
            usage()
            exit(1)

    compare = Compare(base_dir,
                      search_file_path=search_file_path,
                      counter_limit=counter_limit,
                      use_thumb=use_thumb,
                      compare_faces=compare_faces,
                      color_diff_threshold=color_diff_threshold,
                      inclusion_pattern=inclusion_pattern,
                      overwrite=overwrite, verbose=verbose,
                      include_gifs=include_gifs)
    compare.get_files()
    compare.get_data()
    compare.run()
