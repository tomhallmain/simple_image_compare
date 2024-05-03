import getopt
from glob import glob
import os
import pickle
import random
import sys

import cv2
import numpy as np
# from imutils import face_utils

from config import config
from constants import CompareMode
from model import image_embeddings, text_embeddings, embedding_similarity


def usage():
    print("  Option                 Function                                 Default")
    print("      --dir=dirpath      Set base directory                       .      ")
    print("      --counter=int      Set counter cutoff for processing files  10000  ")
    print("      --faces=bool       Set use strict face matching             True   ")
    print("  -h, --help             Print help                                      ")
    print("      --include=pattern  File inclusion pattern                          ")
    print("      --search=filepath  Search for similar files to file         None   ")
    print("  -o, --overwrite        Overwrite saved image data               False  ")
    print("      --threshold=float  Embedding similarity threshold           0.9    ")
    print("  -v                     Verbose                                         ")


def gather_files(base_dir=".", recursive=True, exts=config.file_types):
    files = []
    recursive_str = "**/" if recursive else ""
    for ext in exts:
        pattern = os.path.join(base_dir, recursive_str + "*" + ext)
        files.extend(glob(pattern, recursive=recursive))
    return files


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


def round_up(number, to):
    if number % to == 0:
        return number
    else:
        return number - (number % to) + to


def is_invalid_file(file_path, counter, run_search, inclusion_pattern):
    if file_path is None:
        return True
    elif run_search and counter == 0:
        return False
    elif inclusion_pattern is not None:
        return inclusion_pattern not in file_path
    else:
        return False





class CompareEmbedding:
    COMPARE_MODE = CompareMode.CLIP_EMBEDDING
    SEARCH_OUTPUT_FILE = "simple_image_compare_search_output.txt"
    GROUPS_OUTPUT_FILE = "simple_image_compare_file_groups_output.txt"
    FACES_DATA = "image_faces.pkl"
    EMBEDDINGS_DATA = "image_embeddings.pkl"
    TOP_COLORS_DATA = "image_top_colors.pkl"
    THRESHHOLD_POTENTIAL_DUPLICATE = config.threshold_potential_duplicate_embedding
    THRESHHOLD_GROUP_CUTOFF = 4500 # TODO fix this for Embedding case
    SEARCH_RETURN_CLOSEST = False

    def __init__(self, base_dir=".", search_file_path=None, counter_limit=30000,
                 compare_faces=False, embedding_similarity_threshold=0.9,
                 inclusion_pattern=None, overwrite=False, verbose=False, gather_files_func=gather_files,
                 include_gifs=False, match_dims=False, progress_listener=None):
        self.files = []
        self.set_base_dir(base_dir)
        self.set_search_file_path(search_file_path)
        self.counter_limit = counter_limit
        self.compare_faces = compare_faces
        self.inclusion_pattern = inclusion_pattern
        self.include_gifs = include_gifs
        self.match_dims = match_dims
        self.overwrite = overwrite
        self.verbose = verbose
        self.progress_listener = progress_listener
        self._faceCascade = None
        if self.compare_faces:
            self._set_face_cascade()
        self.embedding_similarity_threshold = embedding_similarity_threshold
        self._file_embeddings = np.empty((0, 512))
        self._file_faces = np.empty((0))
        self.settings_updated = False
        self.gather_files_func = gather_files_func
        self._probable_duplicates = []

    def set_base_dir(self, base_dir):
        '''
        Set the base directory and prepare cache file references.
        '''
        self.base_dir = base_dir
        self.search_output_path = os.path.join(base_dir, CompareEmbedding.SEARCH_OUTPUT_FILE)
        self.groups_output_path = os.path.join(base_dir, CompareEmbedding.GROUPS_OUTPUT_FILE)
        self._file_faces_filepath = os.path.join(base_dir, CompareEmbedding.FACES_DATA)
        self._file_embeddings_filepath = os.path.join(base_dir, CompareEmbedding.EMBEDDINGS_DATA)

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
            if self.include_gifs:
                exts.append(".gif")
            self.files = self.gather_files_func(base_dir=self.base_dir, exts=exts)
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
        print(f" compare faces: {self.compare_faces}")
        print(f" embedding similarity threshold: {self.embedding_similarity_threshold}")
        print(f" max file process limit: {self.counter_limit}")
        print(f" max files processable for base dir: {self.max_files_processed}")
        print(f" file glob pattern: {self.inclusion_pattern}")
        print(f" include gifs: {self.include_gifs}")
        print(f" file embeddings filepath: {self._file_embeddings_filepath}")
        print(f" overwrite image data: {self.overwrite}")
        print("|--------------------------------------------------------------------|\n\n")

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

    def get_data(self):
        '''
        For all the found files in the base directory, either load the cached
        image data or extract new data and add it to the cache.
        '''
        if self.overwrite or not os.path.exists(self._file_embeddings_filepath):
            if not os.path.exists(self._file_embeddings_filepath):
                print("Image data not found so creating new cache"
                      + " - this may take a while.")
            elif self.overwrite:
                print("Overwriting image data caches - this may take a while.")
            self._file_embeddings_dict = {}
            self._file_faces_dict = {}
        else:
            with open(self._file_embeddings_filepath, "rb") as f:
                self._file_embeddings_dict = pickle.load(f)
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
            if is_invalid_file(f, counter, self.is_run_search, self.inclusion_pattern):
                continue

            if counter > self.counter_limit:
                break

            if f in self._file_embeddings_dict:
                embedding = self._file_embeddings_dict[f]
                if self.compare_faces and f in self._file_faces_dict:
                    n_faces = self._file_faces_dict[f]
            else:
                try:
                    embedding = image_embeddings(f)
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
                self._file_embeddings_dict[f] = embedding
                if self.compare_faces:
                    if f in self._file_faces_dict:
                        n_faces = self._file_faces_dict[f]
                    else:
                        n_faces = self._get_faces_count(f)
                        self._file_faces_dict[f] = n_faces
                self.has_new_file_data = True

            counter += 1
            self._file_embeddings = np.append(self._file_embeddings, [embedding], 0)
            if self.compare_faces:
                self._file_faces = np.append(self._file_faces, [n_faces], 0)
            self._files_found.append(f)

            percent_complete = counter / self.max_files_processed_even * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(f"{int(percent_complete)}% data gathered")
                else:
                    print(".", end="", flush=True)
                if self.progress_listener:
                    self.progress_listener.update("Image data collection", percent_complete)

        # Save image file data

        if self.has_new_file_data or self.overwrite:
            with open(self._file_embeddings_filepath, "wb") as store:
                pickle.dump(self._file_embeddings_dict, store)
            if self._faceCascade:
                with open(self._file_faces_filepath, "wb") as store:
                    pickle.dump(self._file_faces_dict, store)
            self._file_embeddings_dict = None
            self._file_faces_dict = None
            if self.verbose:
                if self.overwrite:
                    print("Overwrote any pre-existing image data at:")
                else:
                    print("Updated image data saved to: ")
                print(self._file_embeddings_filepath)
                if self.compare_faces:
                    print(self._file_faces_filepath)

        self._n_files_found = len(self._files_found)

        if self._n_files_found == 0:
            raise AssertionError("No image data found for comparison with"
                                 + " current params - checked"
                                 + " in base dir = \"" + self.base_dir + "\"")
        elif self.verbose:
            print(f"Data from {self._n_files_found} files compiled for comparison.")

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

    def _compute_embedding_diff(self, base_array, compare_array,
                            return_diff_scores=False, threshold=None):
        '''
        Perform an elementwise diff between two image color arrays using the
        selected color difference algorithm.
        '''
        vectorized = np.vectorize(embedding_similarity, signature="(m),(n)->()")
        simlarities = vectorized(base_array, compare_array)
        if threshold is None:
            similars = simlarities > self.embedding_similarity_threshold
        else:
            similars = simlarities > threshold
        if return_diff_scores:
            return similars, simlarities
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
        search_file_embedding = self._file_embeddings[search_file_index]
        file_embeddings = np.delete(self._file_embeddings, search_file_index, 0)
        embedding_similars = self._compute_embedding_diff(
            file_embeddings, search_file_embedding, True)

        if self.compare_faces:
            search_file_faces = self._file_faces[search_file_index]
            file_faces = np.delete(self._file_faces, search_file_index)
            face_comparisons = file_faces - search_file_faces
            face_similars = face_comparisons == 0
            similars = np.nonzero(embedding_similars[0] * face_similars)
        else:
            similars = np.nonzero(embedding_similars[0])

        if CompareEmbedding.SEARCH_RETURN_CLOSEST:
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = embedding_similars[1][_index]
            # Sort results by increasing difference score
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))
        else:
            temp = {}
            count = 0
            for i in range(len(self._files_found)):
                temp[self._files_found[i]] = embedding_similars[1][i]
            for file, similarity in dict(sorted(temp.items(), key=lambda item: item[1])):
                if count == config.max_search_results:
                    break
                files_grouped[file] = similarity
                count += 1
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))

        if len(files_grouped) > 0:
            with open(self.search_output_path, "w") as textfile:
                header = f"Possibly related images to \"{search_path}\":\n"
                textfile.write(header)
                if self.verbose:
                    print(header)
                for f in files_grouped:
                    similarity = int(files_grouped[f])
                    if not f == search_path:
                        if similarity > CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE:
                            line = "DUPLICATE: " + f
                        elif similarity > 0.98:
                            line = "PROBABLE MATCH: " + f
                        else:
                            line = f"{f} - similarity: {similarity}"
                        textfile.write(line + "\n")
                        if self.verbose:
                            print(line)
            if self.verbose:
                print("\nThis output data saved to file at "
                      + self.search_output_path)
        elif self.verbose:
            print("No similar images to \"" + self.search_file_path
                  + "\" identified with current params.")
        return files_grouped

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
                embedding = image_embeddings(search_file_path)
            except OSError as e:
                if self.verbose:
                    print(f"{search_file_path} - {e}")
                raise AssertionError(
                    "Encountered an error accessing the provided file path in the file system.")

            n_faces = self._get_faces_count(search_file_path)
            self._file_embeddings = np.insert(self._file_embeddings, 0, [embedding], 0)
            self._file_faces = np.insert(self._file_faces, 0, [n_faces], 0)
            self._files_found.insert(0, search_file_path)

        files_grouped = self.find_similars_to_image(
            search_file_path, self._files_found.index(search_file_path))
        search_file_path = None
        return files_grouped

    def run_search(self):
        return self._run_search_on_path(self.search_file_path)

    def run_comparison(self):
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
        files_grouped = {}
        group_index = 0
        file_groups = {}
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
            percent_complete = (i / n_files_found_even) * 100
            if percent_complete % 10 == 0:
                if self.verbose:
                    print(f"{int(percent_complete)}% compared")
                else:
                    print(".", end="", flush=True)
                if self.progress_listener:
                    self.progress_listener.update("Image comparison", percent_complete)

            compare_file_embeddings = np.roll(self._file_embeddings, i, 0)
            color_similars = self._compute_embedding_diff(
                self._file_embeddings, compare_file_embeddings, True)

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
                f1_grouped = base_index in files_grouped
                f2_grouped = diff_index in files_grouped

                if diff_score > CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE:
                    base_file = self._files_found[base_index]
                    diff_file = self._files_found[diff_index]
                    if ((base_file, diff_file) not in self._probable_duplicates
                            and (diff_file, base_file) not in self._probable_duplicates):
                        self._probable_duplicates.append((base_file, diff_file))

                if not f1_grouped and not f2_grouped:
                    files_grouped[base_index] = (group_index, diff_score)
                    files_grouped[diff_index] = (group_index, diff_score)
                    group_index += 1
                    continue
                elif f1_grouped:
                    existing_group_index, previous_diff_score = files_grouped[base_index]
                    if previous_diff_score - CompareEmbedding.THRESHHOLD_GROUP_CUTOFF > diff_score:
#                        print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        files_grouped[base_index] = (group_index, diff_score)
                        files_grouped[diff_index] = (group_index, diff_score)
                        group_index += 1
                    else:
                        files_grouped[diff_index] = (
                            existing_group_index, diff_score)
                else:
                    existing_group_index, previous_diff_score = files_grouped[diff_index]
                    if previous_diff_score - CompareEmbedding.THRESHHOLD_GROUP_CUTOFF > diff_score:
#                        print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        files_grouped[base_index] = (group_index, diff_score)
                        files_grouped[diff_index] = (group_index, diff_score)
                        group_index += 1
                    else:
                        files_grouped[base_index] = (existing_group_index, diff_score)

        for file_index in files_grouped:
            _file = self._files_found[file_index]
            group_index, diff_score = files_grouped[file_index]
            if group_index in file_groups:
                file_group = file_groups[group_index]
            else:
                file_group = {}
            file_group[_file] = diff_score
            file_groups[group_index] = file_group

        if not self.verbose:
            print("")
        group_counter = 0
        group_print_cutoff = 5
        to_print_etc = True

        if len(files_grouped) > 0:
            print("")

            # TODO calculate group similarities and mark duplicates separately in this case

            with open(self.groups_output_path, "w") as textfile:
                for group_index in self._sort_groups(file_groups):
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
                  + self.groups_output_path)
        else:
            print("No similar images identified with current params.")
        return (files_grouped, file_groups)

    def run(self):
        '''
        Runs the specified operation on this Compare.
        '''
        if self.is_run_search:
            return self.run_search()
        else:
            return self.run_comparison()

    def find_similars_to_text(self, search_text, text_embedding):
        '''
        Search the numpy array of all known image arrays for similar
        characteristics to the provide image.
        '''
        files_grouped = {}
        _files_found = list(self._files_found)

        if self.verbose:
            print("Identifying similar image files...")

        # It is much less likely for text to match exactly
        adjusted_threshold = self.embedding_similarity_threshold / 3
        embedding_similars = self._compute_embedding_diff(
            self._file_embeddings, text_embedding, True, threshold=adjusted_threshold)

        if CompareEmbedding.SEARCH_RETURN_CLOSEST:
            similars = np.nonzero(embedding_similars[0])
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = embedding_similars[1][_index]
            # Sort results by increasing difference score
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))
        else:
            temp = {}
            count = 0
            for i in range(len(self._files_found)):
                temp[self._files_found[i]] = embedding_similars[1][i]
            for file, similarity in dict(sorted(temp.items(), key=lambda item: item[1], reverse=True)).items():
                if count == config.max_search_results:
                    break
                files_grouped[file] = similarity
                count += 1
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))

        if len(files_grouped) > 0:
            with open(self.search_output_path, "w") as textfile:
                header = f"Possibly related images to \"{search_text}\":\n"
                textfile.write(header)
                if self.verbose:
                    print(header)
                for f in files_grouped:
                    similarity = files_grouped[f]
                    if similarity > CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE:
                        line = "DUPLICATE: " + f
                    elif similarity > 0.98:
                        line = "PROBABLE MATCH: " + f
                    else:
                        line = f"{f} - similarity: {similarity}"
                    textfile.write(line + "\n")
                    if self.verbose:
                        print(line)
            if self.verbose:
                print("\nThis output data saved to file at "
                      + self.search_output_path)
        elif self.verbose:
            print("No similar images to \"" + search_text
                  + "\" identified with current params.")
        return files_grouped

    def search_text(self, search_text):
        files_grouped = {}

        '''
        Prepare and begin a search for a provided image file path.
        '''

        if self.verbose:
            print(f"Tokenizing search text: \"{search_text}\"")

        try:
            text_embedding = text_embeddings(search_text)
        except OSError as e:
            if self.verbose:
                print(f"{search_text} - {e}")
            raise AssertionError(
                "Encountered an error generating token embedding for search text.")

        files_grouped = self.find_similars_to_text(search_text, text_embedding)
        return files_grouped

    def _sort_groups(self, file_groups):
        return sorted(file_groups,
                      key=lambda group_index: len(file_groups[group_index]))

    def get_probable_duplicates(self):
        return self._probable_duplicates

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
    embedding_similarity_threshold = None
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
                embedding_similarity_threshold = float(a)
            elif o == "--use_thumb":
                use_thumb = a != "False" and a != "false" and a != "f"
            else:
                assert False, "unhandled option " + o
        except Exception as e:
            print(e)
            print("")
            usage()
            exit(1)

    compare = CompareEmbedding(base_dir,
                               search_file_path=search_file_path,
                               counter_limit=counter_limit,
                               embedding_similarity_threshold=embedding_similarity_threshold,
                               compare_faces=compare_faces,
                               inclusion_pattern=inclusion_pattern,
                               overwrite=overwrite,
                               verbose=verbose,
                               include_gifs=include_gifs)
    compare.get_files()
    compare.get_data()
    compare.run()
