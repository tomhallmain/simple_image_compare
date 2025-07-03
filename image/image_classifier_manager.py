from typing import Dict, Any, Optional, List

from image.image_classifier import ImageClassifierWrapper
from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger("image_classifier_manager")


class ImageClassifierManager:
    classifier_metadata: Dict[str, Dict[str, Any]]
    classifiers: Dict[str, ImageClassifierWrapper]

    def __init__(self) -> None:
        self.classifier_metadata = {}
        self.classifiers = {}
        if isinstance(config.image_classifier_h5_models, list):
            for model_details in config.image_classifier_h5_models:
                model_name = model_details['model_name']
                self.classifier_metadata[model_name] = model_details

    def can_classify(self) -> bool:
        return len(self.get_model_names()) > 0

    def classify_image(self, model_name: str, image_path: str) -> Any:
        try:
            return self.get_classifier(model_name).classify_image(image_path)
        except KeyError as e:
            if model_name not in self.classifier_metadata:
                classifier_model_names = list(self.classifier_metadata.keys())
                raise Exception(f"Image classifier model name not found: {model_name}\n"
                                f"Valid classifier model names: {classifier_model_names}")
            raise e

    def add_classifier(self, image_classifier: ImageClassifierWrapper) -> None:
        if not isinstance(image_classifier, ImageClassifierWrapper):
            raise Exception(f"Invalid image classifier argument: {image_classifier}")
        if image_classifier.can_run:
            self.classifiers[image_classifier.model_name] = image_classifier
            logger.info(f"Added image classifier: {image_classifier}")
        else:
            logger.warning(f"Image classifier not runnable: {image_classifier}")

    def get_classifier(self, model_name: Optional[str]) -> Optional[ImageClassifierWrapper]:
        if model_name is None or model_name.strip() == "":
            return None
        if model_name in self.classifiers:
            return self.classifiers[model_name]
        if model_name not in self.classifier_metadata:
            raise Exception(f"Failed to find image classifier with model name: \"{model_name}\"")
        classifier = ImageClassifierWrapper(**self.classifier_metadata[model_name])
        self.classifiers[model_name] = classifier
        return classifier

    def get_model_names(self) -> List[str]:
        return list(self.classifier_metadata.keys())


image_classifier_manager = ImageClassifierManager()





