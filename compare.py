import getopt
from glob import glob
import os
import pickle
import random
import sys

import cv2
import imageio
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from collections import Counter
from skimage.color import rgb2lab
# from imutils import face_utils


base_dir = "."
search_output_path = "simple_image_compare_search_output.txt"
groups_output_path = "simple_image_compare_file_groups_output.txt"
run_search = False
overwrite = False
search_file_index = None
search_file_path = None
verbose = False
compare_faces = True
use_thumb = True
counter_limit = 10000
inclusion_pattern = None
color_diff_threshold = None


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


def get_valid_file(base_dir, input_filepath):
    if (not isinstance(input_filepath, str) or input_filepath is None
            or input_filepath == ""):
        return None
    elif os.path.exists(input_filepath):
        return input_filepath
    elif base_dir is not None and os.path.exists(base_dir + "/" + input_filepath):
        return base_dir + "/" + input_filepath
    else:
        return None


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


search_output_path = os.path.join(base_dir, search_output_path)
groups_output_path = os.path.join(base_dir, groups_output_path)


class IndexComparison:
    def __init__(self, index1, index2):
        self.index1 = index1
        self.index2 = index2
        self.sum = index1+index2
        self.product = index1*index2

    def __eq__(self, obj):
        return self.sum == obj.sum and self.product == obj.product

    def __hash__(self):
        return hash(str(self.index1)) * hash(str(self.index2))


def round_up(number, to):
    if number % to == 0:
        return number
    else:
        return number - (number % to) + to


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
    modified_image = cv2.resize(
        image, (thumb_dim, thumb_dim), interpolation=cv2.INTER_AREA)
    modified_image = modified_image.reshape(
        modified_image.shape[0]*modified_image.shape[1], 3)
    return rgb2lab(np.uint8(modified_image))


def get_image_colors(image, clf, show_chart=False):
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
    count_true = 1
    _count = 0

    for i in range(len(bool_list)):
        if _count == x_threshold and count_true > x_threshold:
            return 1
        if _count > x_threshold and count_true + 1 > x_threshold:
            return 1

    return 0


def is_any_x_true_consecutive(bool_list, x_threshold):
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


def is_invalid_file(file_path, counter, run_search, inclusion_pattern):
    if file_path is None:
        return True
    elif run_search and counter == 0:
        return False
    elif inclusion_pattern is not None:
        return inclusion_pattern not in file_path
    else:
        return False


def get_image_array(filepath):
    image = imageio.imread(filepath)
    image_shape = np.shape(image)
    if (len(image_shape) < 3 or image_shape[0] < 1 or image_shape[1] < 1
            or image_shape[2] < 1):
        raise ValueError
    if image_shape[2] > 3:
        image = image[:, :, 0:3]
    return image


class Compare:
    def __init__(self, base_dir, search_file_path, counter_limit, use_thumb,
                 compare_faces, color_diff_threshold, inclusion_pattern,
                 overwrite, verbose):
        self.base_dir = base_dir
        self.search_file_path = search_file_path
        self.is_run_search = search_file_path is not None
        self.counter_limit = counter_limit
        self.use_thumb = use_thumb
        self.compare_faces = compare_faces
        self.inclusion_pattern = inclusion_pattern
        self.overwrite = overwrite
        self.verbose = verbose
        self.file_faces_filepath = os.path.join(base_dir, "image_faces.pkl")
        if self.use_thumb:
            self.thumb_dim = 15
            self.n_colors = self.thumb_dim ** 2
            self.colors_below_threshold = int(self.n_colors / 2)
            self.color_diff_threshold = color_diff_threshold
            if self.color_diff_threshold is None:
                self.color_diff_threshold = 15
            self.file_colors_filepath = os.path.join(
                base_dir, "image_thumb_colors.pkl")
            self.modifier = self.thumb_dim
            self.color_getter = get_image_thumb_colors
            self.color_diff_alg = is_any_x_true_consecutive
        else:
            self.n_colors = 8
            self.colors_below_threshold = int(self.n_colors * 4 / 8)
            self.color_diff_threshold = color_diff_threshold
            if self.color_diff_threshold is None:
                self.color_diff_threshold = 15
            self.file_colors_filepath = os.path.join(
                base_dir, "image_top_colors.pkl")
            self.modifier = KMeans(n_clusters=self.n_colors)
            self.color_getter = get_image_colors
            self.color_diff_alg = is_any_x_true_weighted
        if self.compare_faces:
            self.set_face_cascade()
        self.file_colors = np.empty((0, self.n_colors, 3))
        self.file_faces = np.empty((0))

    def get_files(self):
        self.files_found = []
        self.files = []
        self.files.extend(glob(os.path.join(self.base_dir, "*.jpg")))
        self.files.extend(glob(os.path.join(self.base_dir, "*.jpeg")))
        self.files.extend(glob(os.path.join(self.base_dir, "*.png")))
        self.files.extend(glob(os.path.join(self.base_dir, "*.webp")))
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
        print(" run search: " + str(self.is_run_search))
        if self.is_run_search:
            print(" search_file_path: " + self.search_file_path)
        print(" comparison files base directory: " + self.base_dir)
        print(" compare faces: " + str(self.compare_faces))
        print(" use thumb: " + str(self.use_thumb))
        print(" max file process limit: " + str(self.counter_limit))
        print(" max files processable for base dir: "
              + str(self.max_files_processed))
        print(" file glob pattern: " + str(self.inclusion_pattern))
        print(" n colors: " + str(self.n_colors))
        print(" colors below threshold: " + str(self.colors_below_threshold))
        print(" color diff threshold: " + str(self.color_diff_threshold))
        print(" file colors filepath: " + str(self.file_colors_filepath))
        print(" modifier: " + str(self.modifier))
        print(" color getter: " + str(self.color_getter))
        print(" color diff alg: " + str(self.color_diff_alg))
        print(" overwrite image data: " + str(self.overwrite))
        print("|--------------------------------------------------------------------|\n\n")

    def set_face_cascade(self):
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
        self.faceCascade = cv2.CascadeClassifier(cascPath)

    def get_data(self):
        if self.overwrite or not os.path.exists(self.file_colors_filepath):
            if not os.path.exists(self.file_colors_filepath):
                print("Image data cache not found so creating new cache"
                      + " - this may take a while.")
            self.base_dirfile_colors_dict = {}
            self.file_faces_dict = {}
        else:
            file_colors_file = open(self.file_colors_filepath, "rb")
            file_faces_file = open(self.file_faces_filepath, "rb")
            self.file_colors_dict = pickle.load(file_colors_file)
            self.file_faces_dict = pickle.load(file_faces_file)
            file_colors_file.close()
            file_faces_file.close()

        # Gather image file data from directory

        if verbose:
            print("Gathering image data...")
        else:
            print("Gathering image data", end="", flush=True)

        counter = 0

        for f in self.files:
            if is_invalid_file(f, counter, self.run_search, inclusion_pattern):
                continue

            if counter > self.counter_limit:
                break
            counter += 1

            if f in self.file_colors_dict and f in self.file_faces_dict:
                colors = self.file_colors_dict[f]
                n_faces = self.file_faces_dict[f]
            else:
                try:
                    image = get_image_array(f)
                except OSError as e:
                    print(e)
                    continue
                except ValueError:
                    continue

                if f in self.file_colors_dict:
                    colors = self.file_colors_dict[f]
                else:
                    try:
                        colors = self.color_getter(image, self.modifier)
                    except ValueError as e:
                        if verbose:
                            print(e)
                            print(f)
                        continue
                    self.file_colors_dict[f] = colors
                if f in self.file_faces_dict:
                    n_faces = self.file_faces_dict[f]
                else:
                    n_faces = self.get_faces_count(f)
                    self.file_faces_dict[f] = n_faces
                self.has_new_file_data = True

            self.file_colors = np.append(self.file_colors, [colors], 0)
            self.file_faces = np.append(self.file_faces, [n_faces], 0)
            self.files_found.append(f)

            if counter % 200 == 0:
                percent_complete = counter / self.max_files_processed_even * 100
                if percent_complete % 10 == 0:
                    if verbose:
                        print(str(int(percent_complete)) + "% data gathered")
                    else:
                        print(".", end="", flush=True)

        # Save image file data

        if self.has_new_file_data:
            file_colors_file = open(self.file_colors_filepath, "wb")
            file_faces_file = open(self.file_faces_filepath, "wb")
            pickle.dump(self.file_colors_dict, file_colors_file)
            pickle.dump(self.file_faces_dict, file_faces_file)
            file_colors_file.close()
            file_faces_file.close()
            self.file_colors_dict = None
            self.file_faces_dict = None
            if self.verbose:
                print("Updated image data saved to: ")
                print(self.file_colors_filepath)
                print(self.file_faces_filepath)

        self.n_files_found = len(self.files_found)

        if self.n_files_found == 0 or (self.is_run_search and self.n_files_found < 1):
            raise AssertionError("No image data found for comparison with"
                                 + " current params - checked"
                                 + " in base dir = \"" + base_dir + "\"")
        elif self.verbose:
            print("Data from " + str(self.n_files_found)
                  + " files compiled for comparison.")

    def get_faces_count(self, filepath):
        n_faces = random.random() * 10000 + 6  # Set to a value unlikely to match
        try:
            gray = cv2.imread(filepath, 0)
            faces = self.faceCascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            n_faces = len(faces)
        except Exception as e:
            if verbose:
                print(e)
        return n_faces

    def compute_color_diff(self, base_array, compare_array, return_diff_scores=False):
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
        files_grouped = {}
        _files_found = list(self.files_found)

        if verbose:
            print("Identifying similar image files...")
        _files_found.pop(search_file_index)
        search_file_colors = self.file_colors[search_file_index]
        file_colors = np.delete(self.file_colors, search_file_index, 0)
        color_similars = self.compute_color_diff(
            file_colors, search_file_colors, True)
        if compare_faces:
            search_file_faces = self.file_faces[search_file_index]
            file_faces = np.delete(self.file_faces, search_file_index)
            face_comparisons = file_faces - search_file_faces
            face_similars = face_comparisons == 0
            similars = np.nonzero(color_similars[0] * face_similars)
        else:
            similars = np.nonzero(color_similars[0])
        for _index in similars[0]:
            files_grouped[_files_found[_index]] = color_similars[1][_index]

        if len(files_grouped) > 0:
            with open(search_output_path, "w") as textfile:
                header = "Possibly related images to \"" + search_file_path + "\":\n"
                textfile.write(header)
                print(header)
                for f in sorted(files_grouped, key=lambda f: files_grouped[f]):
                    diff_score = int(files_grouped[f])
                    if not f == search_file_path:
                        if diff_score < 50:
                            textfile.write("DUPLICATE: " + f)
                            print("DUPLICATE: " + f)
                        elif diff_score < 1000:
                            textfile.write("PROBABLE MATCH: " + f)
                            print("PROBABLE MATCH: " + f)
                        else:
                            similarity_score = str(round(1000/diff_score, 4))
                            textfile.write(f + " - similarity: "
                                           + similarity_score + "\n")
                            print(f + " - similarity: " + similarity_score)
            print("\nThis output data saved to file at " + search_output_path)
        else:
            print("No similar images to \"" + search_file_path
                  + "\" identified with current params.")
        return files_grouped

    def run_search(self, search_file_path):
        if (search_file_path is None or search_file_path == ""
                or search_file_path == base_dir):
            while search_file_path is None:
                search_file_path = input(
                    "\nEnter a new file path to search for similars "
                    + "(enter \"exit\" or press Ctrl-C to quit): \n\n  > ")
                if search_file_path is not None and search_file_path == "exit":
                    break
                search_file_path = get_valid_file(
                    self.base_dir, search_file_path)
                if search_file_path is None:
                    print("Invalid filepath provided.")
                else:
                    print("")

        # Gather new image data if it was not in the initial list

        if search_file_path not in self.files_found:
            print("Filepath not found in initial list - gathering new file data")
            try:
                image = get_image_array(search_file_path)
            except OSError as e:
                if self.verbose:
                    print(e)
                raise AssertionError(
                    "Encountered an error accessing the provided file path in the file system.")

            try:
                colors = self.color_getter(image, self.modifier)
            except ValueError as e:
                if self.verbose:
                    print(e)
                raise AssertionError(
                    "Encountered an error gathering colors from the file provided.")
            n_faces = self.get_faces_count(search_file_path)
            self.file_colors = np.append(self.file_colors, [colors], 0)
            self.file_faces = np.append(self.file_faces, [n_faces], 0)
            self.files_found.insert(0, search_file_path)

        files_grouped = self.find_similars_to_image(
            search_file_path, self.files_found.index(search_file_path))
        search_file_path = None
        return files_grouped

    def run_comparison(self):
        files_grouped = {}
        group_index = 0
        file_groups = {}
        n_files_found_even = round_up(self.n_files_found, 5)

        if self.n_files_found > 5000:
            print("\nWARNING: Large image file set found, comparison between all"
                  + " images may take a while.\n")
        if self.verbose:
            print("Identifying groups of similar image files...")
        else:
            print("Identifying groups of similar image files", end="", flush=True)

        for i in range(len(self.files_found)):
            if i == 0:  # At this roll index all files would be comparing to themselves
                continue
            percent_complete = (i / n_files_found_even) * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(str(int(percent_complete)) + "% compared")
                else:
                    print(".", end="", flush=True)

            compare_file_colors = np.roll(self.file_colors, i, 0)
            color_similars = self.compute_color_diff(
                self.file_colors, compare_file_colors, True)

            if self.compare_faces:
                compare_file_faces = np.roll(self.file_faces, i, 0)
                face_comparisons = self.file_faces - compare_file_faces
                face_similars = face_comparisons == 0
                similars = np.nonzero(color_similars[0] * face_similars)
            else:
                similars = np.nonzero(color_similars[0])

            for base_index in similars[0]:
                diff_index = ((base_index - i) % self.n_files_found)
                diff_score = color_similars[0][base_index]

                # comparison = IndexComparison(base_index, diff_index)
                # f comparison in comparisons:
                #     continue
                # comparisons[comparison] = 0

                f1_grouped = base_index in files_grouped
                f2_grouped = diff_index in files_grouped

                if not f1_grouped and not f2_grouped:
                    files_grouped[base_index] = (group_index, diff_score)
                    files_grouped[diff_index] = (group_index, diff_score)
                    group_index += 1
                    continue
                elif f1_grouped:
                    existing_group_index, previous_diff_score = files_grouped[base_index]
                    if previous_diff_score - 500 > diff_score:
                        files_grouped[base_index] = (group_index, diff_score)
                        files_grouped[diff_index] = (group_index, diff_score)
                        group_index += 1
                    else:
                        files_grouped[diff_index] = (
                            existing_group_index, diff_score)
                else:
                    existing_group_index, previous_diff_score = files_grouped[diff_index]
                    if previous_diff_score - 500 > diff_score:
                        files_grouped[base_index] = (group_index, diff_score)
                        files_grouped[diff_index] = (group_index, diff_score)
                        group_index += 1
                    else:
                        files_grouped[base_index] = (
                            existing_group_index, diff_score)

        for file_index in files_grouped:
            _file = self.files_found[file_index]
            group_index, diff_score = files_grouped[file_index]
            if group_index in file_groups:
                file_group = file_groups[group_index]
            else:
                file_group = {}
            file_group[_file] = diff_score
            file_groups[group_index] = file_group

        if not verbose:
            print("")
        group_counter = 0
        group_print_cutoff = 5
        to_print_etc = True

        if len(files_grouped) > 0:
            print("")

            # TODO calculate group similarities and mark duplicates separately in this case

            with open(groups_output_path, "w") as textfile:
                for group_index in sorted(file_groups,
                                          key=lambda group_index:
                                          len(file_groups[group_index])):
                    group = file_groups[group_index]
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
                        textfile.write(f)
                        textfile.write("\n")
                        if group_counter <= group_print_cutoff:
                            print(f)

            print("\nFound " + str(group_counter)
                  + " image groups with current parameters.")
            print("\nPrinted up to first " + str(group_print_cutoff)
                  + " groups identified. All group data saved to file at "
                  + groups_output_path)
        else:
            print("No similar images identified with current params.")
        return (files_grouped, file_groups)

    def run(self):
        if self.is_run_search:
            return self.run_search(self.search_file_path)
        else:
            return self.run_comparison()


if __name__ == "__main__":
    compare = Compare(base_dir, search_file_path, counter_limit, use_thumb,
                      compare_faces, color_diff_threshold, inclusion_pattern,
                      overwrite, verbose)
    compare.get_files()
    compare.get_data()
    compare.run()
