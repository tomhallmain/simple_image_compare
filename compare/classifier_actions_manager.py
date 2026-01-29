"""
Classification Actions Manager module for managing prevalidations, classifier actions, and directory profiles.

This module centralizes the management of:
- Prevalidations list
- Classifier actions list  
- Directory profiles and their usage tracking
"""

from enum import Enum
import os
import threading
from typing import List, Optional

from compare.compare_embeddings_clip import CompareEmbeddingClip
from compare.directory_profile import DirectoryProfile
from compare.embedding_prototype import EmbeddingPrototype
from compare.lookahead import Lookahead
from files.file_actions_window import FileActionsWindow
from image.image_classifier_manager import image_classifier_manager
from image.image_data_extractor import image_data_extractor
from image.image_ops import ImageOps
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.constants import ActionType, ClassifierActionType
from utils.logging_setup import get_logger
from utils.running_tasks_registry import start_thread
from utils.translations import I18N
from utils.utils import Utils



_ = I18N._

logger = get_logger("classifier_actions_manager")





class ClassifierAction:
    NO_POSITIVES_STR = _("(no positives set)")
    NO_NEGATIVES_STR = _("(no negatives set)")

    def __init__(self, name=_("New Classifier Action"), positives=[], negatives=[], threshold=0.23,
                 text_embedding_threshold=None, prototype_threshold=0.23,
                 action=ClassifierActionType.NOTIFY, action_modifier="",
                 image_classifier_name="", image_classifier_selected_categories=[], 
                 use_embedding=True, use_image_classifier=False, use_prompts=False, use_blacklist=False,
                 is_active=True, use_prototype=False, prototype_directory="", 
                 negative_prototype_directory="", negative_prototype_lambda=0.5,
                 _last_used_profile=None, lookahead_names=[]):
        self.name = name
        self.positives = positives
        self.negatives = negatives
        # Backward compatibility: if text_embedding_threshold is None, use threshold
        self.text_embedding_threshold = text_embedding_threshold if text_embedding_threshold is not None else threshold
        self.prototype_threshold = prototype_threshold
        # Keep threshold for backward compatibility (maps to text_embedding_threshold)
        self.threshold = self.text_embedding_threshold
        self.action = action if isinstance(action, Enum) else ClassifierActionType[action]
        self.action_modifier = action_modifier  # Target directory for MOVE/COPY actions
        self.is_active = is_active  # Whether this action is enabled/active
        self.image_classifier_name = image_classifier_name
        self.image_classifier = None
        self.image_classifier_categories = []
        self.image_classifier_selected_categories = image_classifier_selected_categories
        self.lookahead_names = lookahead_names if lookahead_names else []  # List of lookahead names (strings)
        self.use_embedding = use_embedding
        self.use_image_classifier = use_image_classifier
        self.use_prompts = use_prompts
        self.use_blacklist = use_blacklist
        self.use_prototype = use_prototype  # Whether to use embedding prototype
        self.prototype_directory = prototype_directory  # Directory containing sample images for positive prototype
        self.negative_prototype_directory = negative_prototype_directory  # Directory containing sample images for negative prototype
        self.negative_prototype_lambda = negative_prototype_lambda  # Weight for negative prototype (λ)
        self._cached_prototype = None  # Cached positive prototype embedding
        self._cached_negative_prototype = None  # Cached negative prototype embedding
        self._last_used_profile = _last_used_profile  # Last used profile name or directory path (None for new actions)


    def __eq__(self, other):
        """Check equality based on name (classifier actions are uniquely identified by name)."""
        if not isinstance(other, ClassifierAction):
            return False
        return self.name == other.name

    def __hash__(self):
        """Hash based on name (classifier actions are uniquely identified by name)."""
        return hash(self.name)

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
            return ClassifierAction.NO_POSITIVES_STR

    def set_image_classifier(self, classifier_name):
        self.image_classifier_name = classifier_name
        self.image_classifier = image_classifier_manager.get_classifier(classifier_name)
        self.image_classifier_categories = []
        if self.image_classifier is not None:
            self.image_classifier_categories.extend(list(self.image_classifier.model_categories))

    def ensure_image_classifier_loaded(self, notify_callback):
        """Lazy load the image classifier if it hasn't been loaded yet."""
        if self.image_classifier is None and self.image_classifier_name:
            try:
                if notify_callback is not None:
                    notify_callback(_("Loading image classifier <{0}> ...").format(self.image_classifier_name))
                self.set_image_classifier(self.image_classifier_name)
            except Exception as e:
                import traceback
                logger.error(traceback.format_exc())
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
            lookahead = Lookahead.get_lookahead_by_name(lookahead_name)
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
                lookahead_prevalidation = ClassifierActionsManager.get_prevalidation_by_name(name_or_text)
                if lookahead_prevalidation is None:
                    # Prevalidation not found, skip this lookahead
                    lookahead.run_result = False  # Cache the result
                    continue
                # Use the lookahead prevalidation's positives/negatives
                positives = lookahead_prevalidation.positives
                negatives = lookahead_prevalidation.negatives
                # Skip if the referenced prevalidation has no positives or negatives
                if not positives and not negatives:
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
                # logger.info(f"Lookahead {lookahead_name} triggered for prevalidation {self.name}")
                return True
        
        return False

    def ensure_prototype_loaded(self, notify_callback, force_recalculate=False):
        """Lazy load the prototype embeddings if needed."""
        if not self.use_prototype or not self.prototype_directory:
            return
        
        # Load positive prototype
        if self._cached_prototype is None or force_recalculate:
            try:
                if notify_callback is not None:
                    notify_callback(_("Loading embedding prototype from {0}...").format(self.prototype_directory))
                self._cached_prototype = EmbeddingPrototype.calculate_prototype_from_directory(
                    self.prototype_directory,
                    force_recalculate=force_recalculate,
                    notify_callback=notify_callback
                )
                if self._cached_prototype is None:
                    logger.error(f"Failed to load prototype from {self.prototype_directory}")
            except Exception as e:
                logger.error(f"Error loading prototype from {self.prototype_directory}: {e}")
                self._cached_prototype = None
        
        # Load negative prototype if specified
        if self.negative_prototype_directory and (self._cached_negative_prototype is None or force_recalculate):
            try:
                if notify_callback is not None:
                    notify_callback(_("Loading negative embedding prototype from {0}...").format(self.negative_prototype_directory))
                self._cached_negative_prototype = EmbeddingPrototype.calculate_prototype_from_directory(
                    self.negative_prototype_directory,
                    force_recalculate=force_recalculate,
                    notify_callback=notify_callback
                )
                if self._cached_negative_prototype is None:
                    logger.error(f"Failed to load negative prototype from {self.negative_prototype_directory}")
            except Exception as e:
                logger.error(f"Error loading negative prototype from {self.negative_prototype_directory}: {e}")
                self._cached_negative_prototype = None
    
    def _check_prototype_validation(self, image_path):
        """Check if image matches the prototype embedding.
        
        Uses formula: Final Score = sim(query, positive_proto) - λ * sim(query, negative_proto)
        If negative prototype is not set, uses only positive similarity.
        """
        if not self.use_prototype or self._cached_prototype is None:
            return False
        
        try:
            # Use ClassifierAction name as session_cache_key for efficient result caching
            # Calculate similarity to positive prototype (prototype_type=0)
            positive_similarity = EmbeddingPrototype.compare_with_prototype(
                image_path, self._cached_prototype, session_cache_key=self.name
            )
            if config.debug2:
                logger.info(self.name + " Positive similarity: " + str(positive_similarity))
            # If negative prototype is set, subtract weighted negative similarity (prototype_type=1)
            if self._cached_negative_prototype is not None:
                negative_similarity = EmbeddingPrototype.compare_with_prototype(
                    image_path, self._cached_negative_prototype, session_cache_key=self.name, negative_prototype=1
                )
                if config.debug2:
                    logger.info(self.name + " Negative similarity: " + str(negative_similarity))
                final_score = positive_similarity - self.negative_prototype_lambda * negative_similarity
                if config.debug2:
                    logger.info(self.name + " Final score: " + str(final_score))
            else:
                final_score = positive_similarity
                if config.debug2:
                    logger.info(self.name + " Final score: " + str(final_score))
            return final_score >= self.prototype_threshold
        except Exception as e:
            logger.error(f"Error checking prototype validation for {image_path}: {e}")
            return False
    
    def _run_with_batch_prototype_validation(self, directory_paths: list[str], hide_callback, notify_callback, add_mark_callback=None, max_images_per_batch: Optional[int] = None):
        """
        Run classifier action with batch prototype validation for efficiency.
        
        Delegates batch processing to EmbeddingPrototype, then runs actions on matching images.
        Runs the entire process (batch validation + action execution) in a separate thread.
        
        Args:
            directory_paths: List of directory paths to process
            hide_callback: Callback for hiding images
            notify_callback: Callback for notifications
            add_mark_callback: Optional callback for marking images
            max_images_per_batch: Optional maximum number of images to process per batch
        """
        if not self.use_prototype or self._cached_prototype is None:
            return
        
        def batch_validation_worker():
            """Worker function to run batch validation and actions in a separate thread."""
            try:
                # Use EmbeddingPrototype to batch validate images from directories
                matching_paths = EmbeddingPrototype.batch_validate_with_prototypes(
                    directories=directory_paths,
                    positive_prototype=self._cached_prototype,
                    threshold=self.prototype_threshold,
                    negative_prototype=self._cached_negative_prototype,
                    negative_lambda=self.negative_prototype_lambda,
                    notify_callback=notify_callback,
                    max_images_per_batch=max_images_per_batch
                )
                
                # Run actions on matching images
                for image_path in matching_paths:
                    try:
                        self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
                    except Exception as e:
                        logger.error(f"Error running action on {image_path}: {e}")
            except Exception as e:
                logger.error(f"Error in batch prototype validation: {e}")
        
        # Start batch validation and action execution in a separate thread
        start_thread(batch_validation_worker, use_asyncio=False)

    def run(self, directory_paths: list[str], hide_callback, notify_callback, add_mark_callback=None, profile_name_or_path: Optional[str] = None, max_images_per_batch: Optional[int] = None):
        """Run the classifier action on the given directory paths.
        
        Args:
            directory_paths: List of directory paths to process
            hide_callback: Callback for hiding images
            notify_callback: Callback for notifications
            add_mark_callback: Optional callback for marking images
            profile_name_or_path: Optional profile name or directory path to store as last used
            max_images_per_batch: Optional maximum number of images to process per batch
        """
        if not self.is_active:
            logger.info(f"Classifier action {self.name} is disabled, skipping")
            return
        
        # Store the last used profile or directory path
        if profile_name_or_path:
            self._last_used_profile = profile_name_or_path
        elif directory_paths:
            # If no profile name provided, use the first directory path
            self._last_used_profile = directory_paths[0]

        logger.info(f"Running classifier action {self.name} on {len(directory_paths)} directories")
        
        # Pre-load image classifier and prototype before processing images
        self.ensure_image_classifier_loaded(notify_callback)
        self.ensure_prototype_loaded(notify_callback)
        
        # Use batch prototype validation when prototype validation is enabled
        if self.use_prototype:
            self._run_with_batch_prototype_validation(directory_paths, hide_callback, notify_callback, add_mark_callback, max_images_per_batch)

    def run_on_image_path(self, image_path, hide_callback, notify_callback, add_mark_callback=None) -> Optional[ClassifierActionType]:
        # Note: Image classifier and prototype should be loaded before calling this method
        # (see ClassifierActionsWindow.run_classifier_action for pre-loading)
        
        # Check each enabled validation type with short-circuit OR logic        
        if self.use_prototype:
            if self._check_prototype_validation(image_path):
                return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)

        # Check lookaheads first - if any pass, skip this prevalidation
        if self._check_lookaheads(image_path):
            return None

        if self.use_embedding:
            if CompareEmbeddingClip.multi_text_compare(image_path, self.positives, self.negatives, self.text_embedding_threshold):
                return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
        
        if self.use_image_classifier:
            if self.image_classifier is not None:
                if self.image_classifier.test_image_for_categories(image_path, self.image_classifier_selected_categories):
                    return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
            else:
                logger.error(f"Image classifier {self.image_classifier_name} not found for classifier action {self.name}")
        
        if self.use_prompts:
            if self._check_prompt_validation(image_path):
                return self.run_action(image_path, hide_callback, notify_callback, add_mark_callback)
        
        # No validation type passed
        return None

    def run_action(self, image_path, hide_callback, notify_callback, add_mark_callback=None):
        base_message = self.name + _(" detected")
        if self.action == ClassifierActionType.SKIP:
            notify_callback("\n" + base_message + _(" - skipped"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == ClassifierActionType.HIDE:
            hide_callback(image_path)
            notify_callback("\n" + base_message + _(" - hidden"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == ClassifierActionType.NOTIFY:
            notify_callback("\n" + base_message, base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == ClassifierActionType.ADD_MARK:
            add_mark_callback(image_path)
            notify_callback("\n" + base_message + _(" - marked"), base_message=base_message, action_type=ActionType.SYSTEM, is_manual=False)
        elif self.action == ClassifierActionType.MOVE or self.action == ClassifierActionType.COPY:
            if self.action_modifier is not None and len(self.action_modifier) > 0:
                if not os.path.exists(self.action_modifier):
                    raise Exception("Invalid move target directory for classifier action " + self.name + ": " + self.action_modifier)
                if os.path.normpath(os.path.dirname(image_path)) != os.path.normpath(self.action_modifier):
                    action_modifier_name = Utils.get_relative_dirpath(self.action_modifier, levels=2)
                    action_type = ActionType.MOVE_FILE if self.action == ClassifierActionType.MOVE else ActionType.COPY_FILE
                    specific_message = _("Moving file: ") + os.path.basename(image_path) + " -> " + action_modifier_name
                    notify_callback("\n" + specific_message, base_message=base_message,
                                    action_type=action_type, is_manual=False)
                    try:
                        FileActionsWindow.add_file_action(
                            Utils.move_file if self.action == ClassifierActionType.MOVE else Utils.copy_file,
                            image_path, self.action_modifier
                        )
                    except Exception as e:
                        if (self.action == ClassifierActionType.MOVE and
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
                                        Utils.move_file if self.action == ClassifierActionType.MOVE else Utils.copy_file,
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
                raise Exception("Target directory not defined on classifier action "  + self.name)
        elif self.action == ClassifierActionType.DELETE:
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
            return ClassifierAction.NO_NEGATIVES_STR

    def validate(self):
        if self.name is None or len(self.name) == 0:
            raise Exception('Classifier action name is None or empty')
        
        # Check if at least one validation type is enabled
        if not (self.use_embedding or self.use_image_classifier or self.use_prompts or self.use_blacklist or self.use_prototype):
            raise Exception("At least one validation type (embedding, image classifier, prompts, prompts blacklist, or prototype) must be enabled.")
        
        # Validate prototype settings if enabled
        if self.use_prototype:
            if not self.prototype_directory or not self.prototype_directory.strip():
                raise Exception("Prototype directory must be set when using prototype validation.")
            if not os.path.isdir(self.prototype_directory):
                raise Exception(f"Prototype directory does not exist: {self.prototype_directory}")
            # Validate negative prototype directory if set
            if self.negative_prototype_directory and self.negative_prototype_directory.strip():
                if not os.path.isdir(self.negative_prototype_directory):
                    raise Exception(f"Negative prototype directory does not exist: {self.negative_prototype_directory}")
        
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
        if len(errors) > 0:
            logger.error(_("Invalid classifier action {0}, may cause errors or be unable to run!").format(self.name))
            for error in errors:
                logger.warning(error)

    def is_move_action(self):
        return self.action == ClassifierActionType.MOVE or self.action == ClassifierActionType.COPY

    def move_index(self, idx, direction_count=1):
        """Move a classifier action in the list by the specified number of positions.
        
        Args:
            idx: Current index of the classifier action to move
            direction_count: Positive to move down (higher index), negative to move up (lower index)
        """
        classifier_actions = ClassifierActionsManager.classifier_actions
        ClassifierAction.do_move_index(idx, classifier_actions, direction_count)
    
    @staticmethod
    def do_move_index(idx, classifier_actions, direction_count=1):
        list_len = len(classifier_actions)
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
        move_item = classifier_actions.pop(idx)
        classifier_actions.insert(target_idx, move_item)

    def to_dict(self):
        return {
            "name": self.name,
            "positives": self.positives,
            "negatives": self.negatives,
            "threshold": self.text_embedding_threshold,  # Keep for backward compatibility
            "text_embedding_threshold": self.text_embedding_threshold,
            "prototype_threshold": self.prototype_threshold,
            "action": self.action.value,
            "action_modifier": self.action_modifier,
            "is_active": self.is_active,
            "image_classifier_name": self.image_classifier_name,
            "image_classifier_selected_categories": self.image_classifier_selected_categories,
            "use_embedding": self.use_embedding,
            "use_image_classifier": self.use_image_classifier,
            "use_prompts": self.use_prompts,
            "use_blacklist": self.use_blacklist,
            "use_prototype": self.use_prototype,
            "prototype_directory": self.prototype_directory,
            "negative_prototype_directory": self.negative_prototype_directory,
            "negative_prototype_lambda": self.negative_prototype_lambda,
            "_last_used_profile": self._last_used_profile,
            "lookahead_names": self.lookahead_names,
            }

    @staticmethod
    def from_dict(d):
        # Handle backward compatibility - detect original type based on data presence
        if 'use_embedding' not in d:
            # If image_classifier_name is set, it was an image classifier action
            if 'image_classifier_name' in d and d['image_classifier_name'] and d['image_classifier_name'].strip():
                d['use_embedding'] = False
                d['use_image_classifier'] = True
            else:
                # Otherwise it was an embedding action
                d['use_embedding'] = True
                d['use_image_classifier'] = False
        if 'use_image_classifier' not in d:
            d['use_image_classifier'] = False
        if 'lookahead_names' not in d:
            d['lookahead_names'] = []
        if 'use_prompts' not in d:
            d['use_prompts'] = False
        if 'use_blacklist' not in d:
            d['use_blacklist'] = False
        if 'is_active' not in d:
            d['is_active'] = True
        if 'use_prototype' not in d:
            d['use_prototype'] = False
        if 'prototype_directory' not in d:
            d['prototype_directory'] = ""
        if 'negative_prototype_directory' not in d:
            d['negative_prototype_directory'] = ""
        if 'negative_prototype_lambda' not in d:
            d['negative_prototype_lambda'] = 0.5
        if '_last_used_profile' not in d:
            d['_last_used_profile'] = None
        # Handle threshold backward compatibility
        if 'text_embedding_threshold' not in d:
            # Use existing threshold as text_embedding_threshold
            d['text_embedding_threshold'] = d.get('threshold', 0.23)
        if 'prototype_threshold' not in d:
            # Use existing threshold as prototype_threshold for backward compatibility
            d['prototype_threshold'] = d.get('threshold', 0.23)
        
        return ClassifierAction(**d)

    def __str__(self) -> str:
        out = self.name
        validation_types = []
        if self.use_embedding:
            validation_types.append(_("embedding"))
        if self.use_image_classifier and self.image_classifier_name and self.image_classifier_name.strip():
            validation_types.append(_("classifier {0}").format(self.image_classifier_name))
        if self.use_prompts:
            validation_types.append(_("prompts"))
        if self.use_prototype:
            validation_types.append(_("prototype"))
        
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

        if not self.is_active:
            out += " [" + _("disabled") + "]"
        
        return out



class Prevalidation(ClassifierAction):
    def __init__(self, name=_("New Prevalidation"), positives=[], negatives=[], threshold=0.23,
                 text_embedding_threshold=None, prototype_threshold=0.23,
                 action=ClassifierActionType.NOTIFY, action_modifier="", run_on_folder=None, is_active=True,
                 image_classifier_name="", image_classifier_selected_categories=[], 
                 use_embedding=True, use_image_classifier=False, use_prompts=False, use_blacklist=False,
                 lookahead_names=[], profile_name=None, use_prototype=False, prototype_directory="", 
                 negative_prototype_directory="", negative_prototype_lambda=0.5, _last_used_profile=None):
        # Pass all parameters including prototype settings to parent ClassifierAction
        super().__init__(name, positives, negatives, threshold, 
                        text_embedding_threshold, prototype_threshold, action, action_modifier, 
                        image_classifier_name, image_classifier_selected_categories,
                        use_embedding, use_image_classifier, use_prompts, use_blacklist,
                        is_active, use_prototype, prototype_directory,
                        negative_prototype_directory, negative_prototype_lambda,
                        _last_used_profile, lookahead_names=lookahead_names)
        self.profile_name = profile_name  # Name of DirectoryProfile to use (None = global)
        self.profile = None  # Cached DirectoryProfile instance (set after loading, or temporary for backward compatibility)
        # Note: run_on_folder parameter is kept for backward compatibility in from_dict but not stored as instance variable

    def __eq__(self, other):
        """Check equality based on name (prevalidations are uniquely identified by name)."""
        if not isinstance(other, Prevalidation):
            return False
        return self.name == other.name

    def __hash__(self):
        """Hash based on name (prevalidations are uniquely identified by name)."""
        return hash(self.name)

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
            # Profile may be cached
            self.profile = DirectoryProfile.get_profile_by_name(self.profile_name)
            
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
                    DirectoryProfile.directory_profiles.append(temp_profile)
                    logger.info(f"Created temporary DirectoryProfile for backward compatibility: name='{self.profile_name}', prevalidation='{self.name}'")
                    self.profile = temp_profile
                else:
                    # Profile not found and not creating
                    logger.warning(f"Profile {self.profile_name} not found for prevalidation {self.name}")
                    self.profile = None
        else:
            self.profile = None

    def run_on_image_path(self, image_path, hide_callback, notify_callback, add_mark_callback=None) -> Optional[ClassifierActionType]:
        # Lazy load the image classifier if needed
        super().ensure_image_classifier_loaded(notify_callback)
        return super().run_on_image_path(image_path, hide_callback, notify_callback, add_mark_callback)

    def validate_dirs(self):
        super().validate_dirs()
        # Add prevalidation-specific profile directory validation
        errors = []
        if self.profile is not None:
            for directory in self.profile.directories:
                if not os.path.isdir(directory):
                    errors.append(_("Profile directory is not a valid directory: ") + directory)
        if len(errors) > 0:
            logger.error(_("Invalid prevalidation {0}, may cause errors or be unable to run!").format(self.name))
            for error in errors:
                logger.warning(error)

    def move_index(self, idx, direction_count=1):
        """Move a prevalidation in the list by the specified number of positions.
        
        Args:
            idx: Current index of the prevalidation to move
            direction_count: Positive to move down (higher index), negative to move up (lower index)
        """
        prevalidations = ClassifierActionsManager.prevalidations
        ClassifierAction.do_move_index(idx, prevalidations, direction_count)

    def to_dict(self):
        d = super().to_dict()
        d.update({
            "profile_name": self.profile_name,
            # is_active is already in parent's dict, no need to duplicate
            # Prototype properties (use_prototype, prototype_directory, negative_prototype_directory, 
            # negative_prototype_lambda) are already in parent's dict, no need to duplicate
            "lookahead_names": self.lookahead_names,
        })
        return d

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
        if 'use_prototype' not in d:
            d['use_prototype'] = False
        if 'prototype_directory' not in d:
            d['prototype_directory'] = ""
        if 'negative_prototype_directory' not in d:
            d['negative_prototype_directory'] = ""
        if 'negative_prototype_lambda' not in d:
            d['negative_prototype_lambda'] = 0.5
        if 'lookahead_names' not in d:
            d['lookahead_names'] = []
        if 'profile_name' not in d:
            d['profile_name'] = None
        if 'is_active' not in d:
            d['is_active'] = True  # Default to active for prevalidations
        # Handle threshold backward compatibility
        if 'text_embedding_threshold' not in d:
            # Use existing threshold as text_embedding_threshold
            d['text_embedding_threshold'] = d.get('threshold', 0.23)
        if 'prototype_threshold' not in d:
            # Use existing threshold as prototype_threshold for backward compatibility
            d['prototype_threshold'] = d.get('threshold', 0.23)
        
        # Handle backward compatibility: if run_on_folder exists but no profile_name, create temporary profile
        run_on_folder = d.get('run_on_folder')
        if run_on_folder and not d.get('profile_name'):
            pv = Prevalidation(**d)
            # Use update_profile_instance to handle profile lookup/creation
            pv.update_profile_instance(profile_name=run_on_folder, directory_path=run_on_folder)
            return pv
        
        return Prevalidation(**d)

    def __str__(self) -> str:
        # Use parent's __str__ implementation and append lookahead info
        out = super().__str__()
        
        if self.lookahead_names:
            out += " <" + _("lookaheads: {0}").format(", ".join(self.lookahead_names)) + ">"
        
        return out



class ClassifierActionsManager:
    """Manages prevalidations, classifier actions, and directory profiles."""
    
    # Lists managed by this module
    prevalidations: List['Prevalidation'] = []
    classifier_actions: List['ClassifierAction'] = []
    prevalidated_cache: dict[str, ClassifierActionType] = {}
    directories_to_exclude: list[str] = []
    _prevalidations_initialized: bool = False

    @staticmethod
    def _prevalidations_post_init():
        """Lazy initialization of prevalidations - called just before first use."""
        if ClassifierActionsManager._prevalidations_initialized:
            return
        temp_prevalidations = ClassifierActionsManager.prevalidations[:]
        for prevalidation in temp_prevalidations:
            try:
                prevalidation.update_profile_instance()
                prevalidation.validate_dirs()
                prevalidation.ensure_prototype_loaded(None)
            except Exception as e:
                logger.error(f"Error initializing prevalidation {prevalidation.name}: {e}")
                # ClassifierActionsManager.prevalidations.remove(prevalidation)
        ClassifierActionsManager._prevalidations_initialized = True
    
    @staticmethod
    def prevalidate(image_path, get_base_dir_func, hide_callback, notify_callback, add_mark_callback) -> Optional[ClassifierActionType]:
        # Lazy initialization - ensure prevalidations are initialized before first use
        if not ClassifierActionsManager._prevalidations_initialized:
            ClassifierActionsManager._prevalidations_post_init()
        
        # Reset lookahead cache for this prevalidate call
        for lookahead in Lookahead.lookaheads:
            lookahead.run_result = None
        
        base_dir = get_base_dir_func()
        if len(ClassifierActionsManager.directories_to_exclude) > 0 and base_dir in ClassifierActionsManager.directories_to_exclude:
            return None
        if image_path not in ClassifierActionsManager.prevalidated_cache:
            prevalidation_action = None
            for prevalidation in ClassifierActionsManager.prevalidations:
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
                ClassifierActionsManager.prevalidated_cache[image_path] = prevalidation_action
        else:
            prevalidation_action = ClassifierActionsManager.prevalidated_cache[image_path]
        return prevalidation_action
    
    @staticmethod
    def get_profile_usage(profile_name: str) -> dict:
        """
        Get information about what's using a profile by checking the actual lists.
        
        Returns:
            Dictionary with keys:
            - 'prevalidations': List of prevalidation names using this profile
            - 'classifier_actions': List of classifier action names that have this profile as their last used profile
        """
        # Check prevalidations list directly
        prevalidation_names = [
            pv.name for pv in ClassifierActionsManager.prevalidations 
            if pv.profile_name == profile_name
        ]
        
        # Check classifier actions for last used profile matching profile name
        classifier_action_names = [
            ca.name for ca in ClassifierActionsManager.classifier_actions
            if ca._last_used_profile and ca._last_used_profile == profile_name
        ]
        
        return {
            'prevalidations': prevalidation_names,
            'classifier_actions': classifier_action_names
        }
    
    @staticmethod
    def can_remove_profile(profile_name: str) -> tuple[bool, List[str]]:
        """
        Check if a profile can be safely removed.
        
        Returns:
            Tuple of (can_remove, warnings)
            - can_remove: True if profile can be removed
            - warnings: List of warning messages
        """
        usage = ClassifierActionsManager.get_profile_usage(profile_name)
        warnings = []
        
        if usage['prevalidations']:
            warnings.append(f"prevalidations: {', '.join(usage['prevalidations'])}")
        
        if usage['classifier_actions']:
            warnings.append(f"classifier actions (last used profile): {', '.join(usage['classifier_actions'])}")
        
        return (len(warnings) == 0, warnings)
    
    @staticmethod
    def remove_profile(profile_name: str) -> bool:
        """
        Remove a profile after checking usage.
        
        Args:
            profile_name: Name of the profile to remove
            
        Returns:
            True if profile was removed, False if removal was prevented
        """
        # Find the profile
        profile = DirectoryProfile.get_profile_by_name(profile_name)
        if profile is None:
            logger.error(f"Profile {profile_name} not found")
            return False
        
        # Check if it can be removed
        can_remove, warnings = ClassifierActionsManager.can_remove_profile(profile_name)
        
        if warnings:
            logger.warning(f"Profile {profile_name} is used by: {', '.join(warnings)}")
            # Still allow removal, but warn the user
        
        # Remove from list
        if profile in DirectoryProfile.directory_profiles:
            DirectoryProfile.directory_profiles.remove(profile)
        
        logger.info(f"Removed profile: {profile_name}")
        return True
    
    @staticmethod
    def get_prevalidation_by_name(name: str) -> 'Prevalidation':
        """Get a prevalidation by name. Returns None if not found."""
        for prevalidation in ClassifierActionsManager.prevalidations:
            if name == prevalidation.name:
                return prevalidation
        return None

    @staticmethod
    def get_classifier_action_by_name(name: str) -> 'ClassifierAction':
        """Get a classifier action by name. Returns None if not found."""
        for classifier_action in ClassifierActionsManager.classifier_actions:
            if name == classifier_action.name:
                return classifier_action
        return None
    
    @staticmethod
    def load_prevalidations():
        """Load prevalidations from cache."""
        # Load lookaheads first
        for lookahead_dict in list(app_info_cache.get_meta("recent_lookaheads", default_val=[])):
            lookahead = Lookahead.from_dict(lookahead_dict)
            # Check if lookahead already exists - if so, use existing one; otherwise add it
            existing = Lookahead.get_lookahead_by_name(lookahead.name)
            if existing is None:
                Lookahead.lookaheads.append(lookahead)
            # If it exists, we silently use the existing lookahead (no error)

        # Load profiles
        for profile_dict in list(app_info_cache.get_meta("recent_profiles", default_val=[])):
            profile = DirectoryProfile.from_dict(profile_dict)
            # Check if profile already exists - if so, use existing one; otherwise add it
            existing = DirectoryProfile.get_profile_by_name(profile.name)
            if existing is None:
                DirectoryProfile.add_profile(profile)
            # If it exists, we silently use the existing profile (no error)

        for prevalidation_dict in list(app_info_cache.get_meta("recent_prevalidations", default_val=[])):
            prevalidation: Prevalidation = Prevalidation.from_dict(prevalidation_dict)
            # Post-init methods (update_profile_instance, validate_dirs, ensure_prototype_loaded)
            # are now called lazily in _ensure_prevalidations_initialized() just before first use
            if prevalidation not in ClassifierActionsManager.prevalidations:
                ClassifierActionsManager.prevalidations.append(prevalidation)

                # Build directories_to_exclude from loaded prevalidations
                if prevalidation.is_move_action() and prevalidation.action_modifier not in ClassifierActionsManager.directories_to_exclude:
                    ClassifierActionsManager.directories_to_exclude.append(prevalidation.action_modifier)

    @staticmethod
    def store_prevalidations():
        """Store prevalidations to cache."""
        # Store lookaheads
        lookahead_dicts = []
        for lookahead in Lookahead.lookaheads:
            lookahead_dicts.append(lookahead.to_dict())
        app_info_cache.set_meta("recent_lookaheads", lookahead_dicts)

        # Store profiles
        profile_dicts = []
        for profile in DirectoryProfile.directory_profiles:
            profile_dicts.append(profile.to_dict())
        app_info_cache.set_meta("recent_profiles", profile_dicts)

        prevalidation_dicts = []
        for prevalidation in ClassifierActionsManager.prevalidations:
            prevalidation_dicts.append(prevalidation.to_dict())
        app_info_cache.set_meta("recent_prevalidations", prevalidation_dicts)
    
    @staticmethod
    def load_classifier_actions():
        """Load classifier actions from cache."""
        for classifier_action_dict in list(app_info_cache.get_meta("recent_classifier_actions", default_val=[])):
            classifier_action: ClassifierAction = ClassifierAction.from_dict(classifier_action_dict)
            classifier_action.validate_dirs()
            if classifier_action not in ClassifierActionsManager.classifier_actions:
                ClassifierActionsManager.classifier_actions.append(classifier_action)
    
    @staticmethod
    def store_classifier_actions():
        """Store classifier actions to cache."""
        classifier_action_dicts = []
        for classifier_action in ClassifierActionsManager.classifier_actions:
            classifier_action_dicts.append(classifier_action.to_dict())
        app_info_cache.set_meta("recent_classifier_actions", classifier_action_dicts)

