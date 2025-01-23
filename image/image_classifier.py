
import os

from utils.config import config
from utils.utils import Utils

imports_successful = False

try:
    import tensorflow as tf ## NOTE requires tensorflow version < 3
    import tensorflow_hub as hub
    import keras.utils as image
    import numpy as np
    imports_successful = True
except ImportError as e:
    Utils.log_yellow(e)
    Utils.log_yellow("Failed to import packages for image classifier models!")


DEFAULT_MODEL_DETAILS = {
    "model_name": "",
    "model_categories": ["drawing", "photograph"],
    "model_location": "",
    "target_image_dim": 224,   # required/default image dimensionality
    "image_array_divisor": 255,
}

class ImageClassifier:
    def __init__(self, model_details=DEFAULT_MODEL_DETAILS):
        self.model_name = DEFAULT_MODEL_DETAILS["model_name"]
        self.model_categories = DEFAULT_MODEL_DETAILS["model_categories"]
        self.model_location = DEFAULT_MODEL_DETAILS["model_location"]
        self.target_image_dim = DEFAULT_MODEL_DETAILS["target_image_dim"]
        self.image_array_divisor = DEFAULT_MODEL_DETAILS["image_array_divisor"]
        self.__dict__ = dict(model_details)
        self.can_run = imports_successful
        self.model = None
        self.predictions_cache = {}
        if self.can_run:
            try:
                self.model_name = str(self.model_name).strip()
                if self.model_name == "None" or self.model_name == "":
                    raise Exception("Invalid model name: " + self.model_name)
                if not type(self.model_categories) == list or len(self.model_categories) == 0 \
                        or any([type(c) != str for c in self.model_categories]):
                    raise Exception(f"Invalid model categories: {self.model_categories}")
                if not type(self.model_location) == str or not os.path.isfile(self.model_location):
                    raise Exception(f"Invalid model location: {self.model_location}")
                if not type(self.target_image_dim) == int or self.target_image_dim <= 0:
                    raise Exception(f"Invalid target image dimension, must be positive integer: {self.target_image_dim}")
                if not type(self.image_array_divisor) == int or self.image_array_divisor <= 0:
                    raise Exception(f"Invalid image array divisor, must be positive integer: {self.image_array_divisor}")
            except Exception as e:
                self.can_run = False
                Utils.log_red(e)
                Utils.log_yellow("Failed to set model details for image classifier: " + str(model_details))
            try:
                self.model = tf.keras.models.load_model(self.model_location, custom_objects={'KerasLayer': hub.KerasLayer})
            except Exception as e:
                self.can_run = False
                Utils.log_red(e)
                Utils.log_yellow("Failed to initialize model for image classifier: " + self.model_name)

    def predict_image(self, image_path):
        if image_path in self.predictions_cache:
            return self.predictions_cache[image_path]
        assert self.model is not None
        img = image.load_img(image_path, target_size=(self.target_image_dim, self.target_image_dim))
        y = image.img_to_array(img)
        y /= self.image_array_divisor
        images = np.asarray([y])
        predictions = self.model.predict(images)
        classed_predictions = {}
        for i in range(len(self.model_categories)):
            classed_predictions[self.model_categories[i]] = float(predictions[0][i])
        self.predictions_cache[image_path] = list(classed_predictions)
        return classed_predictions

    def classify_image(self, image_path):
        if not self.can_run:
            raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")
        classed_predictions = self.predict_image(image_path)
        keys = list(self.model_categories)
        keys.sort(key=lambda c: classed_predictions[c], reverse=True)
        classed_category = keys[0]
        if not classed_category in self.model_categories:
            raise Exception(f"Failed to find matching model category for predicted category: \"{classed_category}\""
                            f"\nCategories expected: {self.model_categories}")
        return classed_category

    def test_image_for_category(self, image_path, category, threshold):
        if not self.can_run:
            raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")
        return self.predict_image(image_path)[category] > threshold


class ImageClassifierManager:
    def __init__(self):
        self.classifiers = {}
        if type(config.image_classifier_h5_models) == list:
            for model_details in config.image_classifier_h5_models:
                classifier = ImageClassifier(model_details)
                if classifier.can_run:
                    self.classifiers[classifier.model_name] = classifier

    def can_classify(self):
        return len(self.classifiers) > 0

    def classify_image(self, model_name, image_path):
        try:
            return self.classifiers[model_name].classify_image(image_path)
        except KeyError:
            if not model_name in self.classifiers:
                classifier_model_names = list(self.classifiers.keys())
                raise Exception(f"Image classifier model name not found: {model_name}\n"
                                f"Valid classifier model names: {classifier_model_names}")

    def add_classifier(self, image_classifier):
        if type(image_classifier) != ImageClassifier:
            raise Exception(f"Invalid image classifier argument: {image_classifier}")
        self.classifiers[image_classifier.model_name] = image_classifier

    def get_classifier(self, model_name):
        if model_name is None or model_name.strip() == "":
            return None
        try:
            return self.classifiers[model_name]
        except Exception as e:
            raise Exception(f"Failed to find image classifier with model name: \"{model_name}\"")

    def get_model_names(self):
        return list(self.classifiers.keys())


image_classifier_manager = ImageClassifierManager()





