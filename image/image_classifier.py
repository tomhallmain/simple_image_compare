import os

import numpy as np
from PIL import Image

from utils.logging_setup import get_logger

logger = get_logger("image_classifier")


class H5ImageClassifier:
    def __init__(self, model_path, custom_objects=None):
        """Image classifier for H5 models with version-independent loading
        
        Args:
            model_path: Path to .h5 model file
            custom_objects: Dictionary of custom layer classes {name: class}
        """
        self.is_loaded = False
        self.model = self._load_model(model_path, custom_objects or {})
        if self.is_loaded:
            self.input_shape = self._get_input_shape()
            self._verify_model_compatibility()

    def _load_model(self, model_path, custom_objects):
        """Load model with fallback strategies"""
        self._register_common_layers(custom_objects)
        
        loaders = [
            self._load_model_tensorflow_keras,
            self._load_model_tf_keras,
            self._load_model_keras
        ]
        
        for loader in loaders:
            model = loader(model_path, custom_objects)
            if model is not None:
                self.is_loaded = True
                return model

        logger.error(f"Failed to load model at {model_path}")
        return None

    def _register_common_layers(self, custom_objects):
        """Auto-register common custom layers"""
        try:
            import tensorflow_hub as hub
            custom_objects['KerasLayer'] = hub.KerasLayer
        except ImportError:
            pass

    def _load_model_tensorflow_keras(self, model_path, custom_objects):
        """Attempt loading with TensorFlow's built-in Keras"""
        try:
            from tensorflow.keras.models import load_model as tf_load_model
            from tensorflow.keras.utils import custom_object_scope
            with custom_object_scope(custom_objects):
                logger.info("Attempting TensorFlow Keras load...")
                return tf_load_model(model_path)
        except Exception as e:
            logger.error(f"TensorFlow Keras load failed: {str(e)[:200]}")
            return None

    def _load_model_tf_keras(self, model_path, custom_objects):
        """Fallback to tf_keras package"""
        try:
            from tf_keras.models import load_model
            logger.info("Attempting tf_keras load...")
            return load_model(model_path, custom_objects=custom_objects)
        except Exception as e:
            logger.error(f"tf_keras load failed: {str(e)[:200]}")
            return None

    def _load_model_keras(self, model_path, custom_objects):
        """Last-resort standalone Keras attempt"""
        try:
            from keras.models import load_model as keras_load_model
            from keras.utils.custom_object_scope import custom_object_scope
            with custom_object_scope(custom_objects):
                logger.info("Attempting standalone Keras load...")
                return keras_load_model(model_path)
        except Exception as e:
            logger.error(f"Standalone Keras load failed: {str(e)[:200]}")
            return None

    def _get_input_shape(self):
        """Get input dimensions with channels-last/channels-first awareness"""
        input_shape = self.model.input_shape
        if isinstance(input_shape, list):
            input_shape = input_shape[0]
            
        # Handle different data formats
        if len(input_shape) == 4:  # Batch dimension included
            _, height, width, _ = input_shape
        else:
            height, width, _ = input_shape
        return (width, height)  # PIL uses (width, height) for resize

    def _verify_model_compatibility(self):
        """Check for common compatibility issues"""
        if not hasattr(self.model, 'predict'):
            raise ValueError("Loaded model doesn't support prediction interface")
        if len(self.input_shape) != 2:
            raise ValueError("Model expects unexpected input dimensions")

    def preprocess_image(self, image_path):
        """Preprocess image with safety checks"""
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                img = img.resize(self.input_shape)
                img_array = np.array(img, dtype=np.float32) / 255.0
                return np.expand_dims(img_array, axis=0)
        except Exception as e:
            raise ValueError(f"Image processing failed: {str(e)}")

    def predict(self, preprocessed_image, batch_size=32):
        """Run prediction with validation"""
        assert self.model is not None
        if preprocessed_image.shape[1:3] != self.input_shape[::-1]:
            raise ValueError("Input image dimensions don't match model requirements")
        return self.model.predict(preprocessed_image, batch_size=batch_size)

    def predict_image(self, image_path):
        """Run prediction with validation"""
        preprocessed_img = self.preprocess_image(image_path)
        return self.predict(preprocessed_img)



class ImageClassifierWrapper:
    def __init__(self, model_name="", model_categories=["drawing", "photograph"],
                 model_location="", use_hub_keras_layers=False):
        self.model_name = model_name
        self.model_categories = model_categories
        self.model_location = model_location
        self.use_hub_keras_layers = use_hub_keras_layers
        self.can_run = True
        self.h5_classifier = None
        self.predictions_cache = {}
        if self.can_run:
            try:
                self.model_name = str(self.model_name).strip()
                if self.model_name is None or self.model_name == "":
                    raise Exception("Invalid model name: " + self.model_name)
                if not type(self.model_categories) == list or len(self.model_categories) == 0 \
                        or any([type(c) != str for c in self.model_categories]):
                    raise Exception(f"Invalid model categories: {self.model_categories}")
                if not type(self.model_location) == str or not os.path.isfile(self.model_location):
                    raise Exception(f"Invalid model location: {self.model_location}")
                if not type(self.use_hub_keras_layers) == bool:
                    raise Exception(f"Invalid use hub keras layers flag, must be boolean:  {self.use_hub_keras_layers}")
            except Exception as e:
                self.can_run = False
                logger.error(e)
                logger.warning("Failed to set model details for image classifier: " + str(self.__dict__))
            if self.can_run:
                self.load_classifier()

    def load_classifier(self):
        assert self.can_run is True
        custom_objects = {}
        if self.use_hub_keras_layers:
            try:
                import tensorflow_hub as hub
                custom_objects['KerasLayer'] = hub.KerasLayer
            except ImportError:
                logger.error("Failed to import tensorflow hub to support h5 model, please install it using pip")
                self.can_run = False
        if self.can_run:
            try:
                self.h5_classifier = H5ImageClassifier(
                    self.model_location,
                    custom_objects=custom_objects,
                )
                self.can_run = bool(self.h5_classifier.is_loaded)
            except Exception as e:
                self.can_run = False
                logger.error(e)
                logger.warning("Failed to initialize model for image classifier: " + self.model_name)

    def predict_image(self, image_path):
        if image_path in self.predictions_cache:
            return self.predictions_cache[image_path]
        assert self.h5_classifier is not None
        # img = image.load_img(image_path, target_size=(self.target_image_dim, self.target_image_dim))
        # y = image.img_to_array(img)
        # y /= self.image_array_divisor
        # images = np.asarray([y])
        predictions = self.h5_classifier.predict_image(image_path)
        classed_predictions = {}
        for i in range(len(self.model_categories)):
            classed_predictions[self.model_categories[i]] = float(predictions[0][i])
        self.predictions_cache[image_path] = dict(classed_predictions)
        # logger.debug(classed_predictions)
        return classed_predictions

    def classify_image(self, image_path):
        if not self.can_run:
            raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")
        classed_predictions = self.predict_image(image_path)
        keys = list(self.model_categories)
        keys.sort(key=lambda c: classed_predictions[c], reverse=True)
        classed_category = keys[0]
        return classed_category

    def test_image_for_categories(self, image_path, categories):
        if not self.can_run:
            raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")
        category = self.classify_image(image_path)
        return category in categories

    def test_image_for_category(self, image_path, category, threshold):
        if self.can_run:
            return self.predict_image(image_path)[category] > threshold
        raise Exception(f"Invalid state: Image classifier details failed to initialize, unable to classify image")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.model_name}', categories={self.model_categories})"

    def __hash__(self) -> int:
        return hash(self.model_name)
    
    def __eq__(self, other):
        if not isinstance(other, ImageClassifierWrapper):
            raise TypeError(f"Invalid type for comparison: {type(other)}")
        return self.model_name == other.model_name
