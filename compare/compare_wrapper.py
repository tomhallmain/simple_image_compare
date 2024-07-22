from copy import deepcopy
import os

from tkinter import messagebox

import pprint

from compare.compare import Compare, get_valid_file
from compare.compare_embeddings import CompareEmbedding
from utils.config import config
from utils.constants import Mode, CompareMode
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._

class CompareWrapper:
    def __init__(self, master, compare_mode, app_actions):
        self._master = master
        self._compare = None
        self.compare_mode = compare_mode
        self._app_actions = app_actions

        self.files_grouped = {}
        self.file_groups = {}
        self.files_matched = []
        self.search_image_full_path = None
        self.has_image_matches = False
        self.current_group = None
        self.current_group_index = 0
        self.match_index = 0
        self.group_indexes = []
        self.max_group_index = 0

    def has_compare(self):
        return self._compare is not None

    def compare(self):
        if self._compare is None:
            raise Exception("No compare object created")
        return self._compare

    def toggle_search_only_return_closest(self):
        config.search_only_return_closest = not config.search_only_return_closest

    def validate_compare_mode(self, required_compare_mode, error_text):
        if required_compare_mode != self.compare_mode:
            self._app_actions.alert(_("Invalid mode"), error_text, kind="warning")
            raise Exception(f"Invalid mode: {self.compare_mode}")

    def current_match(self):
        return self.files_matched[self.match_index]

    def actual_group_index(self):
        return self.group_indexes[self.current_group_index]

    def show_prev_image(self, show_alert=True):
        if self.files_matched is None:
            return False
        elif len(self.files_matched) == 0:
            if show_alert:
                self._app_actions.alert(_("Search required"), _("No matches found. Search again to find potential matches."))
            return False

        self._app_actions._set_toggled_view_matches()
        
        if self.match_index > 0:
            self.match_index -= 1
        else:
            self.match_index = len(self.files_matched) - 1
        
        self._master.update()
        self._app_actions.create_image(self.current_match())
        return True

    def show_next_image(self, show_alert=True):
        if self.files_matched is None:
            return False
        elif len(self.files_matched) == 0:
            if show_alert:
                self._app_actions.alert(_("Search required"), _("No matches found. Search again to find potential matches."))
            return False

        self._app_actions._set_toggled_view_matches()

        if len(self.files_matched) > self.match_index + 1:
            self.match_index += 1
        else:
            self.match_index = 0

        self._master.update()
        self._app_actions.create_image(self.current_match())
        return True


    def find_next_unrelated_image(self, file_browser, forward=True):
        found_unrelated_image = False
        previous_image = file_browser.current_file()
        original_image = str(previous_image)
        skip_count = 0
        if previous_image is None or len(previous_image) == 0:
            return
        while not found_unrelated_image:
            next_image = file_browser.next_file() if forward else file_browser.previous_file()
            if (self.compare_mode == CompareMode.COLOR_MATCHING and not Compare.is_related(previous_image, next_image)) or \
                    (self.compare_mode == CompareMode.CLIP_EMBEDDING and not CompareEmbedding.is_related(previous_image, next_image)):
                found_unrelated_image = True
                self._app_actions.create_image(next_image)
                self._app_actions.toast(_("Skipped %s images.").format(skip_count))
                return
            skip_count += 1
            previous_image = str(next_image)
            if original_image == previous_image:
                # Looped around and couldn't find an unrelated image
                self._app_actions.alert(_("No Unrelated Images"), _("No unrelated images found."))
                break

    def show_prev_group(self, event=None, file_browser=None) -> None:
        '''
        While in group mode, navigate to the previous group.
        '''
        if file_browser:
            self.find_next_unrelated_image(file_browser, forward=False)
            return
        if (self.file_groups is None or len(self.group_indexes) == 0
                or self.current_group_index == max(self.group_indexes)):
            self.current_group_index = 0
        else:
            self.current_group_index -= 1
        self.set_current_group()

    def show_next_group(self, event=None, file_browser=None) -> None:
        '''
        While in group mode, navigate to the next group.
        '''
        if file_browser:
            self.find_next_unrelated_image(file_browser, forward=True)
            return
        if (self.file_groups is None or len(self.group_indexes) == 0
                or self.current_group_index + 1 == len(self.group_indexes)):
            self.current_group_index = 0
        else:
            self.current_group_index += 1
        self.set_current_group()        

    def set_current_group(self, start_match_index=0) -> None:
        '''
        While in group mode, navigate between the groups.
        '''
        if self.file_groups is None or len(self.file_groups) == 0:
            self._app_actions.toast(_("No Groups Found"))
            return

        actual_group_index = self.actual_group_index()
        self.current_group = self.file_groups[actual_group_index]
        self.match_index = start_match_index
        self.files_matched = []

        for f in sorted(self.current_group, key=lambda f: self.current_group[f]):
            self.files_matched.append(f)

        self._app_actions._set_label_state(group_number=self.current_group_index, size=len(self.files_matched))
        self._master.update()
        self._app_actions.create_image(self.current_match())
    
    def page_down(self, half_length=False):
        paging_length = self._get_paging_length(half_length=half_length)
        test_cursor = self.match_index + paging_length
        if test_cursor >= len(self.files_matched):
            test_cursor = 0
        self.match_index = test_cursor
        return self.current_match()

    def page_up(self, half_length=False):
        paging_length = self._get_paging_length(half_length=half_length)
        test_cursor = self.match_index - paging_length
        if test_cursor < 0:
            test_cursor = -1
        self.match_index = test_cursor
        return self.current_match()

    def _get_paging_length(self, half_length=False):
        divisor = 20 if half_length else 10
        paging_length = int(len(self.files_matched) / divisor)
        if paging_length > 200:
            return 200
        if paging_length == 0:
            return 1
        return paging_length

    def select_series(self, start_file, end_file):
        if start_file not in self.files_matched:
            raise Exception('Start file not in list of matches')
        if end_file not in self.files_matched:
            raise Exception('End file not in list of matches')
        start_index = self.files_matched.index(start_file)
        end_index = self.files_matched.index(end_file)
        if start_index > end_index:
            selected = self.files_matched[end_index:start_index+1]
        else:
            selected = self.files_matched[start_index:end_index+1]
        return selected

    def _requires_new_compare(self, base_dir):
        if not self.has_compare() or self._compare.base_dir != base_dir:
            return True
        current_compare_class = self._compare.__class__.__name__
        if current_compare_class == "Compare":
            return self.compare_mode != CompareMode.COLOR_MATCHING
        elif current_compare_class == "CompareEmbedding":
            return self.compare_mode != CompareMode.CLIP_EMBEDDING
        raise Exception(f"Unknown Compare class {current_compare_class}")

    def _is_new_data_request_required(self, counter_limit, compare_threshold,
                                     inclusion_pattern, recursive, overwrite):
        assert self._compare is not None
        if self.compare_mode == CompareMode.COLOR_MATCHING:
            if self._compare.color_diff_threshold != compare_threshold:
                return True
        elif self._compare.embedding_similarity_threshold != compare_threshold:
            return True
        return (self._compare.counter_limit != counter_limit
                or self._compare.inclusion_pattern != inclusion_pattern
                or self._compare.recursive != recursive
                or (not self._compare.overwrite and overwrite))

    def run(self, base_dir, app_mode, recursive, searching_image, search_file_path, search_text, search_text_negative, find_duplicates,
            counter_limit, compare_threshold, compare_faces, inclusion_pattern, overwrite, listener, store_checkpoints=False):
        get_new_data = True
        self.current_group_index = 0
        self.current_group = None
        self.max_group_index = 0
        self.group_indexes = []
        self.files_matched = []
        self.match_index = 0
        self.search_image_full_path = search_file_path

        if self._requires_new_compare(base_dir):
            self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
                _("Gathering image data... setup may take a while depending on number of files involved."), 30))
            self.new_compare(
                base_dir, recursive, search_file_path, counter_limit, compare_threshold,
                compare_faces, inclusion_pattern, overwrite, listener)
        else:
            assert self._compare is not None
            get_new_data = self._is_new_data_request_required(counter_limit, compare_threshold,
                                                             inclusion_pattern, recursive, overwrite)
            self._compare.set_search_file_path(search_file_path)
            self._compare.counter_limit = counter_limit
            self._compare.compare_faces = compare_faces
            self._compare.inclusion_pattern = inclusion_pattern
            self._compare.overwrite = overwrite
            if self.compare_mode == CompareMode.COLOR_MATCHING:
                self._compare.color_diff_threshold = compare_threshold
            else:
                self._compare.embedding_similarity_threshold = compare_threshold
            self._compare.print_settings()
        
        if self._compare is None:
            raise Exception("No compare object created")

        if self._compare.is_run_search or search_text is not None:
            self._app_actions.set_mode(Mode.SEARCH, do_update=False)
            self._app_actions._set_toggled_view_matches()
        else:
            if app_mode == Mode.SEARCH:
                res = self._app_actions.alert(_("Confirm group run"),
                                 _("Search mode detected, please confirm switch to group mode before run. Group mode will take longer as all images in the base directory are compared."),
                                 kind="askokcancel")
                if res != messagebox.OK and res != True:
                    return
            self._app_actions.set_mode(Mode.GROUP, do_update=False)

        if get_new_data:
            self._app_actions.toast(_("Gathering image data for comparison"))
            self._compare.get_files()
            self._compare.get_data()

        if searching_image:
            if not self._compare.is_run_search:
                raise Exception("Search mode not enabled but searching_image was set to True")
            self.run_search()
        elif search_text is not None:
            self.run_search_text_embedding(search_text=search_text, search_text_negative=search_text_negative)
        else:
            self.run_group(find_duplicates=find_duplicates, store_checkpoints=store_checkpoints)

    def new_compare(self, base_dir, recursive, search_file_path, counter_limit, compare_threshold,
                    compare_faces, inclusion_pattern, overwrite, listener):
        if self.compare_mode == CompareMode.CLIP_EMBEDDING:
            self._compare = CompareEmbedding(
                base_dir,
                recursive=recursive,
                search_file_path=search_file_path,
                counter_limit=counter_limit,
                embedding_similarity_threshold=compare_threshold,
                compare_faces=compare_faces,
                inclusion_pattern=inclusion_pattern,
                overwrite=overwrite,
                verbose=True,
                progress_listener=listener
            )
        elif self.compare_mode == CompareMode.COLOR_MATCHING:
            self._compare = Compare(
                base_dir,
                recursive=recursive,
                search_file_path=search_file_path,
                counter_limit=counter_limit,
                use_thumb=True,
                compare_faces=compare_faces,
                color_diff_threshold=compare_threshold,
                inclusion_pattern=inclusion_pattern,
                overwrite=overwrite,
                verbose=True,
                progress_listener=listener
            )

    def run_search(self) -> None:
        assert self._compare is not None
        self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
            _("Running image comparison with search file..."), 30))
        self.files_grouped = self._compare.run_search()
        self.file_groups = deepcopy(self.files_grouped)

        if len(self.files_grouped[0]) == 0:
            self.has_image_matches = False
            self._app_actions._set_label_state(_("Set a directory and search file."))
            self._app_actions.alert(_("No Match Found"), _("None of the files match the search file with current settings."))
            return

        reverse = self.compare_mode == CompareMode.CLIP_EMBEDDING
        for f in sorted(self.files_grouped[0], key=lambda f: self.files_grouped[0][f], reverse=reverse):
            self.files_matched.append(f)

        self.group_indexes = [0]
        self.current_group_index = 0
        self.max_group_index = 0
        self.match_index = 0
        self.has_image_matches = True
        self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
            _("%s possibly related images found.").format(str(len(self.files_matched))), 30))

        self._app_actions._add_buttons_for_mode()
        self._app_actions.create_image(self.files_matched[self.match_index])

    def run_search_text_embedding(self, search_text, search_text_negative):
        assert self._compare is not None
        self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
            _("Running image comparison with search text..."), 30))
        self.files_grouped = self._compare.search_text(search_text, search_text_negative)
        self.file_groups = deepcopy(self.files_grouped)

        if len(self.file_groups[0]) == 0:
            self.has_image_matches = False
            self._app_actions._set_label_state(_("Set a directory and search file or search text."))
            self._app_actions.alert(_("No Match Found"), _("None of the files match the search text with current settings."))
            return False

        for f in sorted(self.file_groups[0], key=lambda f: self.file_groups[0][f], reverse=True):
            self.files_matched.append(f)

        self.group_indexes = [0]
        self.current_group_index = 0
        self.max_group_index = 0
        self.match_index = 0
        self.has_image_matches = True
        self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
            _("%s possibly related images found.").format(str(len(self.files_matched))), 30))
        self._app_actions._add_buttons_for_mode()
        self._app_actions.create_image(self.current_match())

    def run_group(self, find_duplicates=False, store_checkpoints=False) -> None:
        assert self._compare is not None
        self._app_actions._set_label_state(Utils._wrap_text_to_fit_length(
            _("Running image comparisons..."), 30))
        self.files_grouped, self.file_groups = self._compare.run(store_checkpoints=store_checkpoints)
        
        if len(self.files_grouped) == 0:
            self.has_image_matches = False
            self._app_actions._set_label_state(_("Set a directory and search file."))
            self._app_actions.alert(_("No Groups Found"), _("None of the files can be grouped with current settings."))
            return

        self.group_indexes = self._compare._sort_groups(self.file_groups)
        self.max_group_index = max(self.file_groups.keys())
        self._app_actions._add_buttons_for_mode()
        self.current_group_index = 0

        if find_duplicates:
            self.file_groups = {}
            self.group_indexes = []
            duplicates = self._compare.get_probable_duplicates()
            if len(duplicates) == 0:
                self.has_image_matches = False
                self._app_actions._set_label_state(_("Set a directory and search file."))
                self._app_actions.alert(_("No Duplicates Found"), _("None of the files appear to be duplicates based on the current settings."))
                return
            self._app_actions.set_mode(Mode.DUPLICATES, do_update=True)
            print("Probable duplicates:")
            pprint.pprint(duplicates, width=160)
            duplicate_group_count = 0
            for file1, file2 in duplicates:
                self.file_groups[duplicate_group_count] = {
                    file1: 0,
                    file2: 0
                }
                self.group_indexes.append(duplicate_group_count)
                duplicate_group_count += 1
            self.max_group_index = duplicate_group_count
            self.set_current_group()
        else:
            has_found_stranded_group_members = False

            while len(self.file_groups[self.actual_group_index()]) == 1:
                has_found_stranded_group_members = True
                self.current_group_index += 1

            self.set_current_group()
            if has_found_stranded_group_members:
                self._app_actions.alert(_("Stranded Group Members Found"), _("Some group members were left stranded by the grouping process."))

    def find_file_after_comparison(self, app_mode, search_text="", exact_match=False):
        if not search_text or search_text.strip() == "":
            return None, None
        file_group_map = self._get_file_group_map(app_mode)
        for file, group_indexes in file_group_map.items():
            if search_text == os.path.basename(file):
                return file, group_indexes
        if exact_match:
            return None, None
        search_text = search_text.lower()
        for file, group_indexes in file_group_map.items():
            if os.path.basename(file).lower().startswith(search_text):
                return file, group_indexes
        for file, group_indexes in file_group_map.items():
            if search_text in os.path.basename(file).lower():
                return file, group_indexes
        return None, None

    def _update_groups_for_removed_file(self, app_mode, group_index, match_index, set_group=True, show_next_image=False):
        '''
        After a file has been removed, delete the cached image path for it and
        remove the group if only one file remains in that group.

        NOTE: This would be more complex if there was not a guarantee groups are disjoint.
        '''
        if config.debug:
            print(f"Updating groups for removed file {match_index} in group {group_index}")
        actual_index = self.group_indexes[group_index]
        if set_group or group_index == self.current_group_index:
            files_matched = self.files_matched
            set_group = True
            if config.debug and app_mode != Mode.SEARCH:
                print("setting group")
        else:
            files_matched = []
            group = self.file_groups[actual_index]
            for f in self._get_sorted_file_matches(group, app_mode):                    
                files_matched.append(f)

        if len(files_matched) < 3:
            if app_mode not in (Mode.GROUP, Mode.DUPLICATES):
                return

            # remove this group as it will only have one file
            if app_mode != Mode.SEARCH:
                self.files_grouped = {
                    k: v for k, v in self.files_grouped.items() if v[0] != actual_index}
            del self.file_groups[actual_index]
            del self.group_indexes[group_index]
            if group_index < self.current_group_index:
                self.current_group_index -= 1

            if len(self.file_groups) == 0:
                self._app_actions.alert(_("No More Groups"),
                           _("There are no more image groups remaining for this directory and current filter settings."))
                self.current_group_index = 0
                self.files_grouped = {}
                self.file_groups = {}
                self.match_index = 0
                self.files_matched = []
                self.group_indexes = []
                self._app_actions.set_mode(Mode.BROWSE)
                self._app_actions._set_label_state(_("Set a directory to run comparison."))
                self._app_actions.show_next_image()
                return
            elif group_index == len(self.file_groups):
                self.current_group_index = 0

            if set_group:
                self.set_current_group()
        else:
            filepath = files_matched[match_index]
#            print(f"Filepath from update_groups: {filepath}")
            if app_mode != Mode.SEARCH:
                self.files_grouped = {
                    k: v for k, v in self.files_grouped.items() if v[0] != actual_index}
            del files_matched[match_index]
            del self.file_groups[actual_index][filepath]
 
            if set_group:
                if self.match_index == len(self.files_matched):
                    self.match_index = 0
                elif self.match_index > match_index:
                    self.match_index -= 1

                if show_next_image:
                    self._master.update()
                    self._app_actions.create_image(self.current_match())

    def _get_file_group_map(self, app_mode):
        if app_mode == Mode.BROWSE:
            raise Exception("Cannot get file group map in Browse mode")
        group_map = {}
        for group_count in range(len(self.group_indexes)):
            group_index = self.group_indexes[group_count]
            group = self.file_groups[group_index]
            group_file_count = 0
            for f in self._get_sorted_file_matches(group, app_mode):
                group_map[f] = (group_count, group_file_count)
                group_file_count += 1
        return group_map

    def _get_sorted_file_matches(self, group, app_mode):
        if app_mode == Mode.SEARCH and CompareMode.CLIP_EMBEDDING == self.compare_mode:
            return sorted(group, key=lambda f: group[f], reverse=True)
        else:
            return sorted(group, key=lambda f: group[f])


