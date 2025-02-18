
from image.image_classifier import ImageClassifierWrapper
from utils.config import config


class ImageClassifierManager:
    def __init__(self):
        self.classifiers = {}
        if type(config.image_classifier_h5_models) == list:
            for model_details in config.image_classifier_h5_models:
                classifier = ImageClassifierWrapper(model_details)
                if classifier.can_run:
                    self.classifiers[classifier.model_name] = classifier

    def can_classify(self):
        return len(self.classifiers) > 0

    def classify_image(self, model_name, image_path):
        try:
            return self.classifiers[model_name].classify_image(image_path)
        except KeyError as e:
            if not model_name in self.classifiers:
                classifier_model_names = list(self.classifiers.keys())
                raise Exception(f"Image classifier model name not found: {model_name}\n"
                                f"Valid classifier model names: {classifier_model_names}")
            raise e

    def add_classifier(self, image_classifier):
        if type(image_classifier) != ImageClassifierWrapper:
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





