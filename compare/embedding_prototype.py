import os
import hashlib
from typing import Optional, List
import numpy as np

from compare.base_compare import gather_files
from compare.model import image_embeddings_clip
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.logging_setup import get_logger

logger = get_logger("embedding_prototype")


class EmbeddingPrototype:
    """
    Manages embedding prototypes created from directories of sample images.
    Uses mean/average embedding as the prototype vector.
    """
    
    CACHE_KEY = "embedding_prototypes"
    
    @staticmethod
    def _get_file_list_id(file_paths: List[str]) -> str:
        """
        Generate a unique ID from a sorted list of file paths.
        Uses hash of sorted paths for consistent identification.
        
        Args:
            file_paths: List of file paths
            
        Returns:
            Hash string identifying this file configuration
        """
        # Sort paths for consistency
        sorted_paths = sorted(file_paths)
        # Create a hash from the sorted paths
        paths_str = "\n".join(sorted_paths)
        return hashlib.sha256(paths_str.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _get_prototypes_dict() -> dict:
        """Get the prototypes dictionary from cache."""
        return app_info_cache.get_meta(EmbeddingPrototype.CACHE_KEY, default_val={})
    
    @staticmethod
    def _set_prototypes_dict(prototypes_dict: dict):
        """Set the prototypes dictionary in cache."""
        app_info_cache.set_meta(EmbeddingPrototype.CACHE_KEY, prototypes_dict)
    
    @staticmethod
    def calculate_prototype_from_directory(
        directory_path: str,
        force_recalculate: bool = False,
        notify_callback=None
    ) -> Optional[np.ndarray]:
        """
        Calculate the average embedding prototype from all images in a directory.
        
        Args:
            directory_path: Path to directory containing sample images
            force_recalculate: If True, recalculate even if cached
            notify_callback: Optional callback for progress notifications
            
        Returns:
            Average embedding vector as numpy array, or None if no images found
        """
        if not os.path.isdir(directory_path):
            logger.error(f"Directory does not exist: {directory_path}")
            return None
        
        # Gather all image files from directory
        if notify_callback:
            notify_callback(_("Gathering image files from directory..."))
        
        # Combine image types with .svg
        image_exts = config.image_types[:] + [".svg"]
        
        image_files = gather_files(
            base_dir=directory_path,
            exts=image_exts,
            recursive=True,
            include_videos=False,
            include_gifs=True,
            include_pdfs=False
        )
        
        if not image_files:
            logger.warning(f"No image files found in directory: {directory_path}")
            return None
        
        # Sort files for consistent ID generation
        image_files = sorted(image_files)
        file_list_id = EmbeddingPrototype._get_file_list_id(image_files)
        
        # Check cache unless forcing recalculation
        if not force_recalculate:
            cached_data = EmbeddingPrototype._get_cached_data(file_list_id)
            if cached_data is not None:
                prototype_list = cached_data.get("prototype")
                if prototype_list is not None:
                    cached_prototype = np.array(prototype_list)
                    logger.info(f"Using cached prototype for {len(image_files)} files (ID: {file_list_id[:8]}...)")
                    return cached_prototype
        
        # Calculate embeddings for all images
        if notify_callback:
            notify_callback(_("Calculating embeddings for {0} images...").format(len(image_files)))
        
        embeddings = []
        failed_count = 0
        
        for i, image_path in enumerate(image_files):
            try:
                embedding = image_embeddings_clip(image_path)
                embeddings.append(embedding)
                
                if notify_callback and (i + 1) % 10 == 0:
                    notify_callback(_("Processed {0}/{1} images...").format(i + 1, len(image_files)))
            except Exception as e:
                logger.error(f"Error calculating embedding for {image_path}: {e}")
                failed_count += 1
                continue
        
        if not embeddings:
            logger.error(f"Failed to calculate embeddings for any images in {directory_path}")
            return None
        
        if failed_count > 0:
            logger.warning(f"Failed to calculate embeddings for {failed_count} out of {len(image_files)} images")
        
        # Calculate mean/average embedding
        if notify_callback:
            notify_callback(_("Calculating average embedding..."))
        
        embeddings_array = np.array(embeddings)
        mean_embedding = np.mean(embeddings_array, axis=0)
        
        # Normalize the mean embedding (important for cosine similarity)
        norm = np.linalg.norm(mean_embedding)
        if norm > 0:
            mean_embedding = mean_embedding / norm
        
        # Cache the result
        EmbeddingPrototype._cache_prototype(file_list_id, image_files, mean_embedding)
        
        logger.info(f"Calculated prototype from {len(embeddings)} images (ID: {file_list_id[:8]}...)")
        
        return mean_embedding
    
    @staticmethod
    def _cache_prototype(file_list_id: str, file_paths: List[str], prototype: np.ndarray):
        """
        Cache a prototype embedding and its file list.
        
        Args:
            file_list_id: Unique ID for this file configuration
            file_paths: List of file paths used to create the prototype
            prototype: The prototype embedding vector
        """
        # Store the prototype as a list (numpy arrays aren't JSON serializable)
        prototype_list = prototype.tolist()
        
        # Store both prototype and file list in a dictionary
        cache_data = {
            "prototype": prototype_list,
            "file_list": file_paths
        }
        
        # Get the prototypes dictionary and update it
        prototypes_dict = EmbeddingPrototype._get_prototypes_dict()
        prototypes_dict[file_list_id] = cache_data
        EmbeddingPrototype._set_prototypes_dict(prototypes_dict)
        
        logger.debug(f"Cached prototype with ID: {file_list_id[:8]}...")
    
    @staticmethod
    def _get_cached_data(file_list_id: str) -> Optional[dict]:
        """
        Retrieve cached data for a prototype (both prototype and file_list).
        
        Args:
            file_list_id: Unique ID for the file configuration
            
        Returns:
            Dictionary with "prototype" and "file_list" keys, or None if not found
        """
        prototypes_dict = EmbeddingPrototype._get_prototypes_dict()
        return prototypes_dict.get(file_list_id)
    
    @staticmethod
    def get_cached_prototype(file_list_id: str) -> Optional[np.ndarray]:
        """
        Retrieve a cached prototype embedding.
        
        Args:
            file_list_id: Unique ID for the file configuration
            
        Returns:
            Prototype embedding as numpy array, or None if not found
        """
        cached_data = EmbeddingPrototype._get_cached_data(file_list_id)
        
        if cached_data is None:
            return None
        
        try:
            prototype_list = cached_data.get("prototype")
            if prototype_list is None:
                return None
            return np.array(prototype_list)
        except Exception as e:
            logger.error(f"Error loading cached prototype: {e}")
            return None
    
    @staticmethod
    def get_cached_file_list(file_list_id: str) -> Optional[List[str]]:
        """
        Retrieve the file list for a cached prototype.
        
        Args:
            file_list_id: Unique ID for the file configuration
            
        Returns:
            List of file paths, or None if not found
        """
        cached_data = EmbeddingPrototype._get_cached_data(file_list_id)
        
        if cached_data is None:
            return None
        
        return cached_data.get("file_list")
    
    @staticmethod
    def compare_with_prototype(image_path: str, prototype: np.ndarray) -> float:
        """
        Compare an image with a prototype embedding using cosine similarity.
        
        Args:
            image_path: Path to image to compare
            prototype: Prototype embedding vector
            
        Returns:
            Cosine similarity score (0-1, higher is more similar)
        """
        try:
            image_embedding = image_embeddings_clip(image_path)
            image_embedding_array = np.array(image_embedding)
            
            # Calculate cosine similarity
            dot_product = np.dot(image_embedding_array, prototype)
            # Embeddings are already normalized, so dot product is cosine similarity
            return float(dot_product)
        except Exception as e:
            logger.error(f"Error comparing image {image_path} with prototype: {e}")
            return 0.0
    
    @staticmethod
    def clear_cache(file_list_id: Optional[str] = None):
        """
        Clear cached prototypes. If file_list_id is provided, only clear that one.
        Otherwise, clear all cached prototypes.
        
        Args:
            file_list_id: Optional specific prototype ID to clear
        """
        if file_list_id:
            # Remove specific prototype from dictionary
            prototypes_dict = EmbeddingPrototype._get_prototypes_dict()
            if file_list_id in prototypes_dict:
                del prototypes_dict[file_list_id]
                EmbeddingPrototype._set_prototypes_dict(prototypes_dict)
                logger.info(f"Cleared cache for prototype ID: {file_list_id[:8]}...")
        else:
            # Clear all prototypes
            EmbeddingPrototype._set_prototypes_dict({})
            logger.info("Cleared all prototype caches")


# Import translation function
from utils.translations import I18N
_ = I18N._

