import getopt
import os
import pickle
import sys

import numpy as np
# from imutils import face_utils

from compare.base_compare import BaseCompare, gather_files, round_up, safe_write, is_invalid_file, get_valid_file
from compare.compare_args import CompareArgs
from compare.compare_result import CompareResult
from compare.model import image_embeddings, text_embeddings, embedding_similarity
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
    print("  -o, --overwrite        Overwrite saved image data               False  ")
    print("      --threshold=float  Embedding similarity threshold           0.9    ")
    print("  -v                     Verbose                                         ")


class CompareEmbedding(BaseCompare):
    COMPARE_MODE = CompareMode.CLIP_EMBEDDING
    SEARCH_OUTPUT_FILE = "simple_image_compare_search_output.txt"
    GROUPS_OUTPUT_FILE = "simple_image_compare_file_groups_output.txt"
    FACES_DATA = "image_faces.pkl"
    EMBEDDINGS_DATA = "image_embeddings.pkl"
    TOP_COLORS_DATA = "image_top_colors.pkl"
    THRESHHOLD_POTENTIAL_DUPLICATE = config.threshold_potential_duplicate_embedding
    THRESHHOLD_PROBABLE_MATCH = 0.98
    THRESHHOLD_GROUP_CUTOFF = 4500  # TODO fix this for Embedding case
    TEXT_EMBEDDING_CACHE = {}

    def __init__(self, args=CompareArgs(), gather_files_func=gather_files):
        super().__init__(args, gather_files)
        self.embedding_similarity_threshold = self.args.threshold
        self._file_embeddings = np.empty((0, 512))
        self._file_faces = np.empty((0))
        self.settings_updated = False
        self.gather_files_func = gather_files_func
        self._probable_duplicates = []
        self.segregation_map = {}

    def set_base_dir(self, base_dir):
        '''
        Set the base directory and prepare cache file references.
        '''
        self.base_dir = base_dir
        self.search_output_path = os.path.join(base_dir, CompareEmbedding.SEARCH_OUTPUT_FILE)
        self.groups_output_path = os.path.join(base_dir, CompareEmbedding.GROUPS_OUTPUT_FILE)
        self._file_faces_filepath = os.path.join(base_dir, CompareEmbedding.FACES_DATA)
        self._file_embeddings_filepath = os.path.join(base_dir, CompareEmbedding.EMBEDDINGS_DATA)

    def print_settings(self):
        print("\n\n|--------------------------------------------------------------------|")
        print(" CONFIGURATION SETTINGS:")
        print(f" run search: {self.is_run_search}")
        if self.is_run_search:
            print(f" search_file_path: {self.search_file_path}")
        print(f" comparison files base directory: {self.base_dir}")
        print(f" compare faces: {self.compare_faces}")
        print(f" embedding similarity threshold: {self.embedding_similarity_threshold}")
        print(f" max file process limit: {self.args.counter_limit}")
        print(f" max files processable for base dir: {self.max_files_processed}")
        print(f" recursive: {self.args.recursive}")
        print(f" file glob pattern: {self.args.inclusion_pattern}")
        print(f" include gifs: {self.args.include_gifs}")
        print(f" file embeddings filepath: {self._file_embeddings_filepath}")
        print(f" overwrite image data: {self.args.overwrite}")
        print("|--------------------------------------------------------------------|\n\n")

    def get_data(self):
        '''
        For all the found files in the base directory, either load the cached
        image data or extract new data and add it to the cache.
        '''
        if self.args.overwrite or not os.path.exists(self._file_embeddings_filepath):
            if not os.path.exists(self._file_embeddings_filepath):
                print("Image data not found so creating new cache"
                      + " - this may take a while.")
            elif self.args.overwrite:
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
            if is_invalid_file(f, counter, self.is_run_search, self.args.inclusion_pattern):
                continue

            if counter > self.args.counter_limit:
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
            self._handle_progress(counter, self.max_files_processed_even)

        # Save image file data

        if self.has_new_file_data or self.args.overwrite:
            with open(self._file_embeddings_filepath, "wb") as store:
                pickle.dump(self._file_embeddings_dict, store)
            if self._faceCascade:
                with open(self._file_faces_filepath, "wb") as store:
                    pickle.dump(self._file_faces_dict, store)
            self._file_embeddings_dict = None
            self._file_faces_dict = None
            if self.verbose:
                if self.args.overwrite:
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
        print(f"Store checkpoints: {store_checkpoints}")
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
            self._handle_progress(i, n_files_found_even, gathering_data=False)

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
                f1_grouped = base_index in compare_result.files_grouped
                f2_grouped = diff_index in compare_result.files_grouped

                if diff_score > CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE:
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
                    if previous_diff_score - CompareEmbedding.THRESHHOLD_GROUP_CUTOFF > diff_score:
                        # print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                        compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                        compare_result.group_index += 1
                    else:
                        compare_result.files_grouped[diff_index] = (
                            existing_group_index, diff_score)
                else:
                    existing_group_index, previous_diff_score = compare_result.files_grouped[diff_index]
                    if previous_diff_score - CompareEmbedding.THRESHHOLD_GROUP_CUTOFF > diff_score:
                        # print(f"Previous: {previous_diff_score} , New: {diff_score}")
                        compare_result.files_grouped[base_index] = (compare_result.group_index, diff_score)
                        compare_result.files_grouped[diff_index] = (compare_result.group_index, diff_score)
                        compare_result.group_index += 1
                    else:
                        compare_result.files_grouped[base_index] = (existing_group_index, diff_score)

        for file_index in compare_result.files_grouped:
            _file = self._files_found[file_index]
            group_index, diff_score = compare_result.files_grouped[file_index]
            file_group = compare_result.file_groups[group_index] if group_index in compare_result.file_groups else {}
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

    def find_similars_to_image(self, search_path, search_file_index):
        '''
        Search the numpy array of all known image arrays for similar
        characteristics to the provide image.
        NOTE Legacy method to allow for compare_faces boolean to be respected.
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

        if config.search_only_return_closest:
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = embedding_similars[1][_index]
            # Sort results by increasing difference score
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))
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
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))

        if len(files_grouped) > 0:
            with open(self.search_output_path, "w") as textfile:
                header = f"Possibly related images to \"{search_path}\":\n"
                textfile.write(header)
                if self.verbose:
                    print(header)
                for f in files_grouped:
                    similarity = files_grouped[f]
                    if not f == search_path:
                        if similarity > CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE:
                            line = "DUPLICATE: " + f
                        elif similarity > CompareEmbedding.THRESHHOLD_PROBABLE_MATCH:
                            line = "PROBABLE MATCH: " + f
                        else:
                            line = f"{f} - similarity: {similarity}"
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
        NOTE Legacy method to allow for compare_faces boolean to be respected.
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

            self._file_embeddings = np.insert(self._file_embeddings, 0, [embedding], 0)
            if self.compare_faces:
                n_faces = self._get_faces_count(search_file_path)
                self._file_faces = np.insert(self._file_faces, 0, [n_faces], 0)
            self._files_found.insert(0, search_file_path)

        files_grouped = self.find_similars_to_image(
            search_file_path, self._files_found.index(search_file_path))
        search_file_path = None
        return files_grouped

    def run_search(self):
        if self.args.compare_faces:
            return self._run_search_on_path(self.search_file_path)
        else:
            return self.search_multimodal()

    def _compute_multiembedding_diff(self, positive_embeddings=[], negative_embeddings=[], threshold=0.0):
        files_grouped = {}
        normalization_factor = 1

        if config.search_only_return_closest:
            _files_found = list(self._files_found)
            embedding_similars = self._compute_embedding_diff(
                self._file_embeddings, positive_embeddings[0], True, threshold=threshold)
            similars = np.nonzero(embedding_similars[0])
            for _index in similars[0]:
                files_grouped[_files_found[_index]] = embedding_similars[1][_index]
            # Sort results by increasing difference score
            files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1]))
            return files_grouped

        '''
        Generate embedding_similars arrays for both positive and negative embedding
        sets. For the positives, multiply the similarities together. For the negatives
        successively divide the results from the positive multiplications. The end
        result should reflect a combined similarity in the appropriate direction for
        each set of requested text embeddings.
        '''

        combined_similars = None

        for p_emb in positive_embeddings:
            embedding_similars = self._compute_embedding_diff(
                self._file_embeddings, p_emb, True, threshold=threshold)
            min_similarity = min(embedding_similars[1])
            normalization_factor *= min_similarity
            normalized = embedding_similars[1] / min_similarity
            combined_similars = normalized if combined_similars is None else combined_similars * normalized

        for n_emb in negative_embeddings:
            embedding_similars = self._compute_embedding_diff(
                self._file_embeddings, n_emb, True, threshold=threshold)
            min_similarity = min(embedding_similars[1])
            normalization_factor /= min_similarity
            normalized = embedding_similars[1] / min_similarity
            combined_similars = 1/ normalized if combined_similars is None else combined_similars / normalized

        if combined_similars is None:
            raise Exception('No results found.')

        temp = {}
        count = 0
        for i in range(len(self._files_found)):
            temp[self._files_found[i]] = combined_similars[i]
        for file, similarity in dict(sorted(temp.items(), key=lambda item: item[1], reverse=True)).items():
            if count == config.max_search_results:
                break
            files_grouped[file] = similarity
            count += 1
        files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))
        return files_grouped, normalization_factor

    def find_similars_to_embeddings(self, positive_embeddings, negative_embeddings):
        '''
        Search the numpy array of all known image embeddings for similar
        characteristics to the provided images and texts.
        '''
        files_grouped = {}

        if self.verbose:
            print("Identifying similar image files...")

        if self.args.search_file_path is None and self.args.negative_search_file_path is None:
            # NOTE It is much less likely for text to match exactly
            adjusted_threshold = self.embedding_similarity_threshold / 3
        else:
            adjusted_threshold = self.embedding_similarity_threshold
        files_grouped, normalization_factor = self._compute_multiembedding_diff(positive_embeddings, negative_embeddings, adjusted_threshold)
        adjusted_threshold_duplicate = CompareEmbedding.THRESHHOLD_POTENTIAL_DUPLICATE / normalization_factor
        adjusted_threshold_match = CompareEmbedding.THRESHHOLD_PROBABLE_MATCH / normalization_factor

        if len(files_grouped) > 0:
            with open(self.search_output_path, "w") as textfile:
                header = f"Possibly related images to ("
                if self.args.search_file_path is not None:
                    header += f"search file {self.args.search_file_path}, "
                if self.args.search_text is not None:
                    header += f"search text \"{self.args.search_text}\", "
                if self.args.negative_search_file_path is not None:
                    header += f"negative search file {self.args.negative_search_file_path}, "
                if self.args.search_text_negative is not None:
                    header += f"negative search text \"{self.args.search_text_negative}\", "
                header = header[:-2] + "):\n"
                textfile.write(header)
                if self.verbose:
                    print(header)
                for f in files_grouped:
                    similarity = files_grouped[f]
                    # NOTE with text or negative-only searches it is probably impossible for duplicates to appear
                    if similarity > adjusted_threshold_duplicate:
                        line = "DUPLICATE: " + f
                    elif similarity > adjusted_threshold_match:
                        line = "PROBABLE MATCH: " + f
                    else:
                        line = f"{f} - similarity: {similarity}"
                    safe_write(textfile, line + "\n")
                    if self.verbose:
                        print(line)
            if self.verbose:
                print("\nThis output data saved to file at " + self.search_output_path)
        elif self.verbose:
            print("No related images identified with current params.")
        return {0: files_grouped}

    def search_multimodal(self):
        '''
        Search for provided search images and text.
        '''

        if config.text_embedding_search_presets_exclusive \
                and self.args.search_text in config.text_embedding_search_presets:
            return self.segregate_by_text_with_domain(self.args.search_text)

        files_grouped = {0: {}}
        positive_embeddings = []
        negative_embeddings = []

        if self.args.search_file_path is not None:
            self._tokenize_image(self.args.search_file_path, positive_embeddings)

        if self.args.negative_search_file_path is not None:
            self._tokenize_image(self.args.negative_search_file_path, negative_embeddings, "negative search image")

        if self.args.search_text is not None and self.args.search_text.strip() != "":
            for text in self.args.search_text.split(","):
                self._tokenize_text(text.strip(), positive_embeddings, "positive search text")

        if self.args.search_text_negative is not None and self.args.search_text_negative.strip() != "":
            for text in self.args.search_text_negative.split(","):
                self._tokenize_text(text.strip(), negative_embeddings, "negative search text")

        if len(positive_embeddings) == 0 and len(negative_embeddings) == 0:
            print(f"Failed to generate embeddings.\n"
                  f"search image = {self.args.search_file_path}\n"
                  f"negative search image = {self.args.negative_search_file_path}\n"
                  f"search text = {self.args.search_text}\n"
                  f"search text negative = {self.args.search_text_negative}")
            return files_grouped  # TODO better exception handling

        files_grouped = self.find_similars_to_embeddings(positive_embeddings, negative_embeddings)
        return files_grouped

    def segregate_by_text_with_domain(self, search_text, search_text_negative=None, threshold=0.0):
        #### TODO refactor this to work with negative search text
        '''
        Optionally we may want to find the matches that are most exclusive to the
        search text within the domain of the provided search presets.
        '''
        files_grouped = {}
        temp = {}
        embeddings = []
        search_text_index = config.text_embedding_search_presets.index(search_text)
        count = 0

        if len(self.segregation_map) == 0 or self.args.overwrite:  # TODO different boolean for this cache
            for preset in config.text_embedding_search_presets:
                self._tokenize_text(preset, embeddings)

            for f in self._files_found:
                self.segregation_map[f] = []

            for embedding in embeddings:
                embedding_similars = self._compute_embedding_diff(
                    self._file_embeddings, embedding, True, threshold=threshold)
                normalized = embedding_similars[1] / min(embedding_similars[1])
                for i in range(len(normalized)):
                    self.segregation_map[self._files_found[i]].append(normalized[i])

        for f, similarities in self.segregation_map.items():
            max_similarity_index = similarities.index(max(similarities))
            if search_text_index == max_similarity_index:
                temp[f] = similarities[max_similarity_index]

        # TODO need some type of way to massage the results so that the clusters formed by the texts with
        # strong signals don't cannibalize the results from the other search terms

        for file, similarity in dict(sorted(temp.items(), key=lambda item: item[1], reverse=True)).items():
            if count == config.max_search_results:
                break
            files_grouped[file] = similarity
            count += 1
        files_grouped = dict(sorted(files_grouped.items(), key=lambda item: item[1], reverse=True))

        return {0: files_grouped}

    def _tokenize_text(self, text, embeddings=[], descriptor="search text"):
        if text in CompareEmbedding.TEXT_EMBEDDING_CACHE:
            text_embedding = CompareEmbedding.TEXT_EMBEDDING_CACHE[text]
            if text_embedding is not None:
                embeddings.append(CompareEmbedding.TEXT_EMBEDDING_CACHE[text])
                return
        if self.verbose:
            print(f"Tokenizing {descriptor}: \"{text}\"")
        try:
            text_embedding = text_embeddings(text)
            embeddings.append(text_embedding)
            CompareEmbedding.TEXT_EMBEDDING_CACHE[text] = text_embedding
        except OSError as e:
            if self.verbose:
                print(f"{text} - {e}")
            raise AssertionError(
                f"Encountered an error generating token embedding for {descriptor}")

    def _tokenize_image(self, image_path, embeddings=[], descriptor="search image"):
        if self.verbose:
            print(f"Tokenizing {descriptor}: \"{image_path}\"")
        try:
            embedding = image_embeddings(image_path)
            embeddings.append(embedding)
        except OSError as e:
            if self.verbose:
                print(f"{image_path} - {e}")
            raise AssertionError(
                "Encountered an error accessing the provided file path in the file system.")

    def _sort_groups(self, file_groups):
        return sorted(file_groups,
                      key=lambda group_index: len(file_groups[group_index]))

    def get_probable_duplicates(self):
        return self._probable_duplicates

    def remove_from_groups(self, removed_files=[]):
        # TODO technically it would be better to refresh the file and data lists every time a compare is done
        # If not, will need to add a way to re-add the removed file data in case the remove action was undone
        remove_indexes = []
        for f in removed_files:
            if f in self._files_found:
                remove_indexes.append(self._files_found.index(f))
        remove_indexes.sort()

        if len(self._file_embeddings) > 0:
            self._file_embeddings = np.delete(self._file_embeddings, remove_indexes, axis=0)
        if len(self._file_faces) > 0:
            self._file_faces = np.delete(self._file_faces, remove_indexes, axis=0)

        for f in removed_files:
            if f in self._files_found:
                self._files_found.remove(f)

    def readd_files(self, filepaths=[]):
        readded_indexes = []
        for f in filepaths:
            if f not in self._files_found:
                readded_indexes.append(len(self._files_found))
                self._files_found.append(f)
                try:
                    embedding = image_embeddings(f)
                except OSError as e:
                    print(f"Error generating embedding from file {f}: {e}")
                    continue
                self.file_embeddings_dict[f] = embedding
                self._file_embeddings = np.append(self._file_embeddings, [embedding], 0)
                if self.compare_faces:
                    n_faces = self.get_faces_count(f)
                    self._file_faces_dict = n_faces
                    self._file_faces = np.append(self._file_faces, [n_faces], 0)
                if self.verbose:
                    print(f"Readded file to compare: {f}")

    @staticmethod
    def single_text_compare(image_path, texts_dict):
        print(f"Running text comparison for \"{image_path}\" - text = {texts_dict}")
        similarities = {}
        try:
            image_embedding = image_embeddings(image_path)
        except OSError as e:
            print(f"{image_path} - {e}")
            raise AssertionError(
                f"Encountered an error accessing the provided file path {image_embeddings} in the file system.")
        for key, text in texts_dict.items():
            if text in CompareEmbedding.TEXT_EMBEDDING_CACHE:
                text_embedding = CompareEmbedding.TEXT_EMBEDDING_CACHE[text]
            else:
                try:
                    text_embedding = text_embeddings(text)
                    CompareEmbedding.TEXT_EMBEDDING_CACHE[text] = text_embedding
                except OSError as e:
                    print(f"{text} - {e}")
                    raise AssertionError("Encountered an error accessing the provided file path in the file system.")
            similarities[key] = embedding_similarity(image_embedding, text_embedding)
        return similarities

    @staticmethod
    def is_related(image1, image2):
        try:
            emb1 = image_embeddings(image1)
            emb2 = image_embeddings(image2)
        except OSError as e:
            print(f"{search_file_path} - {e}")
            raise AssertionError(
                "Encountered an error accessing the provided file paths in the file system.")
        similarity = embedding_similarity(emb1, emb2)[0]
        return similarity > 0.8


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
