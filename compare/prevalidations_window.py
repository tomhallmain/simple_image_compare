from enum import Enum
import os

from tkinter import Toplevel, Frame, Label, OptionMenu, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL
import tkinter.font as fnt
from tkinter.ttk import Entry, Button

from compare.compare_embeddings import CompareEmbedding
from files.file_actions_window import FileActionsWindow
from image.image_classifier_manager import image_classifier_manager
from image.prevalidation_action import PrevalidationAction
from utils.app_style import AppStyle
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._



class Prevalidation:
    NO_POSITIVES_STR = _("(no positives set)")
    NO_NEGATIVES_STR = _("(no negatives set)")

    def __init__(self, name=_("New Prevalidation"), positives=[], negatives=[], threshold=0.23,
                 action=PrevalidationAction.NOTIFY, action_modifier="", run_on_folder=None, is_active=True,
                 image_classifier_name="", image_classifier_selected_category="N/A"):
        self.name = name
        self.positives = positives
        self.negatives = negatives
        self.threshold = threshold
        self.action = action if isinstance(action, Enum) else PrevalidationAction[action]
        self.action_modifier = action_modifier
        self.run_on_folder = run_on_folder
        self.is_active = is_active
        self.image_classifier_name = image_classifier_name
        self.image_classifier = None
        self.image_classifier_categories = ["N/A"]
        self.image_classifier_selected_category = image_classifier_selected_category
        self.set_image_classifier(image_classifier_name)

    def set_positives(self, text):
        self.positives = [x.strip() for x in Utils.split(text, ",") if len(x) > 0]

    def set_negatives(self, text):
        self.negatives = [x.strip() for x in Utils.split(text, ",") if len(x) > 0]

    def get_positives_str(self):
        if len(self.positives) > 0:
            out = ""
            for i in range(len(self.positives)):
                out += self.positives[i].replace(",", "\\,") + ", " if i < len(self.positives)-1 else self.positives[i]
            return out
        else:
            return Prevalidation.NO_POSITIVES_STR

    def set_image_classifier(self, classifier_name):
        self.image_classifier = image_classifier_manager.get_classifier(classifier_name)
        if self.image_classifier is not None:
            self.image_classifier_categories = ["N/A"]
            self.image_classifier_categories.extend(list(self.image_classifier.image_classifier_categories))

    def is_selected_category_unset(self):
        return self.image_classifier_selected_category == "N/A"

    def run_on_image_path(self, image_path, hide_callback, toast_callback):
        if self.image_classifier is not None:
            is_above_threshold = self.image_classifier.test_image_for_category(image_path, self.image_classifier_selected_category, self.threshold)
        else:
            is_above_threshold = CompareEmbedding.multi_text_compare(image_path, self.positives, self.negatives, self.threshold)
        if is_above_threshold:
            return self.run_action(image_path, hide_callback, toast_callback)
        else:
            return None

    def run_action(self, image_path, hide_callback, toast_callback):
        if self.action == PrevalidationAction.SKIP:
            toast_callback(self.name +  _(" detected") +  _(" - skipped"))
        elif self.action == PrevalidationAction.HIDE:
            hide_callback(image_path)
            toast_callback(self.name + _(" detected") + _(" - hidden"))
        elif self.action == PrevalidationAction.NOTIFY:
            toast_callback(self.name + _(" detected"))
        elif self.action == PrevalidationAction.MOVE or self.action == PrevalidationAction.COPY:
            if self.action_modifier is not None and len(self.action_modifier) > 0:
                if not os.path.exists(self.action_modifier):
                    raise Exception("Invalid move target directory for prevalidation " + self.name + ": " + self.action_modifier)
                if not os.path.normpath(os.path.dirname(image_path)) == os.path.normpath(self.action_modifier):
                    toast_callback(self.name + _(" detected") + "\n" + _("Moving file: ") + image_path)
                    try:
                        FileActionsWindow.add_file_action(
                            Utils.move_file if self.action == PrevalidationAction.MOVE else Utils.copy_file,
                            image_path, self.action_modifier
                        )
                    except Exception as e:
                        print(e)
            else:
                raise Exception("Target directory not defined on prevalidation "  + self.name)
        elif self.action == PrevalidationAction.DELETE:
            toast_callback(self.name + _(" detected") + "\n" + _("Deleting file: ") + image_path)
            try:
                os.remove(image_path)
                print("Deleted file at " + image_path)
            except Exception as e:
                print(e)
        return self.action

    def get_negatives_str(self):
        if len(self.negatives) > 0:
            out = ""
            for i in range(len(self.negatives)):
                out += self.negatives[i].replace(",", "\\,") + ", " if i < len(self.negatives)-1 else self.negatives[i]
            return out
        else:
            return Prevalidation.NO_NEGATIVES_STR

    def validate(self):
        if self.name is None or len(self.name) == 0:
            raise Exception('Prevalidation name is None or empty')
        if self.image_classifier is None:
            if (self.positives is None or len(self.positives) == 0) and \
                    (self.negatives is None and len(self.negatives) == 0):
                raise Exception("At least one of positive or negative texts must be set.")
        if self.image_classifier is not None and self.image_classifier_selected_category not in self.image_classifier_categories:
            raise Exception(f"The selected category \"{self.image_classifier_selected_category}\" was not found in the image classifier's category options")
        if self.is_move_action() and \
                not os.path.isdir(self.action_modifier):
            raise Exception('Action modifier must be a valid directory')
        if self.run_on_folder is not None and not os.path.isdir(self.run_on_folder):
            raise Exception('Run on folder must be a valid directory: ' + self.run_on_folder)

    def is_move_action(self):
        return self.action == PrevalidationAction.MOVE or self.action == PrevalidationAction.COPY

    def move_index(self, idx, direction_count=1):
        unit = 1 if direction_count > 0 else -1
        direction_count = abs(direction_count)
        replacement_idx = idx
        while direction_count > 0:
            replacement_idx += unit
            direction_count -= 1
            if replacement_idx >= len(PrevalidationsWindow.prevalidations):
                replacement_idx = 0
            elif replacement_idx < 0:
                replacement_idx = len(PrevalidationsWindow.prevalidations) - 1
        # if replacement_idx >= idx:
        #     replacement_idx -= 1
        move_item = PrevalidationsWindow.prevalidations[idx]
        del PrevalidationsWindow.prevalidations[idx]
        PrevalidationsWindow.prevalidations.insert(replacement_idx, move_item)

    def to_dict(self):
        return {
            "name": self.name,
            "positives": self.positives,
            "negatives": self.negatives,
            "threshold": self.threshold,
            "action": self.action.value,
            "action_modifier": self.action_modifier,
            "run_on_folder": self.run_on_folder,
            "is_active": self.is_active,
            "image_classifier_name": self.image_classifier_name,
            "image_classifier_selected_category": self.image_classifier_selected_category,
            }

    @staticmethod
    def from_dict(d):
        return Prevalidation(**d)

    def __str__(self) -> str:
        if self.image_classifier is not None:
            return self.name + _(" testing classifier {0} for {1}").format(self.image_classifier_name, self.image_classifier_selected_category)
        else:
            return self.name + _(" ({0} positives, {1} negatives)").format(len(self.positives), len(self.negatives))

class PrevalidationModifyWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, prevalidation, dimensions="600x600"):
        PrevalidationModifyWindow.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        PrevalidationModifyWindow.top_level.geometry(dimensions)
        self.master = PrevalidationModifyWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.prevalidation = prevalidation if prevalidation is not None else Prevalidation()
        PrevalidationModifyWindow.top_level.title(_("Modify Prevalidation") + f": {self.prevalidation.name}")

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)

        row = 0
        self._label_info = Label(self.frame)
        self.add_label(self._label_info, _("Prevalidation Name"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.new_prevalidation_name = StringVar(self.master, value=_("New Prevalidation") if prevalidation is None else prevalidation.name)
        self.new_prevalidation_name_entry = Entry(self.frame, textvariable=self.new_prevalidation_name, width=50, font=fnt.Font(size=config.font_size))
        self.new_prevalidation_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_positives = Label(self.frame)
        self.add_label(self.label_positives, _("Positives"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.positives_var = StringVar(self.master, value=self.prevalidation.get_positives_str())
        self.positives_entry = Entry(self.frame, textvariable=self.positives_var, width=50, font=fnt.Font(size=config.font_size))
        self.positives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_negatives = Label(self.frame)
        self.add_label(self.label_negatives, _("Negatives"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.negatives_var = StringVar(self.master, value=self.prevalidation.get_negatives_str())
        self.negatives_entry = Entry(self.frame, textvariable=self.negatives_var, width=50, font=fnt.Font(size=config.font_size))
        self.negatives_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.prevalidation.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_action = Label(self.frame)
        self.add_label(self.label_action, _("Action"), row=row, column=0)
        self.action_var = StringVar(self.master, value=self.prevalidation.action.name)
        action_options = [str(k) for k in PrevalidationAction.__members__]
        self.action_choice = OptionMenu(self.frame, self.action_var, self.prevalidation.action.name, *action_options, command=self.set_action)
        self.action_choice.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_action_modifier = Label(self.frame)
        self.add_label(self.label_action_modifier, _("Action Modifier"), row=row, column=0)
        self.action_modifier_var = StringVar(self.master, value=self.prevalidation.action_modifier)
        self.action_modifier_entry = Entry(self.frame, textvariable=self.action_modifier_var, width=50, font=fnt.Font(size=config.font_size))
        self.action_modifier_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_run_on_folder = Label(self.frame)
        self.add_label(self.label_run_on_folder, _("Run on Directory"), row=row, column=0)
        self.run_on_folder_var = StringVar(self.master, value=self.prevalidation.run_on_folder)
        self.run_on_folder_entry = Entry(self.frame, textvariable=self.run_on_folder_var, width=50, font=fnt.Font(size=config.font_size))
        self.run_on_folder_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_image_classifier_name = Label(self.frame)
        self.add_label(self.label_image_classifier_name, _("Image Classifier Name"), row=row, column=0)
        self.image_classifier_name_var = StringVar(self.master, value=self.prevalidation.image_classifier_name)
        name_options = [""]
        name_options.extend(image_classifier_manager.get_model_names())
        self.image_classifier_name_choice = OptionMenu(self.frame, self.image_classifier_name_var, self.prevalidation.image_classifier_name, *action_options, command=self.set_image_classifier)
        self.image_classifier_name_choice.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_selected_category = Label(self.frame)
        self.add_label(self.label_selected_category, _("Image Classifier Selected Category"), row=row, column=0)
        self.image_classifier_selected_category_var = StringVar(self.master, value=self.prevalidation.image_classifier_selected_category)
        self.image_classifier_selected_category_choice = OptionMenu(self.frame, self.image_classifier_selected_category_var, self.prevalidation.image_classifier_selected_category, *self.prevalidation.image_classifier_categories[:], command=self.set_image_classifier_selected_category)
        self.image_classifier_selected_category_choice.grid(row=row, column=1, sticky=W)

        row += 1
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Done"), self.finalize_prevalidation, row=row, column=0)

        self.master.update()

    def set_name(self):
        name = self.new_prevalidation_name.get().strip()
        self.prevalidation.name = name

    def set_positives(self):
        text = self.positives_entry.get().strip()
        if text != Prevalidation.NO_POSITIVES_STR:
            self.prevalidation.set_positives(text)

    def set_negatives(self):
        text = self.negatives_entry.get().strip()
        if text != Prevalidation.NO_NEGATIVES_STR:
            self.prevalidation.set_negatives(text)

    def set_threshold(self, event=None):
        self.prevalidation.threshold = float(self.threshold_slider.get()) / 100

    def set_action(self, event=None):
        self.prevalidation.action = PrevalidationAction[self.action_var.get()]

    def set_action_modifier(self):
        self.prevalidation.action_modifier = self.action_modifier_var.get()

    def set_run_on_folder(self):
        self.prevalidation.run_on_folder = self.run_on_folder_entry.get().strip() \
                if self.run_on_folder_entry.get().strip() != "" else None

    def set_image_classifier(self, event=None):
        self.prevalidation.set_image_classifier(self.image_classifier_name_var.get())
        set_category_value = self.prevalidation.image_classifier_categories[0] if self.prevalidation.is_selected_category_unset() else self.prevalidation.selected_category
        self.image_classifier_selected_category_var.set(set_category_value)
        self.master.update()

    def set_image_classifier_selected_category(self, event=None):
        self.prevalidation.image_classifier_selected_category = self.image_classifier_selected_category_var.get()

    def finalize_prevalidation(self, event=None):
        self.set_name()
        self.set_positives()
        self.set_negatives()
        self.set_threshold()
        self.set_action()
        self.set_action_modifier()
        self.set_run_on_folder()
        self.set_image_classifier()
        self.set_image_classifier_selected_category()
        self.prevalidation.validate()
        self.close_windows()
        self.refresh_callback(self.prevalidation)

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)



class PrevalidationsWindow():
    prevalidated_cache = {}
    directories_to_exclude = []
    top_level = None
    prevalidation_modify_window = None
    prevalidations = []

    MAX_PRESETS = 50

    MAX_HEIGHT = 900
    N_TAGS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def prevalidate(image_path, get_base_dir_func, hide_callback, toast_callback):
        base_dir = get_base_dir_func()
        if len(PrevalidationsWindow.directories_to_exclude) > 0:
            if base_dir in PrevalidationsWindow.directories_to_exclude:
                return None
        if image_path not in PrevalidationsWindow.prevalidated_cache:
            prevalidation_action = None
            for prevalidation in PrevalidationsWindow.prevalidations:
                if prevalidation.is_active:
                    if prevalidation.is_move_action() and prevalidation.action_modifier == base_dir:
                        continue
                    if prevalidation.run_on_folder is not None and base_dir != prevalidation.run_on_folder:
                        continue
                    prevalidation_action = prevalidation.run_on_image_path(image_path, hide_callback, toast_callback)
                    if prevalidation_action is not None:
                        break
            if prevalidation_action is None or prevalidation_action.is_cache_type():
                PrevalidationsWindow.prevalidated_cache[image_path] = prevalidation_action
        else:
            prevalidation_action = PrevalidationsWindow.prevalidated_cache[image_path]
        return prevalidation_action

    @staticmethod
    def set_prevalidations():
        for prevalidation_dict in list(app_info_cache.get_meta("recent_prevalidations", default_val=[])):
            prevalidation = Prevalidation.from_dict(prevalidation_dict)
            PrevalidationsWindow.prevalidations.append(prevalidation)
            if prevalidation.is_move_action():
                PrevalidationsWindow.directories_to_exclude.append(prevalidation.action_modifier)

    @staticmethod
    def store_prevalidations():
        prevalidation_dicts = []
        for prevalidation in PrevalidationsWindow.prevalidations:
            prevalidation_dicts.append(prevalidation.to_dict())
        app_info_cache.set_meta("recent_prevalidations", prevalidation_dicts)

    @staticmethod
    def get_prevalidation_by_name(name):
        for prevalidation in PrevalidationsWindow.prevalidations:
            if name == prevalidation.name:
                return prevalidation
        raise Exception(_("No prevalidation found with name: {0}. Set it on the Prevalidations Window.").format(name))

    @staticmethod
    def get_geometry(is_gui=True):
        width = 700
        height = 400
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        PrevalidationsWindow.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        PrevalidationsWindow.top_level.geometry(PrevalidationsWindow.get_geometry())
        PrevalidationsWindow.top_level.title(_("Prevalidations"))
        self.master = PrevalidationsWindow.top_level
        self.app_actions = app_actions
        self.filter_text = ""
        self.filtered_prevalidations = PrevalidationsWindow.prevalidations[:]
        self.label_list = []
        self.label_list2 = []
        self.is_active_var_list = []
        self.is_active_list = []
        self.set_prevalidation_btn_list = []
        self.modify_prevalidation_btn_list = []
        self.delete_prevalidation_btn_list = []
        self.move_down_btn_list = []

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.columnconfigure(3, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        self._label_info = Label(self.frame)
        self.add_label(self._label_info, _("Set Prevalidations"), row=0, wraplength=PrevalidationsWindow.COL_0_WIDTH)
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Add prevalidation"), self.open_prevalidation_modify_window, column=1)
        self.clear_recent_prevalidations_btn = None
        self.add_btn("clear_recent_prevalidations_btn", _("Clear prevalidations"), self.clear_recent_prevalidations, column=2)

        self.add_prevalidation_widgets()

        # self.master.bind("<Key>", self.filter_prevalidations)
        # self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

    def add_prevalidation_widgets(self):
        row = 0
        base_col = 0
        for i in range(len(self.filtered_prevalidations)):
            row = i+1
            prevalidation = self.filtered_prevalidations[i]
            label_name = Label(self.frame)
            self.label_list.append(label_name)
            self.add_label(label_name, str(prevalidation), row=row, column=base_col, wraplength=PrevalidationsWindow.COL_0_WIDTH)

            label_action = Label(self.frame)
            self.label_list2.append(label_action)
            self.add_label(label_action, prevalidation.action.name, row=row, column=base_col + 1)

            is_active_var = BooleanVar(value=prevalidation.is_active)
            def set_is_active_handler(prevalidation=prevalidation, var=is_active_var):
                prevalidation.is_active = var.get()
                print(f"Set {prevalidation} to active: {prevalidation.is_active}")
            is_active_box = Checkbutton(self.frame, variable=is_active_var, font=fnt.Font(size=config.font_size), command=set_is_active_handler)
            is_active_box.grid(row=row, column=base_col + 2, sticky=(W))
            self.is_active_list.append(is_active_box)
            self.is_active_var_list.append(is_active_var)

            activate_prevalidation_var = BooleanVar(value=prevalidation.is_active)
            self.activate_prevalidation_choice = Checkbutton(self.frame, variable=activate_prevalidation_var, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))
            set_prevalidation_btn = Button(self.frame, text=_("Set"))
            self.set_prevalidation_btn_list.append(set_prevalidation_btn)
            set_prevalidation_btn.grid(row=row, column=base_col+3)
            def set_prevalidation_handler(event, prevalidation=prevalidation, var=activate_prevalidation_var):
                prevalidation.is_active = var.get()
                print(f"Set {prevalidation} to active: {prevalidation.is_active}")
            set_prevalidation_btn.bind("<Button-1>", set_prevalidation_handler)

            modify_prevalidation_btn = Button(self.frame, text=_("Modify"))
            self.set_prevalidation_btn_list.append(modify_prevalidation_btn)
            modify_prevalidation_btn.grid(row=row, column=base_col+4)
            def modify_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.open_prevalidation_modify_window(event, prevalidation)
            modify_prevalidation_btn.bind("<Button-1>", modify_prevalidation_handler)

            delete_prevalidation_btn = Button(self.frame, text=_("Delete"))
            self.delete_prevalidation_btn_list.append(delete_prevalidation_btn)
            delete_prevalidation_btn.grid(row=row, column=base_col+5)
            def delete_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.delete_prevalidation(event, prevalidation)
            delete_prevalidation_btn.bind("<Button-1>", delete_prevalidation_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+6)
            def move_down_handler(event, self=self, prevalidation=prevalidation):
                prevalidation.move_index(i, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_prevalidation_modify_window(self, event=None, prevalidation=None):
        if PrevalidationsWindow.prevalidation_modify_window is not None:
            PrevalidationsWindow.prevalidation_modify_window.master.destroy()
        PrevalidationsWindow.prevalidation_modify_window = PrevalidationModifyWindow(
            self.master, self.app_actions, self.refresh_prevalidations, prevalidation)

    def refresh_prevalidations(self, prevalidation):
        if prevalidation in PrevalidationsWindow.prevalidations:
            PrevalidationsWindow.prevalidations.remove(prevalidation)
        PrevalidationsWindow.prevalidations.insert(0, prevalidation)
        self.filtered_prevalidations = PrevalidationsWindow.prevalidations[:]
        PrevalidationsWindow.prevalidated_cache.clear()
        # TODO only clear the actions that have been tested by the changed prevalidation.
        # Note that this includes the actions that have been tested by the prevalidations after the one changed
        # as well as any cached "None" values as this implies all prevalidations were tested for those images.
        # Perhaps better said, the actions that have not been tested by the prevalidation that was changed can be preserved.
        PrevalidationsWindow.directories_to_exclude.clear()
        for prevalidation in PrevalidationsWindow.prevalidations:
            if prevalidation.is_move_action():
                PrevalidationsWindow.directories_to_exclude.append(prevalidation.action_modifier)
        self.refresh()

    def delete_prevalidation(self, event=None, prevalidation=None):
        if prevalidation is not None and prevalidation in PrevalidationsWindow.prevalidations:
            PrevalidationsWindow.prevalidations.remove(prevalidation)
        self.refresh()

    def filter_prevalidations(self, event):
        """
        TODO

        Rebuild the filtered prevalidations list based on the filter string and update the UI.
        """
        modifier_key_pressed = (event.state & 0x1) != 0 or (event.state & 0x4) != 0 # Do not filter if modifier key is down
        if modifier_key_pressed:
            return
        if len(event.keysym) > 1:
            # If the key is up/down arrow key, roll the list up/down
            if event.keysym == "Down" or event.keysym == "Up":
                if event.keysym == "Down":
                    self.filtered_prevalidations = self.filtered_prevalidations[1:] + [self.filtered_prevalidations[0]]
                else:  # keysym == "Up"
                    self.filtered_prevalidations = [self.filtered_prevalidations[-1]] + self.filtered_prevalidations[:-1]
                self.clear_widget_lists()
                self.add_prevalidation_widgets()
                self.master.update()
            if event.keysym != "BackSpace":
                return
        if event.keysym == "BackSpace":
            if len(self.filter_text) > 0:
                self.filter_text = self.filter_text[:-1]
        elif event.char:
            self.filter_text += event.char
        else:
            return
        if self.filter_text.strip() == "":
            print("Filter unset")
            # Restore the list of target directories to the full list
            self.filtered_prevalidations.clear()
            self.filtered_prevalidations = PrevalidationsWindow.prevalidations[:]
        else:
            temp = []
            return # TODO
            for prevalidation in PrevalidationsWindow.prevalidations:
                if prevalidation not in temp:
                    if prevalidation and (f" {self.filter_text}" in prevalidation.lower() or f"_{self.filter_text}" in prevalidation.lower()):
                        temp.append(prevalidation)
            self.filtered_prevalidations = temp[:]

        self.refresh()


    def do_action(self, event=None):
        """
        The user has requested to set a prevalidation. Based on the context, figure out what to do.

        If no prevalidations exist, call handle_prevalidation() with prevalidation=None to set a new prevalidation.

        If prevalidations exist, call set_prevalidation() to set the first prevalidation.

        If control key pressed, ignore existing and add a new prevalidation.

        If alt key pressed, use the penultimate prevalidation.

        The idea is the user can filter the directories using keypresses, then press enter to
        do the action on the first filtered tag.
        """
#        shift_key_pressed = (event.state & 0x1) != 0
        control_key_pressed = (event.state & 0x4) != 0
        alt_key_pressed = (event.state & 0x20000) != 0
        if alt_key_pressed:
            penultimate_prevalidation = PrevalidationsWindow.get_history_prevalidation(start_index=1)
            if penultimate_prevalidation is not None and os.path.isdir(penultimate_prevalidation):
                self.set_prevalidation(prevalidation=penultimate_prevalidation)
        elif len(self.filtered_prevalidations) == 0 or control_key_pressed:
            self.open_prevalidation_modify_window()
        else:
            if len(self.filtered_prevalidations) == 1 or self.filter_text.strip() != "":
                prevalidation = self.filtered_prevalidations[0]
            else:
                prevalidation = PrevalidationsWindow.last_set_prevalidation
            self.set_prevalidation(prevalidation=prevalidation)

    def clear_recent_prevalidations(self, event=None):
        self.clear_widget_lists()
        PrevalidationsWindow.prevalidations.clear()
        self.filtered_prevalidations.clear()
        self.add_prevalidation_widgets()
        self.master.update()

    def clear_widget_lists(self):
        for label in self.label_list:
            label.destroy()
        for label in self.label_list2:
            label.destroy()
        for chkbtn in self.is_active_list:
            chkbtn.destroy()
        for btn in self.set_prevalidation_btn_list:
            btn.destroy()
        for btn in self.modify_prevalidation_btn_list:
            btn.destroy()
        for btn in self.delete_prevalidation_btn_list:
            btn.destroy()
        for btn in self.move_down_btn_list:
            btn.destroy()
        self.label_list = []
        self.label_list2 = []
        self.is_active_list = []
        self.set_prevalidation_btn_list = []
        self.modify_prevalidation_btn_list = []
        self.delete_prevalidation_btn_list = []
        self.move_down_btn_list = []

    def refresh(self, refresh_list=True):
        self.filtered_prevalidations = PrevalidationsWindow.prevalidations[:]
        self.clear_widget_lists()
        self.add_prevalidation_widgets()
        self.master.update()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)


