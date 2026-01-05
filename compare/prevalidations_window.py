from enum import Enum
import os
from typing import Optional

from tkinter import Frame, Label, Scale, Checkbutton, BooleanVar, StringVar, LEFT, W, HORIZONTAL, Scrollbar, Listbox, BOTH, RIGHT, TOP, E
import tkinter.font as fnt
from tkinter.ttk import Entry, Button, Combobox

from compare.compare_embeddings_clip import CompareEmbeddingClip
from files.file_actions_window import FileActionsWindow
from image.image_classifier_manager import image_classifier_manager
from image.image_data_extractor import image_data_extractor
from image.image_ops import ImageOps
from image.prevalidation_action import PrevalidationAction
from lib.multiselect_dropdown import MultiSelectDropdown
from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.constants import ActionType
from utils.logging_setup import get_logger
from utils.translations import I18N
from utils.utils import Utils

_ = I18N._
logger = get_logger("prevalidations_window")


class DirectoryProfile:
    """Represents a profile that groups multiple directories together."""
    
    def __init__(self, name="", directories=None):
        self.name = name  # Unique name to identify this profile
        self.directories = directories if directories is not None else []  # List of directory paths
    
    def to_dict(self):
        """Serialize to dictionary for caching."""
        return {
            "name": self.name,
            "directories": self.directories,
        }
    
    @staticmethod
    def from_dict(d):
        """Deserialize from dictionary."""
        return DirectoryProfile(
            name=d.get("name", ""),
            directories=d.get("directories", [])
        )


class PrevalidationLookahead:
    """Represents a lookahead check for a prevalidation."""
    
    def __init__(self, name="", name_or_text="", threshold=0.23, is_prevalidation_name=False):
        self.name = name  # Unique name to identify this lookahead
        self.name_or_text = name_or_text
        self.threshold = threshold
        self.is_prevalidation_name = is_prevalidation_name
        self.run_result = None  # Cached result for the current prevalidate call (None = not run yet, True = triggered, False = not triggered)

    def validate(self):
        if self.name is None or self.name.strip() == "":
            return False
        if self.name_or_text is None or self.name_or_text.strip() == "":
            return False
        if self.is_prevalidation_name:
            try:
                PrevalidationsWindow.get_prevalidation_by_name(self.name_or_text)
                return True
            except Exception:
                return False
        return True
    
    def to_dict(self):
        """Serialize to dictionary for caching."""
        return {
            "name": self.name,
            "name_or_text": self.name_or_text,
            "threshold": self.threshold,
            "is_prevalidation_name": self.is_prevalidation_name,
        }
    
    @staticmethod
    def from_dict(d):
        """Deserialize from dictionary."""
        name = d.get("name", "")
        name_or_text = d.get("name_or_text", "")
        threshold = d.get("threshold", 0.23)
        is_prevalidation_name = d.get("is_prevalidation_name", False)
        
        return PrevalidationLookahead(
            name=name,
            name_or_text=name_or_text,
            threshold=threshold,
            is_prevalidation_name=is_prevalidation_name
        )


class Prevalidation:
    NO_POSITIVES_STR = _("(no positives set)")
    NO_NEGATIVES_STR = _("(no negatives set)")

    def __init__(self, name=_("New Prevalidation"), positives=[], negatives=[], threshold=0.23,
                 action=PrevalidationAction.NOTIFY, action_modifier="", run_on_folder=None, is_active=True,
                 image_classifier_name="", image_classifier_selected_categories=[], 
                 use_embedding=True, use_image_classifier=False, use_prompts=False, use_blacklist=False,
                 lookahead_names=[], profile_name=None):
        self.name = name
        self.positives = positives
        self.negatives = negatives
        self.threshold = threshold
        self.action = action if isinstance(action, Enum) else PrevalidationAction[action]
        self.action_modifier = action_modifier
        self.profile_name = profile_name  # Name of DirectoryProfile to use (None = global)
        self.profile = None  # Cached DirectoryProfile instance (set after loading, or temporary for backward compatibility)
        self.is_active = is_active
        # Note: run_on_folder parameter is kept for backward compatibility in from_dict but not stored as instance variable
        self.image_classifier_name = image_classifier_name
        self.image_classifier = None
        self.image_classifier_categories = []
        self.image_classifier_selected_categories = image_classifier_selected_categories
        self.use_embedding = use_embedding
        self.use_image_classifier = use_image_classifier
        self.use_prompts = use_prompts
        self.use_blacklist = use_blacklist
        self.lookahead_names = lookahead_names if lookahead_names else []  # List of lookahead names (strings)

    def update_profile_instance(self, profile_name=None, directory_path=None):
        """
        Update the cached profile instance based on profile_name.
        
        Args:
            profile_name: Optional profile name to set. If provided, updates self.profile_name first,
                         then updates the cached profile instance. If None, uses existing self.profile_name.
            auto_create: If True and profile doesn't exist, create it (for backward compatibility).
            directory_path: Directory path to use when creating profile (required if auto_create=True).
        """
        if profile_name is not None:
            self.profile_name = profile_name
        
        if self.profile_name:
            # Check if profile exists
            self.profile = PrevalidationsWindow.get_profile_by_name(self.profile_name)
            
            if self.profile is None:
                if directory_path:
                    # Create DirectoryProfile for backward compatibility
                    if not os.path.isdir(directory_path):
                        logger.warning(f"Invalid directory in run_on_folder for prevalidation '{self.name}': {directory_path}. Skipping profile creation.")
                        self.profile = None
                        self.profile_name = None
                        return
                    
                    # Use the directory path as the name to ensure uniqueness
                    temp_profile = DirectoryProfile(name=self.profile_name, directories=[directory_path])
                    # Add to profiles list so it can be reused by other prevalidations
                    PrevalidationsWindow.profiles.append(temp_profile)
                    logger.info(f"Created temporary DirectoryProfile for backward compatibility: name='{self.profile_name}', prevalidation='{self.name}'")
                    self.profile = temp_profile
                else:
                    # Profile not found and not creating
                    logger.warning(f"Profile {self.profile_name} not found for prevalidation {self.name}")
                    self.profile = None
        else:
            self.profile = None

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
        self.image_classifier_name = classifier_name
        self.image_classifier = image_classifier_manager.get_classifier(classifier_name)
        self.image_classifier_categories = []
        if self.image_classifier is not None:
            self.image_classifier_categories.extend(list(self.image_classifier.model_categories))

    def _ensure_image_classifier_loaded(self, notify_callback):
        """Lazy load the image classifier if it hasn't been loaded yet."""
        if self.image_classifier is None and self.image_classifier_name:
            try:
                if notify_callback is not None:
                    notify_callback(_("Loading image classifier <{0}> ...").format(self.image_classifier_name))
                self.set_image_classifier(self.image_classifier_name)
            except Exception as e:
                logger.error(f"Error loading image classifier <{self.image_classifier_name}>!")

    def is_selected_category_unset(self):
        # TODO - this may be incorrect, would make more sense to be the opposite logic, need to check
        return len(self.image_classifier_selected_categories) > 0

    def _check_prompt_validation(self, image_path):
        """Check if image prompts match the positive or negative criteria."""
        try:
            positive_prompt, negative_prompt = image_data_extractor.extract_prompts_all_strategies(image_path)

            # Skip if no prompts found (None indicates failure to extract prompts)
            if positive_prompt is None:
                return False
            
            # Check positive prompts
            positive_match = True
            if self.positives:
                positive_match = any(pos.lower() in positive_prompt.lower() for pos in self.positives)
            
            # Check negative prompts
            negative_match = True
            if self.negatives:
                negative_match = any(neg.lower() in negative_prompt.lower() for neg in self.negatives)
            
            return positive_match or negative_match
            
        except Exception as e:
            logger.error(f"Error checking prompt validation for {image_path}: {e}")
            return False

    def _check_lookaheads(self, image_path):
        """Check if any lookahead prevalidations are triggered. Returns True if any lookahead passes."""
        if not self.lookahead_names:
            return False
        
        for lookahead_name in self.lookahead_names:
            # Look up the lookahead from the shared list
            lookahead = PrevalidationsWindow.get_lookahead_by_name(lookahead_name)
            if lookahead is None:
                continue
            
            # Check if this lookahead has already been evaluated in this prevalidate call
            if lookahead.run_result is not None:
                # Use cached result
                if lookahead.run_result:
                    logger.info(f"Lookahead {lookahead_name} triggered for prevalidation {self.name} (cached)")
                    return True
                continue
            
            name_or_text = lookahead.name_or_text
            threshold = lookahead.threshold
            
            # Check if it's a prevalidation name or custom text
            if lookahead.is_prevalidation_name:
                # It's a prevalidation name - get the referenced prevalidation
                try:
                    lookahead_prevalidation = PrevalidationsWindow.get_prevalidation_by_name(name_or_text)
                    # Use the lookahead prevalidation's positives/negatives
                    positives = lookahead_prevalidation.positives
                    negatives = lookahead_prevalidation.negatives
                    # Skip if the referenced prevalidation has no positives or negatives
                    if not positives and not negatives:
                        lookahead.run_result = False  # Cache the result
                        continue
                except Exception:
                    # Prevalidation not found, skip this lookahead
                    lookahead.run_result = False  # Cache the result
                    continue
            else:
                # It's custom text, treat as a positive
                positives = [name_or_text]
                negatives = []
            
            # Check if this lookahead passes
            result = CompareEmbeddingClip.multi_text_compare(image_path, positives, negatives, threshold)
            lookahead.run_result = result  # Cache the result
            
            if result:
                logger.info(f"Lookahead {lookahead_name} triggered for prevalidation {self.name}")
                return True
        
        return False

    def run_on_image_path(self, image_path, hide_callback, notify_callback, add_mark_callback=None) -> Optional[PrevalidationAction]:
        # Lazy load the image classifier if needed
        self._ensure_image_classifier_loaded(notify_callback)
        
        # Check lookaheads first - if any pass, skip this prevalidation
        if self._check_lookaheads(image_path):
            return None
        
        # Check each enabled validation type with short-circuit OR logic
        if self.use_embedding:
            if CompareEmbeddingClip.multi_text_compare(image_path, self.positives, self.negatives, self.threshold):
                return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
        
        if self.use_image_classifier:
            if self.image_classifier is not None:
                if self.image_classifier.test_image_for_categories(image_path, self.image_classifier_selected_categories):
                    return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
            else:
                logger.error(f"Image classifier {self.image_classifier_name} not found for prevalidation {self.name}")
        
        if self.use_prompts:
            if self._check_prompt_validation(image_path):
                return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
        
        # No validation type passed
        return None

    def run_action(self, image_path, hide_callback, notify_callback, add_mark_callback=None):
        base_message = self.name + _(" detected")
        if self.action == PrevalidationAction.SKIP:
            notify_callback("\n" + base_message + _(" - skipped"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == PrevalidationAction.HIDE:
            hide_callback(image_path)
            notify_callback("\n" + base_message + _(" - hidden"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == PrevalidationAction.NOTIFY:
            notify_callback("\n" + base_message, base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == PrevalidationAction.ADD_MARK:
            add_mark_callback(image_path)
            notify_callback("\n" + base_message + _(" - marked"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == PrevalidationAction.MOVE or self.action == PrevalidationAction.COPY:
            if self.action_modifier is not None and len(self.action_modifier) > 0:
                if not os.path.exists(self.action_modifier):
                    raise Exception("Invalid move target directory for prevalidation " + self.name + ": " + self.action_modifier)
                if os.path.normpath(os.path.dirname(image_path)) != os.path.normpath(self.action_modifier):
                    action_modifier_name = Utils.get_relative_dirpath(self.action_modifier, levels=2)
                    action_type = ActionType.MOVE_FILE if self.action == PrevalidationAction.MOVE else ActionType.COPY_FILE
                    specific_message = _("Moving file: ") + os.path.basename(image_path) + " -> " + action_modifier_name
                    notify_callback("\n" + specific_message, base_message=base_message,
                                    action_type=action_type, is_manual=False)
                    try:
                        FileActionsWindow.add_file_action(
                            Utils.move_file if self.action == PrevalidationAction.MOVE else Utils.copy_file,
                            image_path, self.action_modifier
                        )
                    except Exception as e:
                        if (self.action == PrevalidationAction.MOVE and
                            "File already exists:" in str(e) and
                            os.path.exists(image_path)):
                            target_path = os.path.join(self.action_modifier, os.path.basename(image_path))
                            if Utils.calculate_hash(image_path) == Utils.calculate_hash(target_path):
                                # The file already exists in target, so we need to remove it from the source
                                # NOTE: this is a hack to avoid an error that sometimes happens where a file gets stranded
                                # possibly due to the sd-runner application re-saving it after the move, but it could 
                                # technically happen for other more valid reasons. Ideally need to identify why this error
                                # occurs and fix it.
                                try:
                                    with Utils.file_operation_lock:
                                        os.remove(image_path)
                                        logger.info("Removed file from source: " + image_path)
                                except Exception as e:
                                    logger.error("Error removing file from source: " + image_path + ": " + str(e))
                            elif ImageOps.compare_image_content_without_exif(image_path, target_path):
                                # Hash comparison failed, but image content is identical
                                # (different EXIF data but same visual content)
                                logger.info(f"File hashes differ but image content matches: {image_path} <> {target_path}")
                                logger.info("Replacing target file with source file (source has more EXIF data)")
                                try:
                                    # Replace target with source file (source has more information)
                                    FileActionsWindow.add_file_action(
                                        Utils.move_file if self.action == PrevalidationAction.MOVE else Utils.copy_file,
                                        image_path, self.action_modifier, auto=True, overwrite_existing=True
                                    )
                                    logger.info("Replaced target file with source: " + image_path)
                                except Exception as e:
                                    logger.error("Error replacing target file with source: " + image_path + ": " + str(e))
                            else:
                                logger.error(e)
                        else:
                            logger.error(e)
            else:
                raise Exception("Target directory not defined on prevalidation "  + self.name)
        elif self.action == PrevalidationAction.DELETE:
            notify_callback("\n" + _("Deleting file: ") + os.path.basename(image_path), base_message=base_message,
                            action_type=ActionType.REMOVE_FILE, is_manual=False)
            try:
                with Utils.file_operation_lock:
                    os.remove(image_path)
                    logger.info("Deleted file at " + image_path)
            except Exception as e:
                logger.error("Error deleting file at " + image_path + ": " + str(e))
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
        
        # Check if at least one validation type is enabled
        if not (self.use_embedding or self.use_image_classifier or self.use_prompts or self.use_blacklist):
            raise Exception("At least one validation type (embedding, image classifier, prompts, or prompts blacklist) must be enabled.")
        
        # Check if positives/negatives are set when needed
        if (self.use_embedding or self.use_prompts) and (self.positives is None or len(self.positives) == 0) and \
                (self.negatives is None or len(self.negatives) == 0):
            raise Exception("At least one of positive or negative texts must be set when using embedding or prompt validation.")
        
        # Validate image classifier settings if enabled
        if self.use_image_classifier:
            if self.image_classifier is not None and any([category not in self.image_classifier_categories for category in self.image_classifier_selected_categories]):
                raise Exception(f"One or more selected categories {self.image_classifier_selected_categories} were not found in the image classifier's category options")
            if self.image_classifier_name is not None and self.image_classifier_name.strip() != "" and self.image_classifier is None:
                raise Exception(f"The image classifier \"{self.image_classifier_name}\" was not found in the available image classifiers")
        
        if self.is_move_action() and not os.path.isdir(self.action_modifier):
            raise Exception('Action modifier must be a valid directory')

    def validate_dirs(self):
        errors = []
        if self.action_modifier and self.action_modifier != "" and not os.path.isdir(self.action_modifier):
            errors.append(_("Action modifier is not a valid directory: ") + self.action_modifier)
        if self.profile is not None:
            for directory in self.profile.directories:
                if not os.path.isdir(directory):
                    errors.append(_("Profile directory is not a valid directory: ") + directory)
        if len(errors) > 0:
            logger.error(_("Invalid prevalidation {0}, may cause errors or be unable to run!").format(self.name))
            for error in errors:
                logger.warning(error)

    def is_move_action(self):
        return self.action == PrevalidationAction.MOVE or self.action == PrevalidationAction.COPY

    def move_index(self, idx, direction_count=1):
        """Move a prevalidation in the list by the specified number of positions.
        
        Args:
            idx: Current index of the prevalidation to move
            direction_count: Positive to move down (higher index), negative to move up (lower index)
        """
        prevalidations = PrevalidationsWindow.prevalidations
        list_len = len(prevalidations)
        if list_len <= 1:
            return  # Nothing to move
        
        # Calculate target index with wrapping
        target_idx = (idx + direction_count) % list_len
        if target_idx < 0:
            target_idx += list_len
        
        # If target is the same as current, no move needed
        if target_idx == idx:
            return
        
        # Simple approach: remove the item and insert it at the target position
        move_item = prevalidations.pop(idx)
        prevalidations.insert(target_idx, move_item)

    def to_dict(self):
        return {
            "name": self.name,
            "positives": self.positives,
            "negatives": self.negatives,
            "threshold": self.threshold,
            "action": self.action.value,
            "action_modifier": self.action_modifier,
            "profile_name": self.profile_name,
            "is_active": self.is_active,
            "image_classifier_name": self.image_classifier_name,
            "image_classifier_selected_categories": self.image_classifier_selected_categories,
            "use_embedding": self.use_embedding,
            "use_image_classifier": self.use_image_classifier,
            "use_prompts": self.use_prompts,
            "use_blacklist": self.use_blacklist,
            "lookahead_names": self.lookahead_names,
            }

    @staticmethod
    def from_dict(d):
        # Handle backward compatibility - detect original type based on data presence
        if 'use_embedding' not in d:
            # If image_classifier_name is set, it was an image classifier prevalidation
            if 'image_classifier_name' in d and d['image_classifier_name'] and d['image_classifier_name'].strip():
                d['use_embedding'] = False
                d['use_image_classifier'] = True
            else:
                # Otherwise it was an embedding prevalidation
                d['use_embedding'] = True
                d['use_image_classifier'] = False
        if 'use_image_classifier' not in d:
            d['use_image_classifier'] = False
        if 'use_prompts' not in d:
            d['use_prompts'] = False
        if 'use_blacklist' not in d:
            d['use_blacklist'] = False
        if 'lookahead_names' not in d:
            d['lookahead_names'] = []
        if 'profile_name' not in d:
            d['profile_name'] = None
        
        # Handle backward compatibility: if run_on_folder exists but no profile_name, create temporary profile
        run_on_folder = d.get('run_on_folder')
        if run_on_folder and not d.get('profile_name'):
            pv = Prevalidation(**d)
            # Use update_profile_instance to handle profile lookup/creation
            pv.update_profile_instance(profile_name=run_on_folder, directory_path=run_on_folder)
            return pv
        
        return Prevalidation(**d)

    def __str__(self) -> str:
        out = self.name
        validation_types = []
        if self.use_embedding:
            validation_types.append(_("embedding"))
        if self.use_image_classifier and self.image_classifier_name and self.image_classifier_name.strip():
            validation_types.append(_("classifier {0}").format(self.image_classifier_name))
        if self.use_prompts:
            validation_types.append(_("prompts"))
        
        if validation_types:
            # Build the description parts
            description_parts = []
            
            # Add categories if image classifier is enabled and has categories
            if self.use_image_classifier and self.image_classifier_selected_categories:
                description_parts.append(_("categories: {0}").format(", ".join(self.image_classifier_selected_categories)))
            
            # Add positives/negatives if any are set
            if self.positives or self.negatives:
                description_parts.append(_("{0} positives, {1} negatives").format(len(self.positives), len(self.negatives)))
            
            # Combine all parts
            if description_parts:
                out += _(" using {0} ({1})").format(", ".join(validation_types), "; ".join(description_parts))
            else:
                out += _(" using {0}").format(", ".join(validation_types))
        else:
            out += _(" ({0} positives, {1} negatives)").format(len(self.positives), len(self.negatives))

        if self.lookahead_names:
            out += " <" + _("lookaheads: {0}").format(", ".join(self.lookahead_names)) + ">"
        
        return out

class DirectoryProfileWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, profile=None, dimensions="600x500"):
        DirectoryProfileWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = DirectoryProfileWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.profile = profile if profile is not None else DirectoryProfile()
        self.is_edit = profile is not None
        self.original_name = self.profile.name if self.is_edit else None
        DirectoryProfileWindow.top_level.title(_("Edit Profile") if self.is_edit else _("Create Profile"))

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        
        # Profile name
        self.label_name = Label(self.frame)
        self.add_label(self.label_name, _("Profile Name"), row=row, wraplength=DirectoryProfileWindow.COL_0_WIDTH)
        self.profile_name_var = StringVar(self.master, value=self.profile.name)
        self.profile_name_entry = Entry(self.frame, textvariable=self.profile_name_var, width=50, 
                                        font=fnt.Font(size=config.font_size))
        self.profile_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        
        # Directories listbox with scrollbar
        self.label_directories = Label(self.frame)
        self.add_label(self.label_directories, _("Directories"), row=row, wraplength=DirectoryProfileWindow.COL_0_WIDTH)
        
        directories_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        directories_frame.grid(row=row, column=1, sticky=W+E)
        
        listbox_frame = Frame(directories_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.directories_listbox = Listbox(listbox_frame, height=6, width=50, yscrollcommand=scrollbar.set,
                                           font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.directories_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.directories_listbox.yview)
        
        # Buttons for directories
        dir_buttons_frame = Frame(directories_frame, bg=AppStyle.BG_COLOR)
        dir_buttons_frame.pack(side=LEFT, padx=(5, 0))
        
        self.add_dir_btn = Button(dir_buttons_frame, text=_("Add"), command=self.add_directory)
        self.add_dir_btn.pack(side=TOP, pady=2)
        
        self.remove_dir_btn = Button(dir_buttons_frame, text=_("Remove"), command=self.remove_directory)
        self.remove_dir_btn.pack(side=TOP, pady=2)
        
        # Initialize directories listbox
        self.refresh_directories_listbox()

        row += 1
        self.done_btn = None
        self.add_btn("done_btn", _("Done"), self.finalize_profile, row=row, column=0)

        self.master.update()

    def refresh_directories_listbox(self):
        """Refresh the directories listbox."""
        if hasattr(self, 'directories_listbox'):
            self.directories_listbox.delete(0, "end")
            for directory in self.profile.directories:
                self.directories_listbox.insert("end", directory)

    def add_directory(self):
        """Add a directory to the profile."""
        # Simple text entry dialog - could be enhanced with file browser
        from tkinter import simpledialog
        directory = simpledialog.askstring(_("Add Directory"), _("Enter directory path:"))
        if directory and directory.strip():
            directory = directory.strip()
            if os.path.isdir(directory):
                if directory not in self.profile.directories:
                    self.profile.directories.append(directory)
                    self.refresh_directories_listbox()
                else:
                    logger.warning(f"Directory {directory} already in profile")
            else:
                logger.error(f"Invalid directory: {directory}")

    def remove_directory(self):
        """Remove the selected directory from the profile."""
        selection = self.directories_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(self.profile.directories):
            del self.profile.directories[idx]
            self.refresh_directories_listbox()

    def finalize_profile(self, event=None):
        profile_name = self.profile_name_var.get().strip()
        
        if not profile_name:
            logger.error("Profile name is required")
            return
        
        # Check if profile name already exists (for new profiles)
        if not self.is_edit:
            if PrevalidationsWindow.get_profile_by_name(profile_name) is not None:
                logger.error(f"Profile with name {profile_name} already exists")
                return
        else:
            # For editing, check if name changed and conflicts
            if profile_name != self.original_name:
                if PrevalidationsWindow.get_profile_by_name(profile_name) is not None:
                    logger.error(f"Profile with name {profile_name} already exists")
                    return
        
        self.profile.name = profile_name
        
        if not self.is_edit:
            PrevalidationsWindow.profiles.append(self.profile)
        else:
            # Find and update the existing profile
            for idx, prof in enumerate(PrevalidationsWindow.profiles):
                if prof.name == self.original_name:
                    PrevalidationsWindow.profiles[idx] = self.profile
                    break
            
            # Update references if name changed
            if self.original_name != profile_name:
                for pv in PrevalidationsWindow.prevalidations:
                    if pv.profile_name == self.original_name:
                        pv.profile_name = profile_name
        
        self.close_windows()
        self.refresh_callback()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name, None) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)


class PrevalidationLookaheadWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, lookahead=None, dimensions="500x450"):
        PrevalidationLookaheadWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = PrevalidationLookaheadWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.lookahead = lookahead if lookahead is not None else PrevalidationLookahead()
        self.is_edit = lookahead is not None
        self.original_name = self.lookahead.name if self.is_edit else None
        PrevalidationLookaheadWindow.top_level.title(_("Edit Lookahead") if self.is_edit else _("Create Lookahead"))

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

        row = 0
        
        # Lookahead name
        self.label_name = Label(self.frame)
        self.add_label(self.label_name, _("Lookahead Name"), row=row, wraplength=PrevalidationLookaheadWindow.COL_0_WIDTH)
        self.lookahead_name_var = StringVar(self.master, value=self.lookahead.name)
        self.lookahead_name_entry = Entry(self.frame, textvariable=self.lookahead_name_var, width=50, 
                                          font=fnt.Font(size=config.font_size))
        self.lookahead_name_entry.grid(row=row, column=1, sticky=W)

        row += 1
        
        # Checkbox to toggle between prevalidation name and custom text
        self.is_prevalidation_name_var = BooleanVar(value=self.lookahead.is_prevalidation_name)
        self.is_prevalidation_name_checkbox = Checkbutton(self.frame, 
                                                          text=_("Reference existing prevalidation name"), 
                                                          variable=self.is_prevalidation_name_var,
                                                          command=self.update_ui_for_type,
                                                          bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                                                          activebackground=AppStyle.BG_COLOR,
                                                          activeforeground=AppStyle.FG_COLOR,
                                                          font=fnt.Font(size=config.font_size))
        self.is_prevalidation_name_checkbox.grid(row=row, column=1, sticky=W, pady=5)

        row += 1
        
        # Label for name_or_text field
        self.label_name_or_text = Label(self.frame)
        self.add_label(self.label_name_or_text, _("Prevalidation Name or Custom Text"), 
                      row=row, wraplength=PrevalidationLookaheadWindow.COL_0_WIDTH)
        
        # Frame to hold either combobox or entry
        self.name_or_text_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.name_or_text_frame.grid(row=row, column=1, sticky=W+E)
        
        # Get list of existing prevalidation names
        self.existing_names = [pv.name for pv in PrevalidationsWindow.prevalidations]
        
        self.name_or_text_var = StringVar(self.master, value=self.lookahead.name_or_text)
        
        # Create both widgets but only show one based on checkbox
        self.name_or_text_combobox = Combobox(self.name_or_text_frame, textvariable=self.name_or_text_var, 
                                             values=self.existing_names, width=47,
                                             font=fnt.Font(size=config.font_size))
        self.name_or_text_combobox.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)
        
        self.name_or_text_entry = Entry(self.name_or_text_frame, textvariable=self.name_or_text_var, width=50,
                                        font=fnt.Font(size=config.font_size))
        
        # Initialize UI based on current type
        self.update_ui_for_type()

        row += 1
        
        # Threshold slider
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=PrevalidationLookaheadWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.lookahead.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.done_btn = None
        self.add_btn("done_btn", _("Done"), self.finalize_lookahead, row=row, column=0)

        self.master.update()

    def update_ui_for_type(self):
        """Update UI to show either combobox or entry based on checkbox state."""
        is_prevalidation = self.is_prevalidation_name_var.get()
        
        # Clear the frame
        for widget in self.name_or_text_frame.winfo_children():
            widget.destroy()
        
        if is_prevalidation:
            # Show combobox for selecting prevalidation name
            self.name_or_text_combobox = Combobox(self.name_or_text_frame, textvariable=self.name_or_text_var, 
                                                 values=self.existing_names, width=47,
                                                 font=fnt.Font(size=config.font_size))
            self.name_or_text_combobox.pack(fill=BOTH, expand=True)
            self.name_or_text_combobox.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)
        else:
            # Show entry for custom text
            self.name_or_text_entry = Entry(self.name_or_text_frame, textvariable=self.name_or_text_var, width=50,
                                            font=fnt.Font(size=config.font_size))
            self.name_or_text_entry.pack(fill=BOTH, expand=True)

    def set_threshold(self, event=None):
        self.lookahead.threshold = float(self.threshold_slider.get()) / 100

    def finalize_lookahead(self, event=None):
        lookahead_name = self.lookahead_name_var.get().strip()
        name_or_text = self.name_or_text_var.get().strip()
        
        if not lookahead_name:
            logger.error("Lookahead name is required")
            return
        if not name_or_text:
            logger.error("Prevalidation name or custom text is required")
            return
        
        # Check if lookahead name already exists (for new lookaheads)
        if not self.is_edit:
            if PrevalidationsWindow.get_lookahead_by_name(lookahead_name) is not None:
                logger.error(f"Lookahead with name {lookahead_name} already exists")
                return
        else:
            # For editing, check if name changed and conflicts
            old_lookahead = self.lookahead
            if lookahead_name != old_lookahead.name:
                if PrevalidationsWindow.get_lookahead_by_name(lookahead_name) is not None:
                    logger.error(f"Lookahead with name {lookahead_name} already exists")
                    return
        
        threshold = self.lookahead.threshold
        is_prevalidation_name = self.is_prevalidation_name_var.get()
        
        # If it's a prevalidation name, verify it exists
        if is_prevalidation_name and name_or_text not in self.existing_names:
            logger.warning(f"Prevalidation '{name_or_text}' not found, treating as custom text")
            is_prevalidation_name = False
        
        self.lookahead.name = lookahead_name
        self.lookahead.name_or_text = name_or_text
        self.lookahead.threshold = threshold
        self.lookahead.is_prevalidation_name = is_prevalidation_name
        
        if not self.is_edit:
            PrevalidationsWindow.lookaheads.append(self.lookahead)
        else:
            # Find and update the existing lookahead by matching the original name
            for idx, lh in enumerate(PrevalidationsWindow.lookaheads):
                if lh.name == self.original_name:
                    PrevalidationsWindow.lookaheads[idx] = self.lookahead
                    break
            
            # Update references if name changed
            if self.original_name != lookahead_name:
                for pv in PrevalidationsWindow.prevalidations:
                    if self.original_name in pv.lookahead_names:
                        idx_ref = pv.lookahead_names.index(self.original_name)
                        pv.lookahead_names[idx_ref] = lookahead_name
        
        self.close_windows()
        self.refresh_callback()

    def close_windows(self, event=None):
        self.master.destroy()

    def add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))

    def add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name, None) is None:
            button = Button(master=self.frame, text=text, command=command)
            setattr(self, button_ref_name, button)
            button # for some reason this is necessary to maintain the reference?
            button.grid(row=row, column=column)


class PrevalidationModifyWindow():
    top_level = None
    COL_0_WIDTH = 600

    def __init__(self, master, app_actions, refresh_callback, prevalidation, dimensions="600x600"):
        PrevalidationModifyWindow.top_level = SmartToplevel(persistent_parent=master, geometry=dimensions)
        self.master = PrevalidationModifyWindow.top_level
        self.app_actions = app_actions
        self.refresh_callback = refresh_callback
        self.prevalidation = prevalidation if prevalidation is not None else Prevalidation()
        PrevalidationModifyWindow.top_level.title(_("Modify Prevalidation") + f": {self.prevalidation.name}")

        # Ensure image classifier is loaded for UI display
        self.prevalidation._ensure_image_classifier_loaded(app_actions.title_notify if app_actions is not None else None)

        self.frame = Frame(self.master)
        self.frame.grid(column=0, row=0)
        self.frame.columnconfigure(0, weight=9)
        self.frame.columnconfigure(1, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)

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
        # Validation type checkboxes
        self.label_validation_types = Label(self.frame)
        self.add_label(self.label_validation_types, _("Validation Types"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        self.use_embedding_var = BooleanVar(value=self.prevalidation.use_embedding)
        self.use_embedding_checkbox = Checkbutton(self.frame, text=_("Use Embedding"), variable=self.use_embedding_var, 
                                                command=self.update_ui_for_validation_types,
                                                bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_embedding_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_image_classifier_var = BooleanVar(value=self.prevalidation.use_image_classifier)
        self.use_image_classifier_checkbox = Checkbutton(self.frame, text=_("Use Image Classifier"), variable=self.use_image_classifier_var,
                                                        command=self.update_ui_for_validation_types,
                                                        bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_image_classifier_checkbox.grid(row=row, column=1, sticky=W)
        
        row += 1
        self.use_prompts_var = BooleanVar(value=self.prevalidation.use_prompts)
        self.use_prompts_checkbox = Checkbutton(self.frame, text=_("Use Prompts"), variable=self.use_prompts_var,
                                               command=self.update_ui_for_validation_types,
                                               bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.use_prompts_checkbox.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_threshold = Label(self.frame)
        self.add_label(self.label_threshold, _("Threshold"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        self.threshold_slider = Scale(self.frame, from_=0, to=100, orient=HORIZONTAL, command=self.set_threshold)
        self.threshold_slider.set(float(self.prevalidation.threshold) * 100)
        self.threshold_slider.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_action = Label(self.frame)
        self.add_label(self.label_action, _("Action"), row=row, column=0)
        self.action_var = StringVar(self.master, value=self.prevalidation.action.get_translation())
        action_options = [k.get_translation() for k in PrevalidationAction]
        self.action_choice = Combobox(self.frame, textvariable=self.action_var, values=action_options)
        self.action_choice.current(action_options.index(self.prevalidation.action.get_translation()))
        self.action_choice.bind("<<ComboboxSelected>>", self.set_action)
        self.action_choice.grid(row=row, column=1, sticky=W)
        # Style the combobox
        self.action_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_action_modifier = Label(self.frame)
        self.add_label(self.label_action_modifier, _("Action Modifier"), row=row, column=0)
        self.action_modifier_var = StringVar(self.master, value=self.prevalidation.action_modifier)
        self.action_modifier_entry = Entry(self.frame, textvariable=self.action_modifier_var, width=50, font=fnt.Font(size=config.font_size))
        self.action_modifier_entry.grid(row=row, column=1, sticky=W)

        row += 1
        self.label_image_classifier_name = Label(self.frame)
        self.add_label(self.label_image_classifier_name, _("Image Classifier Name"), row=row, column=0)
        self.image_classifier_name_var = StringVar(self.master, value=self.prevalidation.image_classifier_name)
        name_options = [""]
        name_options.extend(image_classifier_manager.get_model_names())
        self.image_classifier_name_choice = Combobox(self.frame, textvariable=self.image_classifier_name_var, values=name_options)
        self.image_classifier_name_choice.current(name_options.index(self.prevalidation.image_classifier_name))
        self.image_classifier_name_choice.bind("<<ComboboxSelected>>", self.set_image_classifier)
        self.image_classifier_name_choice.grid(row=row, column=1, sticky=W)
        self.image_classifier_name_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)

        row += 1
        self.label_selected_category = Label(self.frame)
        self.add_label(self.label_selected_category, _("Image Classifier Selected Category"), row=row, column=0)
        self.selected_category_choice_row = row
        self.image_classifier_selected_categories = MultiSelectDropdown(self.frame, self.prevalidation.image_classifier_categories[:],
                                                                        row=self.selected_category_choice_row, sticky=W,
                                                                        select_text=_("Select Categories..."),
                                                                        selected=self.prevalidation.image_classifier_selected_categories[:],
                                                                        command=self.set_image_classifier_selected_categories)

        row += 1
        # Prevalidation Lookaheads section - just select which lookaheads to use
        self.label_lookaheads = Label(self.frame)
        self.add_label(self.label_lookaheads, _("Lookaheads (select from shared list)"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        # Multi-select dropdown for lookaheads
        lookahead_options = [lookahead.name for lookahead in PrevalidationsWindow.lookaheads]
        self.lookaheads_multiselect = MultiSelectDropdown(self.frame, lookahead_options[:],
                                                          row=row, column=1, sticky=W,
                                                          select_text=_("Select Lookaheads..."),
                                                          selected=self.prevalidation.lookahead_names[:],
                                                          command=self.set_lookahead_names)
        
        row += 1
        # Profile selection
        self.label_profile = Label(self.frame)
        self.add_label(self.label_profile, _("Directory Profile"), row=row, wraplength=PrevalidationModifyWindow.COL_0_WIDTH)
        
        # Profile dropdown - include "(Global)" option for no profile
        profile_options = [""]  # Empty string = Global
        profile_options.extend([profile.name for profile in PrevalidationsWindow.profiles])
        
        current_profile_name = self.prevalidation.profile_name if self.prevalidation.profile_name else ""
        self.profile_var = StringVar(self.master, value=current_profile_name)
        self.profile_choice = Combobox(self.frame, textvariable=self.profile_var, values=profile_options, width=47,
                                       font=fnt.Font(size=config.font_size))
        # Set current selection
        if current_profile_name in profile_options:
            self.profile_choice.current(profile_options.index(current_profile_name))
        else:
            self.profile_choice.current(0)  # Default to Global
        self.profile_choice.bind("<<ComboboxSelected>>", self.set_profile_name)
        self.profile_choice.grid(row=row, column=1, sticky=W)
        self.profile_choice.config(background=AppStyle.BG_COLOR, foreground=AppStyle.FG_COLOR)
        
        row += 1
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Done"), self.finalize_prevalidation, row=row, column=0)

        # Initialize UI based on current validation types
        self.update_ui_for_validation_types()

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

    def set_validation_types(self):
        self.prevalidation.use_embedding = self.use_embedding_var.get()
        self.prevalidation.use_image_classifier = self.use_image_classifier_var.get()
        self.prevalidation.use_prompts = self.use_prompts_var.get()

    def update_ui_for_validation_types(self):
        """Update UI elements based on the selected validation types."""
        use_embedding = self.use_embedding_var.get()
        use_image_classifier = self.use_image_classifier_var.get()
        use_prompts = self.use_prompts_var.get()
        
        # Show/hide image classifier fields
        if use_image_classifier:
            self.image_classifier_name_choice.grid()
            self.label_image_classifier_name.grid()
            self.image_classifier_selected_categories.button.grid()
            self.label_selected_category.grid()
        else:
            self.image_classifier_name_choice.grid_remove()
            self.label_image_classifier_name.grid_remove()
            self.image_classifier_selected_categories.button.grid_remove()
            self.label_selected_category.grid_remove()
        
        # Show/hide positive/negative fields based on type
        if use_embedding or use_prompts:
            self.positives_entry.grid()
            self.label_positives.grid()
            self.negatives_entry.grid()
            self.label_negatives.grid()
        else:
            self.positives_entry.grid_remove()
            self.label_positives.grid_remove()
            self.negatives_entry.grid_remove()
            self.label_negatives.grid_remove()

    def set_action(self, event=None):
        self.prevalidation.action = PrevalidationAction.get_action(self.action_var.get())

    def set_action_modifier(self):
        self.prevalidation.action_modifier = self.action_modifier_var.get()

    def set_image_classifier(self, event=None):
        self.prevalidation.set_image_classifier(self.image_classifier_name_var.get())
        set_category_value = self.prevalidation.image_classifier_categories[0] \
                if self.prevalidation.is_selected_category_unset() else self.prevalidation.image_classifier_selected_categories
        self.image_classifier_selected_categories.set_options_and_selection(
                self.prevalidation.image_classifier_categories[:], set_category_value[:])
        # self.image_classifier_selected_category_choice = OptionMenu(self.frame, self.image_classifier_selected_category_var,
        #                                                             *self.prevalidation.image_classifier_categories[:],
        #                                                             command=self.set_image_classifier_selected_category)
        self.master.update()

    def set_image_classifier_selected_categories(self, event=None):
        self.prevalidation.image_classifier_selected_categories = list(self.image_classifier_selected_categories.get_selected())

    def set_lookahead_names(self, event=None):
        """Set the selected lookahead names for this prevalidation."""
        self.prevalidation.lookahead_names = list(self.lookaheads_multiselect.get_selected())
    
    def set_profile_name(self, event=None):
        """Set the profile name for this prevalidation."""
        selected_profile_name = self.profile_var.get().strip()
        # Empty string means Global (no profile)
        profile_name = selected_profile_name if selected_profile_name else None
        self.prevalidation.update_profile_instance(profile_name=profile_name)
    
    def refresh_profile_options(self):
        """Refresh the profile dropdown options."""
        if hasattr(self, 'profile_choice'):
            profile_options = [""]  # Empty string = Global
            profile_options.extend([profile.name for profile in PrevalidationsWindow.profiles])
            
            current_value = self.profile_var.get()
            self.profile_choice['values'] = profile_options
            
            # Update current selection if still valid, otherwise default to Global
            if current_value in profile_options:
                self.profile_choice.current(profile_options.index(current_value))
            else:
                self.profile_choice.current(0)
                self.profile_var.set("")
    
    def refresh_lookahead_options(self):
        """Refresh the lookahead multiselect dropdown options."""
        lookahead_options = [lookahead.name for lookahead in PrevalidationsWindow.lookaheads]
        self.lookaheads_multiselect.set_options_and_selection(
            lookahead_options[:], 
            self.prevalidation.lookahead_names[:]
        )
    
    def finalize_prevalidation(self, event=None):
        self.set_name()
        self.set_positives()
        self.set_negatives()
        self.set_threshold()
        self.set_validation_types()
        self.set_action()
        self.set_action_modifier()
        # self.set_image_classifier()
        self.set_image_classifier_selected_categories()
        self.set_lookahead_names()  # Save lookahead selections
        self.set_profile_name()  # Save profile selection
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
    prevalidated_cache: dict[str, PrevalidationAction] = {}
    directories_to_exclude: list[str] = []
    top_level = None
    prevalidation_modify_window: Optional[PrevalidationModifyWindow] = None
    lookahead_window: Optional[PrevalidationLookaheadWindow] = None
    profile_window: Optional[DirectoryProfileWindow] = None
    prevalidations: list[Prevalidation] = []
    lookaheads: list[PrevalidationLookahead] = []  # Shared lookaheads that can be referenced by multiple prevalidations
    profiles: list[DirectoryProfile] = []  # Shared directory profiles that can be referenced by multiple prevalidations

    MAX_PRESETS = 50

    MAX_HEIGHT = 900
    N_TAGS_CUTOFF = 30
    COL_0_WIDTH = 600

    @staticmethod
    def prevalidate(image_path, get_base_dir_func, hide_callback, notify_callback, add_mark_callback) -> Optional[PrevalidationAction]:
        # Reset lookahead cache for this prevalidate call
        for lookahead in PrevalidationsWindow.lookaheads:
            lookahead.run_result = None
        
        base_dir = get_base_dir_func()
        if len(PrevalidationsWindow.directories_to_exclude) > 0 and base_dir in PrevalidationsWindow.directories_to_exclude:
            return None
        if image_path not in PrevalidationsWindow.prevalidated_cache:
            prevalidation_action = None
            for prevalidation in PrevalidationsWindow.prevalidations:
                if prevalidation.is_active:
                    if prevalidation.is_move_action() and prevalidation.action_modifier == base_dir:
                        continue
                    # Check if prevalidation should run on this directory
                    if prevalidation.profile is not None and base_dir not in prevalidation.profile.directories:
                        continue
                    prevalidation_action = prevalidation.run_on_image_path(image_path, hide_callback, notify_callback, add_mark_callback)
                    if prevalidation_action is not None:
                        break
            if prevalidation_action is None or prevalidation_action.is_cache_type():
                PrevalidationsWindow.prevalidated_cache[image_path] = prevalidation_action
        else:
            prevalidation_action = PrevalidationsWindow.prevalidated_cache[image_path]
        return prevalidation_action

    @staticmethod
    def set_prevalidations():
        # Load lookaheads first
        for lookahead_dict in list(app_info_cache.get_meta("recent_lookaheads", default_val=[])):
            lookahead = PrevalidationLookahead.from_dict(lookahead_dict)
            PrevalidationsWindow.lookaheads.append(lookahead)
        
        # Load profiles
        for profile_dict in list(app_info_cache.get_meta("recent_profiles", default_val=[])):
            profile = DirectoryProfile.from_dict(profile_dict)
            PrevalidationsWindow.profiles.append(profile)
        
        # Then load prevalidations
        for prevalidation_dict in list(app_info_cache.get_meta("recent_prevalidations", default_val=[])):
            prevalidation: Prevalidation = Prevalidation.from_dict(prevalidation_dict)
            prevalidation.update_profile_instance()
            prevalidation.validate_dirs()
            PrevalidationsWindow.prevalidations.append(prevalidation)
            if prevalidation.is_move_action():
                PrevalidationsWindow.directories_to_exclude.append(prevalidation.action_modifier)

    @staticmethod
    def store_prevalidations():
        # Store lookaheads
        lookahead_dicts = []
        for lookahead in PrevalidationsWindow.lookaheads:
            lookahead_dicts.append(lookahead.to_dict())
        app_info_cache.set_meta("recent_lookaheads", lookahead_dicts)
        
        # Store profiles
        profile_dicts = []
        for profile in PrevalidationsWindow.profiles:
            profile_dicts.append(profile.to_dict())
        app_info_cache.set_meta("recent_profiles", profile_dicts)
        
        # Store prevalidations
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
    def get_lookahead_by_name(name):
        """Get a lookahead by name. Returns None if not found."""
        for lookahead in PrevalidationsWindow.lookaheads:
            if name == lookahead.name:
                return lookahead
        return None
    
    @staticmethod
    def get_profile_by_name(name):
        """Get a profile by name. Returns None if not found."""
        for profile in PrevalidationsWindow.profiles:
            if name == profile.name:
                return profile
        return None

    @staticmethod
    def get_geometry(is_gui=True):
        width = 1200
        height = 600
        return f"{width}x{height}"

    def __init__(self, master, app_actions):
        PrevalidationsWindow.top_level = SmartToplevel(persistent_parent=master, title=_("Prevalidations"), geometry=PrevalidationsWindow.get_geometry())
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
        self.frame.columnconfigure(4, weight=1)
        self.frame.columnconfigure(5, weight=1)
        self.frame.columnconfigure(6, weight=1)
        self.frame.columnconfigure(7, weight=1)
        self.frame.config(bg=AppStyle.BG_COLOR)
        
        self.add_lookahead_management_section()
        self.add_profile_management_section()

        # Prevalidations section title (row 4: after lookaheads 0-1, profiles 2-3)
        self.prevalidations_title = Label(self.frame, text=_("Prevalidations"), 
                                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                         font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.prevalidations_title.grid(row=4, column=0, columnspan=4, sticky=W, pady=(5, 10))
        
        self.add_prevalidation_btn = None
        self.add_btn("add_prevalidation_btn", _("Add prevalidation"), self.open_prevalidation_modify_window, row=4, column=1)
        self.clear_recent_prevalidations_btn = None
        self.add_btn("clear_recent_prevalidations_btn", _("Clear prevalidations"), self.clear_recent_prevalidations, row=4, column=2)

        # Add enable prevalidations checkbox (row 5)
        self.label_enable_prevalidations = Label(self.frame)
        self.enable_prevalidations = BooleanVar(value=config.enable_prevalidations)
        self.checkbox_enable_prevalidations = Checkbutton(self.frame, variable=self.enable_prevalidations, 
                                                        command=self.toggle_prevalidations)
        self.add_label(self.label_enable_prevalidations, _("Enable Prevalidations"), row=5, wraplength=PrevalidationsWindow.COL_0_WIDTH)
        self.checkbox_enable_prevalidations.grid(row=5, column=1, sticky=W)

        self.add_prevalidation_widgets()

        # self.master.bind("<Key>", self.filter_prevalidations)
        # self.master.bind("<Return>", self.do_action)
        self.master.bind("<Escape>", self.close_windows)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.update()
        self.frame.after(1, lambda: self.frame.focus_force())

    def add_lookahead_management_section(self):
        """Add a section for managing lookaheads."""
        
        # Lookaheads section title
        self.lookaheads_title = Label(self.frame, text=_("Lookaheads"), 
                                     bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                     font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.lookaheads_title.grid(row=0, column=0, columnspan=4, sticky=W, pady=(20, 10))
        
        # Create a separate frame for lookaheads
        self.lookahead_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.lookahead_frame.grid(row=1, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
        
        # Listbox with scrollbar for lookaheads
        listbox_frame = Frame(self.lookahead_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.grid(row=1, column=0, sticky=W+E)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.lookaheads_listbox = Listbox(listbox_frame, height=4, width=60, yscrollcommand=scrollbar.set,
                                          font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.lookaheads_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.lookaheads_listbox.yview)
        
        # Buttons frame
        buttons_frame = Frame(self.lookahead_frame, bg=AppStyle.BG_COLOR)
        buttons_frame.grid(row=1, column=1, sticky=W, padx=(5, 0))
        
        self.add_lookahead_btn = Button(buttons_frame, text=_("Add Lookahead"), command=self.add_lookahead)
        self.add_lookahead_btn.pack(side=TOP, pady=2)
        
        self.edit_lookahead_btn = Button(buttons_frame, text=_("Edit Lookahead"), command=self.edit_lookahead)
        self.edit_lookahead_btn.pack(side=TOP, pady=2)
        
        self.remove_lookahead_btn = Button(buttons_frame, text=_("Remove Lookahead"), command=self.remove_lookahead)
        self.remove_lookahead_btn.pack(side=TOP, pady=2)
        
        # Initialize lookaheads listbox
        self.refresh_lookaheads_listbox()
        
        self.lookahead_frame.columnconfigure(0, weight=1)

    def refresh_lookaheads_listbox(self):
        """Refresh the lookaheads listbox with current lookaheads."""
        if hasattr(self, 'lookaheads_listbox'):
            self.lookaheads_listbox.delete(0, "end")
            for lookahead in PrevalidationsWindow.lookaheads:
                display_text = f"{lookahead.name} ({lookahead.name_or_text}, threshold: {lookahead.threshold:.2f})"
                self.lookaheads_listbox.insert("end", display_text)
    
    def add_lookahead(self):
        """Open dialog to add a new lookahead."""
        if PrevalidationsWindow.lookahead_window is not None:
            PrevalidationsWindow.lookahead_window.master.destroy()
        PrevalidationsWindow.lookahead_window = PrevalidationLookaheadWindow(
            self.master, self.app_actions, self.refresh_lookaheads_listbox)
    
    def edit_lookahead(self):
        """Open dialog to edit the selected lookahead."""
        selection = self.lookaheads_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(PrevalidationsWindow.lookaheads):
            if PrevalidationsWindow.lookahead_window is not None:
                PrevalidationsWindow.lookahead_window.master.destroy()
            PrevalidationsWindow.lookahead_window = PrevalidationLookaheadWindow(
                self.master, self.app_actions, self.refresh_lookaheads_listbox, 
                PrevalidationsWindow.lookaheads[idx])
    
    def remove_lookahead(self):
        """Remove the selected lookahead."""
        selection = self.lookaheads_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(PrevalidationsWindow.lookaheads):
            lookahead = PrevalidationsWindow.lookaheads[idx]
            # Check if any prevalidation is using this lookahead
            used_by = [pv.name for pv in PrevalidationsWindow.prevalidations if lookahead.name in pv.lookahead_names]
            if used_by:
                logger.warning(f"Lookahead {lookahead.name} is used by prevalidations: {', '.join(used_by)}")
            del PrevalidationsWindow.lookaheads[idx]
            self.refresh_lookaheads_listbox()
            # Refresh modify window if open
            if PrevalidationsWindow.prevalidation_modify_window:
                PrevalidationsWindow.prevalidation_modify_window.refresh_lookahead_options()
    
    def add_profile_management_section(self):
        """Add a section for managing directory profiles."""
        
        # Profiles section title
        self.profiles_title = Label(self.frame, text=_("Directory Profiles"), 
                                   bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, 
                                   font=fnt.Font(size=config.font_size + 2, weight="bold"))
        self.profiles_title.grid(row=2, column=0, columnspan=4, sticky=W, pady=(20, 10))
        
        # Create a separate frame for profiles
        self.profile_frame = Frame(self.frame, bg=AppStyle.BG_COLOR)
        self.profile_frame.grid(row=3, column=0, columnspan=4, sticky=W+E, padx=5, pady=5)
        
        # Listbox with scrollbar for profiles
        listbox_frame = Frame(self.profile_frame, bg=AppStyle.BG_COLOR)
        listbox_frame.grid(row=1, column=0, sticky=W+E)
        
        scrollbar = Scrollbar(listbox_frame)
        scrollbar.pack(side=RIGHT, fill="y")
        
        self.profiles_listbox = Listbox(listbox_frame, height=4, width=60, yscrollcommand=scrollbar.set,
                                        font=fnt.Font(size=config.font_size), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        self.profiles_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.profiles_listbox.yview)
        
        # Buttons frame
        buttons_frame = Frame(self.profile_frame, bg=AppStyle.BG_COLOR)
        buttons_frame.grid(row=1, column=1, sticky=W, padx=(5, 0))
        
        self.add_profile_btn = Button(buttons_frame, text=_("Add Profile"), command=self.add_profile)
        self.add_profile_btn.pack(side=TOP, pady=2)
        
        self.edit_profile_btn = Button(buttons_frame, text=_("Edit Profile"), command=self.edit_profile)
        self.edit_profile_btn.pack(side=TOP, pady=2)
        
        self.remove_profile_btn = Button(buttons_frame, text=_("Remove Profile"), command=self.remove_profile)
        self.remove_profile_btn.pack(side=TOP, pady=2)
        
        # Initialize profiles listbox
        self.refresh_profiles_listbox()
        
        self.profile_frame.columnconfigure(0, weight=1)

    def refresh_profiles_listbox(self):
        """Refresh the profiles listbox with current profiles."""
        if hasattr(self, 'profiles_listbox'):
            self.profiles_listbox.delete(0, "end")
            for profile in PrevalidationsWindow.profiles:
                dir_count = len(profile.directories)
                dir_or_dirs = 'directory' if dir_count == 1 else 'directories'
                display_text = f"{profile.name} ({dir_count} {dir_or_dirs})"
                self.profiles_listbox.insert("end", display_text)
        
        # Refresh profile options in modify window if open
        if PrevalidationsWindow.prevalidation_modify_window:
            PrevalidationsWindow.prevalidation_modify_window.refresh_profile_options()
    
    def add_profile(self):
        """Open dialog to add a new profile."""
        if PrevalidationsWindow.profile_window is not None:
            PrevalidationsWindow.profile_window.master.destroy()
        PrevalidationsWindow.profile_window = DirectoryProfileWindow(
            self.master, self.app_actions, self.refresh_profiles_listbox)
    
    def edit_profile(self):
        """Open dialog to edit the selected profile."""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(PrevalidationsWindow.profiles):
            if PrevalidationsWindow.profile_window is not None:
                PrevalidationsWindow.profile_window.master.destroy()
            PrevalidationsWindow.profile_window = DirectoryProfileWindow(
                self.master, self.app_actions, self.refresh_profiles_listbox, 
                PrevalidationsWindow.profiles[idx])
    
    def remove_profile(self):
        """Remove the selected profile."""
        selection = self.profiles_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx < len(PrevalidationsWindow.profiles):
            profile = PrevalidationsWindow.profiles[idx]
            # Check if any prevalidation is using this profile
            used_by = [pv.name for pv in PrevalidationsWindow.prevalidations if pv.profile_name == profile.name]
            if used_by:
                logger.warning(f"Profile {profile.name} is used by prevalidations: {', '.join(used_by)}")
            del PrevalidationsWindow.profiles[idx]
            self.refresh_profiles_listbox()
            # Refresh modify window if open
            if PrevalidationsWindow.prevalidation_modify_window:
                PrevalidationsWindow.prevalidation_modify_window.refresh_profile_options()
    
    def add_prevalidation_widgets(self):
        # Start at row 6: after lookaheads (0-1), profiles (2-3), prevalidations title (4), enable checkbox (5)
        row = 6
        base_col = 0
        
        # Add header row
        header_font = fnt.Font(size=config.font_size, weight="bold")
        header_name = Label(self.frame, text=_("Name"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_name.grid(row=row, column=base_col, sticky=W, padx=2, pady=2)
        
        header_action = Label(self.frame, text=_("Action"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_action.grid(row=row, column=base_col + 1, sticky=W, padx=2, pady=2)
        
        header_profile = Label(self.frame, text=_("Profile"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_profile.grid(row=row, column=base_col + 2, sticky=W, padx=2, pady=2)
        
        header_active = Label(self.frame, text=_("Active"), bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=header_font)
        header_active.grid(row=row, column=base_col + 3, sticky=W, padx=2, pady=2)
        
        row += 1  # Move to first data row
        
        for i, prevalidation in enumerate(self.filtered_prevalidations):
            row = 7 + i  # Start data rows at row 7 (after header at row 6)
            label_name = Label(self.frame)
            self.label_list.append(label_name)
            self.add_label(label_name, str(prevalidation), row=row, column=base_col, wraplength=PrevalidationsWindow.COL_0_WIDTH)

            label_action = Label(self.frame)
            self.label_list2.append(label_action)
            self.add_label(label_action, prevalidation.action.get_translation(), row=row, column=base_col + 1)
            
            # Add profile column
            profile_text = ""
            if prevalidation.profile_name:
                profile_text = prevalidation.profile_name
            elif prevalidation.profile:
                profile_text = prevalidation.profile.name
            else:
                profile_text = _("(Global)")
            
            label_profile = Label(self.frame)
            self.add_label(label_profile, profile_text, row=row, column=base_col + 2)

            is_active_var = BooleanVar(value=prevalidation.is_active)
            def set_is_active_handler(prevalidation=prevalidation, var=is_active_var):
                prevalidation.is_active = var.get()
                logger.info(f"Set {prevalidation} to active: {prevalidation.is_active}")
            is_active_box = Checkbutton(self.frame, variable=is_active_var, font=fnt.Font(size=config.font_size), command=set_is_active_handler)
            is_active_box.grid(row=row, column=base_col + 3, sticky=(W))
            self.is_active_list.append(is_active_box)
            self.is_active_var_list.append(is_active_var)

            activate_prevalidation_var = BooleanVar(value=prevalidation.is_active)
            self.activate_prevalidation_choice = Checkbutton(self.frame, variable=activate_prevalidation_var, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, font=fnt.Font(size=config.font_size))
            set_prevalidation_btn = Button(self.frame, text=_("Set"))
            self.set_prevalidation_btn_list.append(set_prevalidation_btn)
            set_prevalidation_btn.grid(row=row, column=base_col+4)
            def set_prevalidation_handler(event, prevalidation=prevalidation, var=activate_prevalidation_var):
                prevalidation.is_active = var.get()
                logger.info(f"Set {prevalidation} to active: {prevalidation.is_active}")
            set_prevalidation_btn.bind("<Button-1>", set_prevalidation_handler)

            modify_prevalidation_btn = Button(self.frame, text=_("Modify"))
            self.set_prevalidation_btn_list.append(modify_prevalidation_btn)
            modify_prevalidation_btn.grid(row=row, column=base_col+5)
            def modify_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.open_prevalidation_modify_window(event, prevalidation)
            modify_prevalidation_btn.bind("<Button-1>", modify_prevalidation_handler)

            delete_prevalidation_btn = Button(self.frame, text=_("Delete"))
            self.delete_prevalidation_btn_list.append(delete_prevalidation_btn)
            delete_prevalidation_btn.grid(row=row, column=base_col+6)
            def delete_prevalidation_handler(event, self=self, prevalidation=prevalidation):
                return self.delete_prevalidation(event, prevalidation)
            delete_prevalidation_btn.bind("<Button-1>", delete_prevalidation_handler)

            move_down_btn = Button(self.frame, text=_("Move down"))
            self.move_down_btn_list.append(move_down_btn)
            move_down_btn.grid(row=row, column=base_col+7)
            def move_down_handler(event, self=self, idx=i, prevalidation=prevalidation):
                prevalidation.move_index(idx, 1)
                self.refresh()
            move_down_btn.bind("<Button-1>", move_down_handler)

    def open_prevalidation_modify_window(self, event=None, prevalidation=None):
        if PrevalidationsWindow.prevalidation_modify_window is not None:
            PrevalidationsWindow.prevalidation_modify_window.master.destroy()
        PrevalidationsWindow.prevalidation_modify_window = PrevalidationModifyWindow(
            self.master, self.app_actions, self.refresh_prevalidations, prevalidation)

    def refresh_prevalidations(self, prevalidation):
        # Check if this is a new prevalidation, if so, insert it at the start
        if prevalidation not in PrevalidationsWindow.prevalidations:
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
            logger.info("Filter unset")
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

    def toggle_prevalidations(self):
        config.enable_prevalidations = self.enable_prevalidations.get()

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
        # Clear lookahead section widgets
        if hasattr(self, 'lookaheads_title'):
            self.lookaheads_title.destroy()
        if hasattr(self, 'lookahead_frame'):
            self.lookahead_frame.destroy()
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
        # Re-add lookahead section after prevalidations
        self.add_lookahead_management_section()
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


