import os
import sys
import hashlib
import time
from typing import Optional, List
import numpy as np

from compare.base_compare import gather_files
from compare.compare_data import CompareData
from compare.model import image_embeddings_clip
from utils.app_info_cache import app_info_cache
from utils.config import config
from utils.constants import CompareMode
from utils.logging_setup import get_logger

logger = get_logger("embedding_prototype")

# Cache of CompareData instances per directory
_directory_caches: dict[str, CompareData] = {}
# Track last access time for each cache (for LRU eviction)
_cache_access_times: dict[str, float] = {}
# Maximum memory size (in bytes) for directory caches before removing old ones
# Default: 500 MB (500 * 1024 * 1024 bytes)
MAX_DIRECTORY_CACHE_MEMORY_BYTES = 500 * 1024 * 1024


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
        
        # Get cache for this directory
        cache = EmbeddingPrototype._get_cache_for_directory(directory_path)
        
        for i, image_path in enumerate(image_files):
            try:
                if image_path in cache.file_data_dict:
                    embedding = cache.file_data_dict[image_path]
                else:
                    # Compute embedding if not cached
                    embedding = image_embeddings_clip(image_path)
                    cache.file_data_dict[image_path] = embedding
                    # Add to files_found if not already present (needed for save_data validation)
                    if image_path not in cache.files_found:
                        cache.files_found.append(image_path)
                    cache.has_new_file_data = True
                
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
        
        # Save embedding cache if new data was added and we have files
        if cache.has_new_file_data and len(cache.files_found) > 0:
            try:
                cache.save_data(overwrite=False, verbose=False)
            except Exception as e:
                logger.warning(f"Error saving cache for {directory_path}: {e}")
            EmbeddingPrototype._remove_cache_from_memory(directory_path)
        
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
    def compute_embeddings_batch_with_dirs(image_paths_with_dirs: List[tuple[str, str]], notify_callback=None) -> tuple[np.ndarray, List[str]]:
        """
        Compute embeddings for multiple images in batch, using CompareData cache per directory.
        
        Args:
            image_paths_with_dirs: List of (image_path, base_directory) tuples
            notify_callback: Optional callback for progress notifications
            
        Returns:
            Tuple of (embeddings_array, valid_image_paths) where:
            - embeddings_array: Numpy array of shape (n_valid_images, embedding_dim)
            - valid_image_paths: List of image paths that successfully had embeddings computed
        """
        from compare.model import image_embeddings_clip
        embeddings = []
        valid_image_paths = []
        directories_with_new_data = set()
        previous_directory = None
        cache = None
        
        for i, (image_path, base_directory) in enumerate(image_paths_with_dirs):
            try:
                # Get cache for the base directory
                if base_directory != previous_directory:
                    if cache is not None:
                        # Save cache and remove from memory to allow garbage collection
                        try:
                            cache.save_data(overwrite=False, verbose=False)
                        except Exception as e:
                            logger.warning(f"Error saving cache for {previous_directory}: {e}")
                        cache.has_new_file_data = False
                        EmbeddingPrototype._remove_cache_from_memory(previous_directory)
                    cache = EmbeddingPrototype._get_cache_for_directory(base_directory)
                previous_directory = base_directory
                
                # # Construct full path if image_path is relative
                # if not os.path.isabs(image_path):
                #     full_path = os.path.join(base_directory, image_path)
                # else:
                full_path = image_path
                
                if full_path in cache.file_data_dict:
                    embedding = cache.file_data_dict[full_path]
                else:
                    # Compute embedding if not cached
                    embedding = image_embeddings_clip(full_path)
                    cache.file_data_dict[full_path] = embedding
                    # Add to files_found if not already present (needed for save_data validation)
                    if full_path not in cache.files_found:
                        cache.files_found.append(full_path)
                    cache.has_new_file_data = True
                    directories_with_new_data.add(base_directory)
                
                embeddings.append(embedding)
                valid_image_paths.append(full_path)
                
                if notify_callback and (i + 1) % 1000 == 0:
                    notify_callback(_("Computed embeddings for {0}/{1} images...").format(i + 1, len(image_paths_with_dirs)))
            except Exception as e:
                logger.error(f"Error calculating embedding for {image_path}: {e}")
                continue
        
        # Save caches for directories with new data and remove from memory
        for directory in directories_with_new_data:
            abs_dir = os.path.abspath(directory)
            if abs_dir in _directory_caches:
                cache = _directory_caches[abs_dir]
                try:
                    cache.save_data(overwrite=False, verbose=False)
                except Exception as e:
                    logger.warning(f"Error saving cache for {directory}: {e}")
                EmbeddingPrototype._remove_cache_from_memory(directory)
        
        if not embeddings:
            return np.array([]), []
        
        return np.array(embeddings), valid_image_paths
    
    @staticmethod
    def compare_embeddings_with_prototype(embeddings_array: np.ndarray, prototype: np.ndarray) -> np.ndarray:
        """
        Compare a batch of embeddings with a prototype using vectorized cosine similarity.
        
        Args:
            embeddings_array: Numpy array of shape (n_images, embedding_dim) containing embeddings
            prototype: Prototype embedding vector of shape (embedding_dim,)
            
        Returns:
            Numpy array of cosine similarity scores (0-1, higher is more similar) of shape (n_images,)
        """
        if len(embeddings_array) == 0:
            return np.array([])
        
        # Use vectorized dot product: embeddings_array @ prototype computes dot product for each row
        # Embeddings are already normalized, so dot product is cosine similarity
        similarities = np.dot(embeddings_array, prototype)
        return similarities
    
    @staticmethod
    def _get_cache_for_directory(directory: str) -> CompareData:
        """Get or create a CompareData instance for a directory."""
        abs_dir = os.path.abspath(directory)
        current_time = time.time()
        
        if abs_dir not in _directory_caches:
            _directory_caches[abs_dir] = CompareData(base_dir=abs_dir, mode=CompareMode.CLIP_EMBEDDING)
            _directory_caches[abs_dir].load_data(overwrite=False)
            _cache_access_times[abs_dir] = current_time
        else:
            # Reload data if it was cleared after saving (file_data_dict is None)
            cache = _directory_caches[abs_dir]
            if cache.file_data_dict is None:
                cache.load_data(overwrite=False)
            # Update access time for LRU tracking
            _cache_access_times[abs_dir] = current_time
        return _directory_caches[abs_dir]
    
    @staticmethod
    def _estimate_cache_memory_size() -> int:
        """
        Estimate the total memory size of all directory caches in bytes.
        
        Returns:
            Estimated memory size in bytes
        """
        total_size = sys.getsizeof(_directory_caches)
        for abs_dir, cache in _directory_caches.items():
            # Size of the key (directory path string)
            total_size += sys.getsizeof(abs_dir)
            # Size of the cache object itself (delegates to CompareData.estimate_memory_size)
            total_size += cache.estimate_memory_size()
        return total_size
    
    @staticmethod
    def _evict_caches_if_needed():
        """
        Evict caches using LRU (Least Recently Used) strategy when memory exceeds threshold.
        Removes the least recently accessed caches until memory is below the threshold.
        """
        current_memory = EmbeddingPrototype._estimate_cache_memory_size()
        
        if current_memory <= MAX_DIRECTORY_CACHE_MEMORY_BYTES:
            return
        
        # Sort caches by access time (oldest first) for LRU eviction
        # Create list of (abs_dir, access_time, cache_size) tuples
        cache_info = []
        for abs_dir, cache in _directory_caches.items():
            access_time = _cache_access_times.get(abs_dir, 0.0)
            cache_size = cache.estimate_memory_size()
            cache_info.append((abs_dir, access_time, cache_size))
        
        # Sort by access time (oldest first)
        cache_info.sort(key=lambda x: x[1])
        
        # Evict oldest caches until memory is below threshold
        evicted_count = 0
        for abs_dir, _, _ in cache_info:
            if current_memory <= MAX_DIRECTORY_CACHE_MEMORY_BYTES:
                break
            
            # Remove cache and its access time
            if abs_dir in _directory_caches:
                del _directory_caches[abs_dir]
                if abs_dir in _cache_access_times:
                    del _cache_access_times[abs_dir]
                evicted_count += 1
                current_memory = EmbeddingPrototype._estimate_cache_memory_size()
        
        if evicted_count > 0:
            logger.debug(f"Evicted {evicted_count} LRU cache(s) (memory: {current_memory / (1024*1024):.1f}MB <= {MAX_DIRECTORY_CACHE_MEMORY_BYTES / (1024*1024):.1f}MB)")
    
    @staticmethod
    def _remove_cache_from_memory(directory: str):
        """
        Mark a cache as saved and trigger eviction if memory exceeds threshold.
        Uses LRU strategy to evict least recently used caches.
        """
        abs_dir = os.path.abspath(directory)
        if abs_dir in _directory_caches:
            # Check if we need to evict caches (including this one if it's LRU)
            EmbeddingPrototype._evict_caches_if_needed()
            
            # Log current state
            current_memory = EmbeddingPrototype._estimate_cache_memory_size()
            if abs_dir in _directory_caches:
                logger.debug(f"Keeping cache for {directory} in memory (memory: {current_memory / (1024*1024):.1f}MB <= {MAX_DIRECTORY_CACHE_MEMORY_BYTES / (1024*1024):.1f}MB)")
            else:
                logger.debug(f"Cache for {directory} was evicted by LRU strategy (memory: {current_memory / (1024*1024):.1f}MB <= {MAX_DIRECTORY_CACHE_MEMORY_BYTES / (1024*1024):.1f}MB)")
    
    @staticmethod
    def batch_validate_with_prototypes(
        directories: List[str],
        positive_prototype: np.ndarray,
        threshold: float,
        negative_prototype: Optional[np.ndarray] = None,
        negative_lambda: float = 0.5,
        notify_callback=None,
        max_images_per_batch: Optional[int] = None
    ) -> List[str]:
        """
        Validate images in directories against prototype(s) using vectorized operations.
        
        Gathers images from the provided directories, computes embeddings (using cache),
        then uses vectorized operations to compare with prototypes, returning only
        the image paths that meet the threshold.
        
        Uses formula: Final Score = sim(query, positive_proto) - λ * sim(query, negative_proto)
        If negative prototype is not set, uses only positive similarity.
        
        Processes images in batches if max_images_per_batch is specified to limit memory usage.
        
        Args:
            directories: List of directory paths to process images from
            positive_prototype: Positive prototype embedding vector
            threshold: Similarity threshold (0-1)
            negative_prototype: Optional negative prototype embedding vector
            negative_lambda: Weight for negative prototype (λ)
            notify_callback: Optional callback for progress notifications
            max_images_per_batch: Optional maximum number of images to process per batch (default: None, no batching)
            
        Returns:
            List of image paths that meet the threshold
        """
        if not directories:
            return []
        
        if notify_callback:
            notify_callback(_("Gathering image files from directories..."))
        
        # Gather all image files from directories, tracking which directory each came from
        image_exts = config.image_types[:]
        image_paths_with_dirs = []  # List of (image_path, base_directory) tuples
        for directory in directories:
            if not os.path.isdir(directory):
                logger.warning(f"Directory does not exist: {directory}")
                continue
            
            abs_directory = os.path.abspath(directory)
            files = gather_files(
                base_dir=abs_directory,
                exts=image_exts,
                recursive=True,
                include_videos=False,
                include_gifs=True,
                include_pdfs=False
            )
            # Track which directory these files came from (gather_files returns absolute paths)
            for file_path in files:
                image_paths_with_dirs.append((file_path, abs_directory))
        
        if not image_paths_with_dirs:
            return []
        
        # Process images in batches if max_images_per_batch is specified
        all_matching_paths = []
        total_images = len(image_paths_with_dirs)
        
        # Determine batch size and number of batches
        if max_images_per_batch is not None and total_images > max_images_per_batch:
            batch_size = max_images_per_batch
            num_batches = (total_images + max_images_per_batch - 1) // max_images_per_batch
            if notify_callback:
                notify_callback(_("Processing {0} images in {1} batches of up to {2} images...").format(total_images, num_batches, max_images_per_batch))
            logger.info(f"Processing {total_images} images in {num_batches} batches of up to {max_images_per_batch} images")
        else:
            # Process all images in a single batch
            batch_size = total_images
            num_batches = 1
            if notify_callback:
                notify_callback(_("Computing embeddings for batch prototype validation..."))
        
        # Process each batch
        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_images)
            batch_paths = image_paths_with_dirs[start_idx:end_idx]
            
            if num_batches > 1 and notify_callback:
                notify_callback(_("Processing batch {0}/{1} ({2} images)...").format(batch_idx + 1, num_batches, len(batch_paths)))
            
            # Compute embeddings for this batch
            embeddings_array, valid_image_paths = EmbeddingPrototype.compute_embeddings_batch_with_dirs(batch_paths, notify_callback)
            
            if len(embeddings_array) == 0:
                if batch_idx == 0:
                    logger.warning("No valid embeddings computed for batch prototype validation")
                    return []
                continue
            
            # Vectorized comparison with positive prototype
            positive_similarities = EmbeddingPrototype.compare_embeddings_with_prototype(
                embeddings_array, positive_prototype
            )
            
            # Vectorized comparison with negative prototype if set
            if negative_prototype is not None:
                negative_similarities = EmbeddingPrototype.compare_embeddings_with_prototype(
                    embeddings_array, negative_prototype
                )
                # Calculate final scores: positive - λ * negative
                final_scores = positive_similarities - negative_lambda * negative_similarities
            else:
                final_scores = positive_similarities
            
            # Find images that meet the threshold using vectorized comparison
            threshold_mask = final_scores >= threshold
            
            # Add matching paths from this batch
            batch_matching_paths = [valid_image_paths[i] for i in range(len(valid_image_paths)) if threshold_mask[i]]
            all_matching_paths.extend(batch_matching_paths)
            
            # Log top 5 similarity scores for debugging (only for single batch case when no matches found)
            if num_batches == 1 and len(all_matching_paths) == 0:
                # Create list of (score, path) tuples
                score_path_pairs = [(final_scores[i], valid_image_paths[i]) for i in range(len(valid_image_paths))]
                # Sort by score descending
                score_path_pairs.sort(key=lambda x: x[0], reverse=True)
                # Log top 5
                top_5 = score_path_pairs[:5]
                logger.info(f"No images met the threshold of {threshold:.4f}. Top 5 similarity scores:")
                for score, path in top_5:
                    logger.info(f"  {score:.4f}: {path}")

        if notify_callback:
            notify_callback(_("Found {0} images that meet the threshold...").format(len(all_matching_paths)))
        logger.info(f"Found {len(all_matching_paths)} images that meet the threshold")

        return all_matching_paths
    
    @staticmethod
    def compare_with_prototype(image_path: str, prototype: np.ndarray) -> float:
        """
        Compare an image with a prototype embedding using cosine similarity.
        
        This is a convenience method for single-image comparison. For batch processing,
        use compute_embeddings_batch() followed by compare_embeddings_with_prototype().
        
        Args:
            image_path: Path to image to compare
            prototype: Prototype embedding vector
            
        Returns:
            Cosine similarity score (0-1, higher is more similar)
        """
        try:
            # Get the directory for this image and its cache
            image_dir = os.path.dirname(image_path)
            cache = EmbeddingPrototype._get_cache_for_directory(image_dir)
            
            # Use relative path from directory as key (as CompareData expects)
            rel_path = os.path.relpath(image_path, image_dir)
            
            if rel_path in cache.file_data_dict:
                image_embedding = cache.file_data_dict[rel_path]
            else:
                # Compute embedding if not cached
                image_embedding = image_embeddings_clip(image_path)
                cache.file_data_dict[rel_path] = image_embedding
                # Add to files_found if not already present (needed for save_data validation)
                if rel_path not in cache.files_found:
                    cache.files_found.append(rel_path)
                cache.has_new_file_data = True
                cache.save_data(overwrite=False, verbose=False)
            
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

