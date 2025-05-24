import os
import tempfile
import asyncio
from typing import Dict

import cv2

has_imported_pypdfium2 = False
try:
    import pypdfium2 as pdfium
    has_imported_pypdfium2 = True
except ImportError:
    pass

has_imported_cairosvg = False
try:
    import cairosvg
    has_imported_cairosvg = True
except ImportError:
    pass

has_imported_pyppeteer = False
try:
    from pyppeteer import launch
    has_imported_pyppeteer = True
except ImportError:
    pass

from utils.config import config
from utils.utils import Utils
from utils.constants import CompareMediaType


class FrameCache:
    """
    A cache for extracting and storing the first frame from various media types (videos, GIFs, PDFs, SVGs, HTMLs).
    This helps improve performance by avoiding repeated frame extraction operations.

    TODO support getting an "average" frame from a video, or at least an average embedding
    """
    temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")
    cache: Dict[str, str] = {}  # Maps media_path to cached image path

    @classmethod
    def get_image_path(cls, media_path: str) -> str:
        """
        Get the image path for a media file. If it's a video/GIF/PDF/SVG/HTML, extracts the first frame.
        Otherwise returns the original path.

        Args:
            media_path: Path to the media file

        Returns:
            Path to the image file (either original or extracted frame)
        """
        media_path_lower = media_path.lower()

        # Check for SVG files first (since they're the simplest to convert)
        if media_path_lower.endswith('.svg'):
            if config.enable_svgs:
                if has_imported_cairosvg:
                    return cls.get_first_frame(media_path, CompareMediaType.SVG)
                else:
                    raise ImportError("Unable to convert SVG to PNG: cairosvg is not installed")
            else:
                return media_path

        # Check for PDF files next
        if media_path_lower.endswith('.pdf'):
            if config.enable_pdfs:
                if has_imported_pypdfium2:
                    return cls.get_first_frame(media_path, CompareMediaType.PDF)
                else:
                    raise ImportError("Unable to extract PDF frame: pypdfium2 is not installed")
            else:
                return media_path

        # Check for HTML files
        if media_path_lower.endswith('.html') or media_path_lower.endswith('.htm'):
            if config.enable_html:
                if has_imported_pyppeteer:
                    return cls.get_first_frame(media_path, CompareMediaType.HTML)
                else:
                    raise ImportError("Unable to convert HTML to image: pyppeteer is not installed")
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
            elif media_type == CompareMediaType.SVG:
                cls._extract_svg_frame(media_path)
            elif media_type == CompareMediaType.HTML:
                cls._extract_html_frame(media_path)
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
    def _extract_svg_frame(cls, svg_path: str) -> None:
        """
        Convert an SVG file to a PNG image.

        Args:
            svg_path: Path to the SVG file
        """
        try:
            Utils.log(f"Converting SVG to PNG: {svg_path}")
            basename = os.path.splitext(os.path.basename(svg_path))[0] + ".png"
            frame_path = os.path.join(cls.temporary_directory.name, basename)
            
            # Convert SVG to PNG using cairosvg
            cairosvg.svg2png(url=svg_path, write_to=frame_path)
            cls.cache[svg_path] = frame_path
        except Exception as e:
            Utils.log(f"Error processing SVG {svg_path}: {str(e)}")
            raise

    @classmethod
    def _extract_html_frame(cls, html_path: str) -> None:
        """
        Convert an HTML file to a PDF and then extract its first page as an image.

        Args:
            html_path: Path to the HTML file
        """
        try:
            Utils.log(f"Converting HTML to image: {html_path}")
            # First convert HTML to PDF
            pdf_path = os.path.join(cls.temporary_directory.name, 
                                  os.path.splitext(os.path.basename(html_path))[0] + ".pdf")
            
            # Convert HTML to PDF using Pyppeteer
            async def convert_html_to_pdf():
                browser = await launch(headless=True)
                page = await browser.newPage()
                
                # Read the HTML file
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                # Set the content and wait for network idle
                await page.setContent(html_content, {'waitUntil': 'networkidle0'})
                
                # Generate PDF with good quality settings
                await page.pdf({
                    'path': pdf_path,
                    'format': 'A4',
                    'printBackground': True,
                    'margin': {
                        'top': '0',
                        'right': '0',
                        'bottom': '0',
                        'left': '0'
                    }
                })
                
                await browser.close()
            
            # Run the async function
            asyncio.get_event_loop().run_until_complete(convert_html_to_pdf())
            
            # Now extract the first page as an image using our existing PDF extraction
            cls._extract_pdf_frame(pdf_path)
            
            # Update cache to point to the HTML file instead of the temporary PDF
            cls.cache[html_path] = cls.cache[pdf_path]
            del cls.cache[pdf_path]
            
        except Exception as e:
            Utils.log(f"Error processing HTML {html_path}: {str(e)}")
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

