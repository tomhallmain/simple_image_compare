import os
import tempfile
from typing import Optional, Dict, List

import cv2
import pypdfium2 as pdfium

from utils.config import config
from utils.utils import Utils
from utils.constants import CompareMediaType


class FrameCache:
    """
    A cache for extracting and storing the first frame from various media types (videos, GIFs, PDFs).
    This helps improve performance by avoiding repeated frame extraction operations.
    """
    temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")
    cache: Dict[str, str] = {}  # Maps media_path to cached image path

    @classmethod
    def get_image_path(cls, media_path: str) -> str:
        """
        Get the image path for a media file. If it's a video/GIF/PDF, extracts the first frame.
        Otherwise returns the original path.

        Args:
            media_path: Path to the media file

        Returns:
            Path to the image file (either original or extracted frame)
        """
        media_path_lower = media_path.lower()

        # Check for PDF files first
        if media_path_lower.endswith('.pdf'):
            if config.enable_pdfs:
                return cls.get_first_frame(media_path, CompareMediaType.PDF)
            else:
                return media_path

        # Check for video types from config (which may be dynamic)
        if config.enable_videos:
            for ext in config.video_types:
                if media_path_lower.endswith(ext):
                    return cls.get_first_frame(media_path, CompareMediaType.VIDEO)

        return media_path

    @classmethod
    def get_first_frame(cls, media_path: str, media_type: CompareMediaType) -> str:
        """
        Get the first frame from a media file, using cache if available.

        Args:
            media_path: Path to the media file
            media_type: Type of media (from CompareMediaType enum)

        Returns:
            Path to the extracted frame image
        """
        if media_path not in cls.cache:
            cls.set_first_frame(media_path, media_type)
        return cls.cache[media_path]

    @classmethod
    def set_first_frame(cls, media_path: str, media_type: CompareMediaType) -> None:
        """
        Extract and cache the first frame from a media file.

        Args:
            media_path: Path to the media file
            media_type: Type of media (from CompareMediaType enum)
        """
        try:
            if media_type == CompareMediaType.PDF:
                cls._extract_pdf_frame(media_path)
            else:
                cls._extract_video_frame(media_path)
        except Exception as e:
            Utils.log(f"Error extracting frame from {media_path}: {str(e)}")
            # Fallback to original path if extraction fails
            cls.cache[media_path] = media_path

    @classmethod
    def _extract_pdf_frame(cls, pdf_path: str) -> None:
        """
        Extract the first page from a PDF as an image.

        Args:
            pdf_path: Path to the PDF file
        """
        try:
            Utils.log(f"Extracting first page from PDF: {pdf_path}")
            pdf = pdfium.PdfDocument(pdf_path)
            if len(pdf) > 0:
                page = pdf[0]
                # Use a higher scale for better quality
                image = page.render(scale=4).to_pil()
                
                basename = os.path.splitext(os.path.basename(pdf_path))[0] + ".jpg"
                frame_path = os.path.join(cls.temporary_directory.name, basename)
                
                image.save(frame_path, quality=95)
                cls.cache[pdf_path] = frame_path
            else:
                raise ValueError("PDF has no pages")
        except Exception as e:
            Utils.log(f"Error processing PDF {pdf_path}: {str(e)}")
            raise

    @classmethod
    def _extract_video_frame(cls, video_path: str) -> None:
        """
        Extract the first frame from a video/GIF file.

        Args:
            video_path: Path to the video/GIF file
        """
        Utils.log(f"Extracting first frame from video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        try:
            ret, frame = cap.read()
            if not ret:
                raise ValueError("Could not read the first frame")

            basename = os.path.splitext(os.path.basename(video_path))[0] + ".jpg"
            frame_path = os.path.join(cls.temporary_directory.name, basename)
            
            # Use high quality JPEG compression
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cls.cache[video_path] = frame_path
        finally:
            cap.release()

    @classmethod
    def clear(cls) -> None:
        """Clear the frame cache."""
        cls.cache.clear()

    @classmethod
    def cleanup(cls) -> None:
        """Clean up temporary files and directory."""
        cls.clear()
        cls.temporary_directory.cleanup()
        cls.temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")

