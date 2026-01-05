import os
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union, Any

import numpy as np
from PIL import Image

from utils.logging_setup import get_logger

logger = get_logger("image_classifier")


class BackendType(Enum):
    """Backend type for image classifiers"""
    PYTORCH = "pytorch"
    HDF5 = "hdf5"
    OTHER = "other"


def _register_adaptive_concat_pool():
    """Register AdaptiveConcatPool2d in __main__ for unpickling compatibility"""
    try:
        import torch
        import torch.nn as nn
        import sys
        
        # Define the class
        class AdaptiveConcatPool2d(nn.Module):
            def __init__(self, sz=None):
                super().__init__()
                self.ap = nn.AdaptiveAvgPool2d(sz or 1)
                self.mp = nn.AdaptiveMaxPool2d(sz or 1)
                
            def forward(self, x):
                return torch.cat([self.mp(x), self.ap(x)], 1)
        
        # Register in the current module
        import sys
        current_module = sys.modules[__name__]
        if not hasattr(current_module, 'AdaptiveConcatPool2d'):
            setattr(current_module, 'AdaptiveConcatPool2d', AdaptiveConcatPool2d)
        
        # Also register in __main__ if it exists
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            if not hasattr(main_module, 'AdaptiveConcatPool2d'):
                setattr(main_module, 'AdaptiveConcatPool2d', AdaptiveConcatPool2d)
                
        # Also register under common FastAI names
        if '__main__' in sys.modules:
            main_module = sys.modules['__main__']
            # Some FastAI models might expect this
            if not hasattr(main_module, 'AdaptiveConcatPool'):
                setattr(main_module, 'AdaptiveConcatPool', AdaptiveConcatPool2d)
        
        return AdaptiveConcatPool2d
        
    except ImportError:
        # Define a placeholder if torch is not available
        class AdaptiveConcatPool2d:
            def __init__(self, *args, **kwargs):
                raise ImportError("PyTorch is required for AdaptiveConcatPool2d")
        return AdaptiveConcatPool2d


# Register the class at module import time
AdaptiveConcatPool2d = _register_adaptive_concat_pool()


class BaseImageClassifier(ABC):
    """Abstract base class for image classifiers"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.is_loaded = False
        self.model = None
        self.input_shape = None
        
    @abstractmethod
    def load_model(self) -> bool:
        """Load the model from file"""
        pass
    
    @abstractmethod
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for model input"""
        pass
    
    @abstractmethod
    def predict(self, preprocessed_image: np.ndarray, batch_size: int = 32) -> np.ndarray:
        """Run prediction on preprocessed image"""
        pass
    
    def predict_image(self, image_path: str) -> np.ndarray:
        """Complete prediction pipeline"""
        preprocessed_img = self.preprocess_image(image_path)
        return self.predict(preprocessed_img)
    
    def _get_input_shape(self) -> Tuple[int, int]:
        """Get input dimensions (width, height) for PIL resize"""
        if self.input_shape is not None:
            return self.input_shape
            
        # Default implementation can be overridden
        raise NotImplementedError("Subclasses must implement _get_input_shape or set self.input_shape")


class H5ImageClassifier(BaseImageClassifier):
    """TensorFlow/Keras H5 model classifier"""
    
    def __init__(self, model_path: str, custom_objects: Optional[Dict] = None):
        """Image classifier for H5 models with version-independent loading
        
        Args:
            model_path: Path to .h5 model file
            custom_objects: Dictionary of custom layer classes {name: class}
        """
        super().__init__(model_path)
        self.custom_objects = custom_objects or {}
        self.load_errors = []
        self.load_model()
    
    def _register_common_layers(self, custom_objects: Dict):
        """Auto-register common custom layers and handle compatibility issues"""
        try:
            import tensorflow_hub as hub
            custom_objects['KerasLayer'] = hub.KerasLayer
        except ImportError:
            pass

    def _load_model_tensorflow_keras(self, model_path: str, custom_objects: Dict):
        """Attempt loading with TensorFlow's built-in Keras"""
        try:
            from tensorflow.keras.models import load_model as tf_load_model
            from tensorflow.keras.utils import custom_object_scope
            with custom_object_scope(custom_objects):
                logger.info("Attempting TensorFlow Keras load...")
                return tf_load_model(model_path)
        except Exception as e:
            self.load_errors.append(f"TensorFlow Keras load failed: {str(e)[:300]}")
            return None

    def _load_model_tf_keras(self, model_path: str, custom_objects: Dict):
        """Fallback to tf_keras package"""
        try:
            from tf_keras.models import load_model
            logger.info("Attempting tf_keras load...")
            return load_model(model_path, custom_objects=custom_objects)
        except Exception as e:
            self.load_errors.append(f"tf_keras load failed: {str(e)[:300]}")
            return None

    def _load_model_keras(self, model_path: str, custom_objects: Dict):
        """Last-resort standalone Keras attempt"""
        try:
            from keras.models import load_model as keras_load_model
            from keras.utils.custom_object_scope import custom_object_scope
            with custom_object_scope(custom_objects):
                logger.info("Attempting standalone Keras load...")
                return keras_load_model(model_path)
        except Exception as e:
            self.load_errors.append(f"Standalone Keras load failed: {str(e)[:300]}")
            return None

    def load_model(self) -> bool:
        """Load model with fallback strategies"""
        self._register_common_layers(self.custom_objects)
        
        loaders = [
            self._load_model_tensorflow_keras,
            self._load_model_tf_keras,
            self._load_model_keras
        ]
        
        for loader in loaders:
            self.model = loader(self.model_path, self.custom_objects)
            if self.model is not None:
                self.is_loaded = True
                self.input_shape = self._get_input_shape()
                self._verify_model_compatibility()
                return True

        logger.error(f"Failed to load model at {self.model_path}")
        for error in self.load_errors:
            logger.error(error)
        return False

    def _get_input_shape(self) -> Tuple[int, int]:
        """Get input dimensions with channels-last/channels-first awareness"""
        if self.model is None:
            raise ValueError("Model not loaded")
            
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

    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image with safety checks"""
        try:
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                img = img.resize(self.input_shape)
                img_array = np.array(img, dtype=np.float32) / 255.0
                return np.expand_dims(img_array, axis=0)
        except Exception as e:
            raise ValueError(f"Image processing failed: {str(e)}")

    def predict(self, preprocessed_image: np.ndarray, batch_size: int = 32) -> np.ndarray:
        """Run prediction with validation"""
        if self.model is None:
            raise ValueError("Model not loaded")
            
        if preprocessed_image.shape[1:3] != self.input_shape[::-1]:
            raise ValueError("Input image dimensions don't match model requirements")
        return self.model.predict(preprocessed_image, batch_size=batch_size)


class PyTorchImageClassifier(BaseImageClassifier):
    """PyTorch model classifier"""
    
    def __init__(self, model_path: str, 
                 device: str = 'auto',
                 normalize_mean: List[float] = None,
                 normalize_std: List[float] = None,
                 input_shape: Optional[Tuple[int, int]] = None,
                 model_architecture = None,
                 weights_only: bool = False,  # Changed to False by default for converted models
                 safe_globals: List = None,
                 load_full_model: bool = True):  # New parameter to load full model directly
        """PyTorch model classifier
        
        Args:
            model_path: Path to .pth/.pt model file
            device: 'auto', 'cuda', or 'cpu'
            normalize_mean: Normalization mean values (default: ImageNet)
            normalize_std: Normalization std values (default: ImageNet)
            input_shape: Optional (width, height) if not inferrable from model
            model_architecture: PyTorch model class/instance if loading state dict
            weights_only: Use safe loading (True) or allow arbitrary code execution (False)
            safe_globals: List of additional safe globals for weights_only=True
            load_full_model: If True, load full model directly (not state_dict)
        """
        super().__init__(model_path)
        self.device = self._get_device(device)
        self.normalize_mean = normalize_mean or [0.485, 0.456, 0.406]
        self.normalize_std = normalize_std or [0.229, 0.224, 0.225]
        self._input_shape_override = input_shape
        self.model_architecture = model_architecture
        self.weights_only = weights_only
        self.safe_globals = safe_globals or []
        self.load_full_model = load_full_model
        self.transform = None
        self.load_model()
    
    def _get_device(self, device: str):
        """Determine torch device"""
        if device == 'auto':
            try:
                import torch
                return torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            except ImportError:
                raise ImportError("PyTorch not installed. Install with: pip install torch torchvision")
        return device
    
    def _ensure_adaptive_concat_pool_registered(self):
        """Ensure AdaptiveConcatPool2d is registered before loading"""
        try:
            import sys
            
            # Check if AdaptiveConcatPool2d is registered in __main__
            if '__main__' in sys.modules:
                main_module = sys.modules['__main__']
                if not hasattr(main_module, 'AdaptiveConcatPool2d'):
                    # Import our registered class from current module
                    from image_classifier import AdaptiveConcatPool2d
                    setattr(main_module, 'AdaptiveConcatPool2d', AdaptiveConcatPool2d)
                    
                    # Also try to register common aliases
                    if not hasattr(main_module, 'AdaptiveConcatPool'):
                        setattr(main_module, 'AdaptiveConcatPool', AdaptiveConcatPool2d)
        except Exception as e:
            logger.warning(f"Could not register AdaptiveConcatPool2d in __main__: {e}")
    
    def load_model(self) -> bool:
        """Load PyTorch model"""
        try:
            import torch
            import torch.nn as nn
            from torchvision import transforms
        except ImportError:
            logger.error("PyTorch or torchvision not installed. Install with: pip install torch torchvision")
            return False
        
        try:
            # CRITICAL: Ensure AdaptiveConcatPool2d is registered in __main__ before loading
            # This is essential for unpickling models saved from FastAI
            self._ensure_adaptive_concat_pool_registered()
            
            # Add common safe globals for converted models
            if self.weights_only and not self.safe_globals:
                # Add torch.nn.modules.container.Sequential to safe globals
                self.safe_globals = [torch.nn.modules.container.Sequential]
            
            # Try to load with safe weights_only first
            try:
                if self.weights_only and self.safe_globals:
                    # Add safe globals if provided
                    for safe_global in self.safe_globals:
                        torch.serialization.add_safe_globals([safe_global])
                
                # Attempt to load the model
                if self.weights_only:
                    logger.info("Attempting safe loading (weights_only=True)...")
                    loaded_data = torch.load(self.model_path, map_location=self.device, weights_only=True)
                else:
                    logger.warning("Using unsafe loading (weights_only=False). Only use with trusted models!")
                    loaded_data = torch.load(self.model_path, map_location=self.device, weights_only=False)
                    
            except (RuntimeError, ImportError) as e:
                if "weights_only" in str(e) and self.weights_only:
                    logger.warning(f"Safe loading failed: {e}")
                    logger.warning("Falling back to unsafe loading for compatibility...")
                    loaded_data = torch.load(self.model_path, map_location=self.device, weights_only=False)
                else:
                    raise
            
            # Handle different save formats
            if isinstance(loaded_data, dict):
                if 'state_dict' in loaded_data:
                    # Handle models saved with state_dict in a dict
                    state_dict = loaded_data['state_dict']
                else:
                    # Assume it's a state_dict directly
                    state_dict = loaded_data
                
                if self.model_architecture is None:
                    logger.error("Model file contains state_dict but no model_architecture was provided.")
                    logger.error("Please provide model_architecture parameter when loading state_dict files.")
                    return False
                
                # Load state dict into model architecture
                if isinstance(self.model_architecture, type):
                    # If it's a class, instantiate it
                    self.model = self.model_architecture()
                else:
                    # If it's already an instance, use it
                    self.model = self.model_architecture
                
                # Strip 'module.' prefix if saved from DataParallel
                from collections import OrderedDict
                if all(k.startswith('module.') for k in state_dict.keys()):
                    state_dict = OrderedDict([(k[7:], v) for k, v in state_dict.items()])
                
                # Load state dict
                self.model.load_state_dict(state_dict)
                self.model = self.model.to(self.device)
                
            elif hasattr(loaded_data, 'eval') and hasattr(loaded_data, 'parameters'):
                # Model is already a nn.Module
                self.model = loaded_data.to(self.device)
            else:
                logger.error(f"Unsupported PyTorch model format in {self.model_path}")
                return False
            
            # Set model to evaluation mode
            self.model.eval()
            self.is_loaded = True
            
            # Setup transforms and input shape
            self._setup_transforms()
            
            # Try to infer input shape
            if self._input_shape_override:
                self.input_shape = self._input_shape_override
            else:
                self.input_shape = self._infer_input_shape()
                # Update transforms with correct shape
                self._setup_transforms()
                
            logger.info(f"PyTorch model loaded successfully on device: {self.device}")
            return True
                
        except Exception as e:
            logger.error(f"Failed to load PyTorch model: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def _setup_transforms(self):
        """Setup image transformations"""
        try:
            from torchvision import transforms
            
            if self.input_shape is None:
                # Default to 224x224 if not set
                self.input_shape = (224, 224)
                
            self.transform = transforms.Compose([
                transforms.Resize(self.input_shape[::-1]),  # (height, width) for torch
                transforms.ToTensor(),
                transforms.Normalize(mean=self.normalize_mean, std=self.normalize_std)
            ])
        except ImportError:
            logger.error("torchvision not available for transforms")
    
    def _infer_input_shape(self) -> Tuple[int, int]:
        """Try to infer input shape from model"""
        try:
            import torch
            
            # Check if model has expected_input_size attribute
            if hasattr(self.model, 'expected_input_size'):
                size = self.model.expected_input_size
                if isinstance(size, (tuple, list)) and len(size) >= 2:
                    return (size[1], size[0])  # Convert to (width, height)
            
            # Check if model has input_size attribute
            if hasattr(self.model, 'input_size'):
                size = self.model.input_size
                if isinstance(size, (tuple, list)) and len(size) >= 2:
                    return (size[1], size[0])  # Convert to (width, height)
                elif isinstance(size, int):
                    return (size, size)
            
            # For ResNet models, input is typically 224x224
            model_str = str(self.model).lower()
            if 'resnet' in model_str or 'fastai' in model_str:
                return (224, 224)
            
            # Try to get from first conv layer
            for module in self.model.modules():
                if isinstance(module, torch.nn.Conv2d):
                    # This is a heuristic - actual input might be different
                    logger.info("Inferring input size from Conv2d layer (may not be accurate)")
                    return (224, 224)  # Common default
            
        except Exception as e:
            logger.warning(f"Could not infer input shape: {e}")
        
        # Default fallback
        logger.warning("Could not infer input shape, using default (224, 224)")
        return (224, 224)
    
    def preprocess_image(self, image_path: str) -> np.ndarray:
        """Preprocess image for PyTorch model"""
        if not self.is_loaded:
            raise ValueError("Model not loaded")
        
        try:
            import torch
            
            with Image.open(image_path) as img:
                img = img.convert('RGB')
                tensor = self.transform(img)
                # Add batch dimension
                tensor = tensor.unsqueeze(0).to(self.device)
                return tensor
        except Exception as e:
            raise ValueError(f"Image processing failed: {str(e)}")
    
    def predict(self, preprocessed_image: np.ndarray, batch_size: int = 32) -> np.ndarray:
        """Run prediction with PyTorch model"""
        if not self.is_loaded or self.model is None:
            raise ValueError("Model not loaded")
        
        try:
            import torch
            
            with torch.no_grad():
                output = self.model(preprocessed_image)
                # Convert to probabilities if needed
                if not torch.all(output >= 0) or not torch.all(output <= 1):
                    output = torch.nn.functional.softmax(output, dim=1)
                out = output.cpu().numpy()
                print(out)
                return out
        except Exception as e:
            raise ValueError(f"Prediction failed: {str(e)}")


class ImageClassifierWrapper:
    def __init__(self, model_name="", model_categories=["drawing", "photograph"],
                 model_location="", use_hub_keras_layers=False, 
                 backend="auto", model_kwargs=None):
        """General purpose image classifier wrapper
        
        Args:
            model_name: Name of the model
            model_categories: List of category names
            model_location: Path to model file
            use_hub_keras_layers: For TensorFlow Hub layers (TensorFlow only)
            backend: BackendType enum or string ("auto", "tensorflow"/"hdf5", or "pytorch")
            model_kwargs: Additional kwargs for model initialization
        """
        self.model_name = model_name
        self.model_categories = model_categories
        self.model_location = model_location
        self.use_hub_keras_layers = use_hub_keras_layers
        # Convert string backend to enum, handling legacy values
        self.backend = self._parse_backend(backend)
        self.model_kwargs = model_kwargs or {}
        self.can_run = True
        self.classifier = None
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
                    raise Exception(f"Invalid use hub keras layers flag, must be boolean: {self.use_hub_keras_layers}")
            except Exception as e:
                self.can_run = False
                logger.error(e)
                logger.warning("Failed to set model details for image classifier: " + str(self.__dict__))
            if self.can_run:
                self.load_classifier()

    def _parse_backend(self, backend):
        """Parse backend string to BackendType enum"""
        if isinstance(backend, BackendType):
            return backend
        
        backend_str = str(backend).lower().strip()
        if backend_str == "auto":
            return None  # Will be determined from file extension
        elif backend_str in ("tensorflow", "hdf5", "h5"):
            return BackendType.HDF5
        elif backend_str == "pytorch":
            return BackendType.PYTORCH
        else:
            return BackendType.OTHER

    def load_classifier(self):
        """Load appropriate classifier based on backend and file extension"""
        assert self.can_run is True
        
        # Determine backend if auto
        if self.backend is None:
            if self.model_location.lower().endswith('.h5'):
                self.backend = BackendType.HDF5
            elif self.model_location.lower().endswith(('.pth', '.pt', '.safetensors', '.bin')):
                self.backend = BackendType.PYTORCH
            else:
                self.can_run = False
                logger.error(f"Cannot determine backend for file: {self.model_location}")
                return
        
        # Initialize appropriate classifier
        try:
            if self.backend == BackendType.HDF5:
                custom_objects = {}
                if self.use_hub_keras_layers:
                    try:
                        import tensorflow_hub as hub
                        custom_objects['KerasLayer'] = hub.KerasLayer
                    except ImportError:
                        logger.error("Failed to import tensorflow hub to support h5 model, please install it using pip")
                        self.can_run = False
                        return
                
                self.classifier = H5ImageClassifier(
                    self.model_location,
                    custom_objects=custom_objects,
                    **self.model_kwargs
                )
                
            elif self.backend == BackendType.PYTORCH:
                # For converted FastAI models, set appropriate defaults
                # Check if this looks like a converted FastAI model
                model_name_lower = self.model_name.lower()
                model_path_lower = self.model_location.lower()
                
                # Default kwargs for PyTorch
                pytorch_kwargs = self.model_kwargs.copy()
                
                # Set defaults for converted models if not specified
                if 'weights_only' not in pytorch_kwargs:
                    pytorch_kwargs['weights_only'] = False  # Safer for converted models
                
                self.classifier = PyTorchImageClassifier(
                    self.model_location,
                    **pytorch_kwargs
                )
            else:
                logger.error(f"Unsupported backend: {self.backend}")
                self.can_run = False
                return
                
            self.can_run = bool(self.classifier.is_loaded)
            
        except Exception as e:
            self.can_run = False
            logger.error(e)
            logger.warning(f"Failed to initialize {self.backend} model for image classifier: {self.model_name}")

    def predict_image(self, image_path):
        if image_path in self.predictions_cache:
            return self.predictions_cache[image_path]
        
        if self.classifier is None:
            raise ValueError("Classifier not initialized")
        
        predictions = self.classifier.predict_image(image_path)
        classed_predictions = {}
        
        # Ensure we have the right number of outputs
        if len(predictions[0]) != len(self.model_categories):
            logger.warning(f"Model outputs {len(predictions[0])} classes but expected {len(self.model_categories)}")
            # Map outputs to available categories (or use all outputs)
            for i in range(min(len(predictions[0]), len(self.model_categories))):
                classed_predictions[self.model_categories[i]] = float(predictions[0][i])
        else:
            for i in range(len(self.model_categories)):
                classed_predictions[self.model_categories[i]] = float(predictions[0][i])
        
        self.predictions_cache[image_path] = dict(classed_predictions)
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
        return f"{self.__class__.__name__}(name='{self.model_name}', categories={self.model_categories}, backend={self.backend})"

    def __hash__(self) -> int:
        return hash(self.model_name)
    
    def __eq__(self, other):
        if not isinstance(other, ImageClassifierWrapper):
            raise TypeError(f"Invalid type for comparison: {type(other)}")
        return self.model_name == other.model_name


# Factory function for convenience
def create_image_classifier(model_name: str = "",
                           model_categories: List[str] = None,
                           model_location: str = "",
                           use_hub_keras_layers: bool = False,
                           backend: Union[str, BackendType] = "auto",
                           **kwargs) -> ImageClassifierWrapper:
    """Factory function to create an ImageClassifierWrapper"""
    if model_categories is None:
        model_categories = ["drawing", "photograph"]
    
    return ImageClassifierWrapper(
        model_name=model_name,
        model_categories=model_categories,
        model_location=model_location,
        use_hub_keras_layers=use_hub_keras_layers,
        backend=backend,
        model_kwargs=kwargs
    )


# Helper function specifically for converted FastAI models
def create_converted_fastai_classifier(model_path: str,
                                     model_categories: List[str],
                                     model_name: str = "converted_fastai_model",
                                     **kwargs) -> ImageClassifierWrapper:
    """Helper to create a classifier for converted FastAI models
    
    This assumes the model has been converted using convert_to_pytorch.py
    """
    # Set defaults for converted models
    default_kwargs = {
        "weights_only": False,  # Must be False for converted full models
        "load_full_model": True,  # Load full model, not state_dict
        "device": "auto",
        "input_shape": (224, 224),  # Standard for ResNet
    }
    
    # Update with user kwargs
    default_kwargs.update(kwargs)
    
    return create_image_classifier(
        model_name=model_name,
        model_categories=model_categories,
        model_location=model_path,
        backend=BackendType.PYTORCH,
        **default_kwargs
    )