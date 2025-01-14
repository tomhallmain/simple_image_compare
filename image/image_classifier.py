
import os

from utils.config import config
from utils.utils import Utils

imports_successful = False

try:
    import tensorflow as tf ## NOTE requires tensorflow version < 3
    import tensorflow_hub as hub
    import keras.utils as image
    import numpy as np
except ImportError as e:
    Utils.log_yellow(e)
    Utils.log_yellow("Failed to import packages for image classifier models!")
    imports_successful = True


DEFAULT_IMAGE_DIM = 224   # required/default image dimensionality
MODEL_LOC = r"C:\Users\tehal\nsfw_model\trained_models\mobilenet_v2_140_224\saved_model.h5"
categories = ['drawings', 'hentai', 'neutral', 'porn', 'sexy']

DEFAULT_MODEL_DETAILS = {
    "model_name": "",
    "model_categories": ["drawing", "photograph"],
    "model_location": "",
    "target_image_dim": 224,
    "image_array_divisor": 255,
}

class ImageClassifier:
    def __init__(self, model_details=DEFAULT_MODEL_DETAILS):
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
                        or any(lambda c: type(c) != str, self.model_categories):
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
                self.model = tf.keras.models.load_model(self.model_loc, custom_objects={'KerasLayer': hub.KerasLayer})
            except Exception as e:
                self.can_run = False
                Utils.log_red(e)
                Utils.log_yellow("Failed to initialize model for image classifier: " + self.model_name)

    def predict_image(image_path):
        if image_path in self.predictions_cache:
            return self.predictions_cache[image_path]
        img = image.load_img(image_path, target_size=(self.target_image_dim, target_image_dim))
        y = image.img_to_array(img)
        y /= self.image_array_divisor
        images = np.asarray([y])
        predictions = self.model.predict(images)
        classed_predictions = {}
        for i in range(5):
            classed_predictions[categories[i]] = float(predictions[0][i])
        self.predictions_cache[image_path] = list(classed_predictions)
        return classed_predictions

    def classify_image(image_path):
        if not self.can_run:
            raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")
        classed_predictions = predict_image(model, image_path)
        keys = list(categories)
        keys.sort(key=lambda c: classed_predictions[c], reverse=True)
        classed_category = keys[0]
        if not classed_category in self.model_categories:
            raise Exception(f"Failed to find matching model category for predicted category: \"{classed_category}\""
                            f"\nCategories expected: {self.model_categories}")
        return classed_category

    def test_image_for_category(image_path, category, threshold):
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

    def get_model_names(self):
        return list(self.classifiers.keys())


image_classifier_manager = ImageClassifierManager()





