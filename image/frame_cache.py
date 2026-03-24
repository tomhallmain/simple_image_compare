import os
import tempfile
import asyncio
from typing import Dict, Iterator, List, Optional, Tuple

import cv2
import numpy as np

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
from utils.logging_setup import get_logger
from utils.constants import CompareMediaType

logger = get_logger("frame_cache")

# Bumps sample cache keys when extraction semantics change (invalidates in-memory entries).
_VIDEO_SAMPLE_CACHE_REV = "seqff2"


def _open_video_capture(path: str) -> cv2.VideoCapture:
    """
    Prefer FFmpeg backend for file-backed video; default (e.g. MSMF on Windows) often
    mishandles H.264/HEVC seek and returns blank frames after CAP_PROP_POS_FRAMES.
    """
    apis: List[int] = []
    ff = getattr(cv2, "CAP_FFMPEG", None)
    if ff is not None:
        apis.append(int(ff))
    any_api = getattr(cv2, "CAP_ANY", 0)
    if any_api not in apis:
        apis.append(int(any_api))

    last_cap: Optional[cv2.VideoCapture] = None
    for api in apis:
        cap = cv2.VideoCapture(path, api)
        last_cap = cap
        if cap.isOpened():
            return cap
    return last_cap if last_cap is not None else cv2.VideoCapture(path)


def _is_likely_decoder_blank(frame: np.ndarray) -> bool:
    """
    Detect near-uniform black frames that commonly appear when random frame seek fails
    but decode still "succeeds". Deliberately ignores legitimately very dark scenes by
    requiring simultaneously low mean, low variance, and low channel peaks.
    """
    if frame is None or frame.size == 0:
        return True
    if frame.ndim < 2:
        return True
    gray = frame if frame.ndim == 2 else cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_m = cv2.mean(gray)[0]
    _, stddev = cv2.meanStdDev(gray)
    std_m = float(stddev[0, 0])
    peak = float(np.max(gray))
    return peak < 6.0 and mean_m < 2.5 and std_m < 3.0


def _first_substantive_frame(
    cap: cv2.VideoCapture, max_frames: int = 360
) -> Tuple[bool, Optional[np.ndarray]]:
    """Read forward until the first non-blank frame or EOF. Used for first-frame thumbnail."""
    for _ in range(max(1, max_frames)):
        ret, frame = cap.read()
        if not ret or frame is None:
            return False, None
        if not _is_likely_decoder_blank(frame):
            return True, frame
    return False, None


class FrameCache:
    """
    A cache for extracting and storing the first frame from various media types (videos, GIFs, PDFs, SVGs, HTMLs).
    This helps improve performance by avoiding repeated frame extraction operations.

    TODO support getting an "average" frame from a video, or at least an average embedding
    TODO(GC): Implement bounded cache eviction / periodic cleanup for sampled
    dynamic-media frames. Current sampled cache can grow large with many media
    files and high sampling limits.
    """
    temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")
    cache: Dict[str, str] = {}  # Maps media_path to cached image path
    sampled_cache: Dict[str, List[str]] = {}  # Maps media_path|sample_ratio to sampled frame paths
    media_stats_cache: Dict[str, Dict[str, Optional[float]]] = {}  # Maps media_path to lightweight stats

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
            logger.error(f"Error extracting frame from {media_path}: {str(e)}")
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
            logger.info(f"Extracting first page from PDF: {pdf_path}")
            pdf = pdfium.PdfDocument(pdf_path)
            if len(pdf) > 0:
                cls.media_stats_cache[pdf_path] = {
                    "media_type": "pdf",
                    "total_items": len(pdf),
                    "duration_seconds": None,
                    "fps": None,
                }
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
            logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
            raise

    @classmethod
    def _extract_svg_frame(cls, svg_path: str) -> None:
        """
        Convert an SVG file to a PNG image.

        Args:
            svg_path: Path to the SVG file
        """
        try:
            logger.info(f"Converting SVG to PNG: {svg_path}")
            basename = os.path.splitext(os.path.basename(svg_path))[0] + ".png"
            frame_path = os.path.join(cls.temporary_directory.name, basename)
            
            # Convert SVG to PNG using cairosvg
            cairosvg.svg2png(url=svg_path, write_to=frame_path)
            cls.cache[svg_path] = frame_path
        except Exception as e:
            logger.error(f"Error processing SVG {svg_path}: {str(e)}")
            raise

    @classmethod
    def _extract_html_frame(cls, html_path: str) -> None:
        """
        Convert an HTML file to a PDF and then extract its first page as an image.

        Args:
            html_path: Path to the HTML file
        """
        try:
            logger.info(f"Converting HTML to image: {html_path}")
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
            logger.error(f"Error processing HTML {html_path}: {str(e)}")
            raise

    @classmethod
    def _extract_video_frame(cls, video_path: str) -> None:
        """
        Extract the first frame from a video/GIF file.

        Args:
            video_path: Path to the video/GIF file
        """
        logger.info(f"Extracting first frame from video: {video_path}")
        cap = _open_video_capture(video_path)
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            duration_seconds = None
            if fps and fps > 0 and total_frames > 0:
                duration_seconds = total_frames / fps
            cls.media_stats_cache[video_path] = {
                "media_type": "video",
                "total_items": total_frames if total_frames > 0 else None,
                "duration_seconds": duration_seconds,
                "fps": fps if fps > 0 else None,
            }
            ok, frame = _first_substantive_frame(cap)
            if not ok or frame is None:
                raise ValueError("Could not read a substantive frame from the video")

            basename = os.path.splitext(os.path.basename(video_path))[0] + ".jpg"
            frame_path = os.path.join(cls.temporary_directory.name, basename)
            
            # Use high quality JPEG compression
            cv2.imwrite(frame_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cls.cache[video_path] = frame_path
        finally:
            cap.release()

    @classmethod
    def stream_frame_samples(
        cls, media_path: str, sample_ratio: float = 0.1
    ) -> Tuple[int, Iterator[str]]:
        """
        Lazily produce sampled frame paths for video/GIF/PDF (or a single still path).

        Returns ``(planned_slot_count, iterator)``. *planned_slot_count* is the number
        of sampling slots (``len(frame_indices)`` or ``1`` for fallback), used for
        early-exit thresholds before all frames are decoded. The iterator decodes,
        writes JPEGs, and yields paths one at a time so consumers can stop early.

        On full consumption, results are stored in ``sampled_cache`` (same as
        :meth:`get_frame_samples`). If the consumer stops early, the partial result
        is not cached.

        Falls back to ``get_image_path`` for non-dynamic media.
        """
        media_path_lower = media_path.lower()
        is_video = config.enable_videos and any(
            media_path_lower.endswith(ext) for ext in config.video_types
        )
        is_pdf = media_path_lower.endswith(".pdf") and config.enable_pdfs and has_imported_pypdfium2
        if not is_video and not is_pdf:
            p = cls.get_image_path(media_path)
            return 1, iter([p])

        try:
            ratio = float(sample_ratio)
        except Exception:
            ratio = 0.1
        ratio = max(0.0, min(1.0, ratio))
        min_sample_count = config.dynamic_media_min_sample_count
        max_sample_frames = config.dynamic_media_max_sample_frames
        max_sample_pages = config.dynamic_media_max_sample_pages
        cache_key = (
            f"{media_path}|{ratio:.4f}|min:{min_sample_count}"
            f"|maxf:{max_sample_frames}|maxp:{max_sample_pages}|{_VIDEO_SAMPLE_CACHE_REV}"
        )

        if cache_key in cls.sampled_cache:
            cached = cls.sampled_cache[cache_key]
            return len(cached), iter(cached)

        if is_video:
            return cls._stream_video_frame_samples(
                media_path,
                ratio,
                min_sample_count=min_sample_count,
                max_sample_count=max_sample_frames,
                cache_key=cache_key,
            )
        return cls._stream_pdf_sample_pages(
            media_path,
            ratio,
            min_sample_count=min_sample_count,
            max_sample_count=max_sample_pages,
            cache_key=cache_key,
        )

    @classmethod
    def get_frame_samples(cls, media_path: str, sample_ratio: float = 0.1) -> List[str]:
        """
        Get sampled frame image paths for dynamic media (currently video/GIF/PDF).

        Materializes :meth:`stream_frame_samples` (full decode). Falls back to
        ``get_image_path`` when sampling is not applicable or fails.
        """
        _, path_iter = cls.stream_frame_samples(media_path, sample_ratio)
        sampled_paths = list(path_iter)
        media_path_lower = media_path.lower()
        is_video = config.enable_videos and any(
            media_path_lower.endswith(ext) for ext in config.video_types
        )
        is_pdf = media_path_lower.endswith(".pdf") and config.enable_pdfs and has_imported_pypdfium2
        if len(sampled_paths) == 0 and (is_video or is_pdf):
            sampled_paths = [media_path]
            try:
                ratio = float(sample_ratio)
            except Exception:
                ratio = 0.1
            ratio = max(0.0, min(1.0, ratio))
            min_sample_count = config.dynamic_media_min_sample_count
            max_sample_frames = config.dynamic_media_max_sample_frames
            max_sample_pages = config.dynamic_media_max_sample_pages
            cache_key = (
                f"{media_path}|{ratio:.4f}|min:{min_sample_count}"
                f"|maxf:{max_sample_frames}|maxp:{max_sample_pages}|{_VIDEO_SAMPLE_CACHE_REV}"
            )
            cls.sampled_cache[cache_key] = sampled_paths
        return sampled_paths

    @classmethod
    def _stream_video_frame_samples(
        cls,
        video_path: str,
        sample_ratio: float,
        min_sample_count: int,
        max_sample_count: int,
        cache_key: str,
    ) -> Tuple[int, Iterator[str]]:
        cap = _open_video_capture(video_path)
        try:
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            duration_seconds = None
            if fps and fps > 0 and total_frames > 0:
                duration_seconds = total_frames / fps
            cls.media_stats_cache[video_path] = {
                "media_type": "video",
                "total_items": total_frames if total_frames > 0 else None,
                "duration_seconds": duration_seconds,
                "fps": fps if fps > 0 else None,
            }
            frame_indices = cls._compute_sample_indices(
                total_items=total_frames,
                sample_ratio=sample_ratio,
                min_sample_count=min_sample_count,
                max_sample_count=max_sample_count,
            )
        except Exception as e:
            logger.warning(f"Error extracting sampled frames from {video_path}: {e}")
            try:
                cap.release()
            except Exception:
                pass

            def gen_video_fail() -> Iterator[str]:
                cls.sampled_cache[cache_key] = [video_path]
                yield video_path

            return 1, gen_video_fail()

        if len(frame_indices) == 0:
            cap.release()

            def gen_empty() -> Iterator[str]:
                cls.sampled_cache[cache_key] = [video_path]
                yield video_path

            return 1, gen_empty()

        basename = os.path.splitext(os.path.basename(video_path))[0]
        planned = len(frame_indices)

        def gen() -> Iterator[str]:
            accumulated: List[str] = []
            completed = False
            try:
                yield from cls._iter_video_sample_paths_sequential(
                    cap,
                    video_path,
                    frame_indices,
                    basename,
                    accumulated,
                )
                if len(accumulated) == 0:
                    accumulated.append(video_path)
                    yield video_path
                completed = True
            finally:
                cap.release()
                if completed:
                    cls.sampled_cache[cache_key] = accumulated

        return planned, gen()

    @classmethod
    def _iter_video_sample_paths_sequential(
        cls,
        cap: cv2.VideoCapture,
        video_path: str,
        frame_indices: List[int],
        basename: str,
        accumulated: List[str],
    ) -> Iterator[str]:
        """
        Decode target frames by linear read only; write each JPEG and yield its path.
        Appends each path to *accumulated* (same list the outer generator caches).
        """
        targets = sorted(set(frame_indices))
        want = set(targets)
        idx = 0
        max_target = max(targets)
        total_reported = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        scan_limit = max(
            max_target + 10_000,
            total_reported + 5000 if total_reported > 0 else max_target + 5000,
            len(targets) * 200,
        )
        scan_limit = min(scan_limit, 800_000)
        lookahead_cap = 128

        while want and idx < scan_limit:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            if idx not in want:
                idx += 1
                continue

            chosen: Optional[np.ndarray] = None
            extra = 0
            if not _is_likely_decoder_blank(frame):
                chosen = frame
            else:
                for _ in range(lookahead_cap):
                    r2, f2 = cap.read()
                    extra += 1
                    if not r2 or f2 is None:
                        break
                    if not _is_likely_decoder_blank(f2):
                        chosen = f2
                        break

            if chosen is not None:
                frame_path = os.path.join(
                    cls.temporary_directory.name,
                    f"{basename}_sample_{idx}.jpg",
                )
                cv2.imwrite(frame_path, chosen, [cv2.IMWRITE_JPEG_QUALITY, 95])
                accumulated.append(frame_path)
                yield frame_path
            else:
                logger.debug(
                    "Degenerate sampled frame at index %s for %s (skipped)",
                    idx,
                    video_path,
                )
            want.discard(idx)
            idx += 1 + extra

        if want:
            logger.warning(
                "Video sampling incomplete for %s — missing %s/%s indices (decoder ended or scan cap)",
                video_path,
                len(want),
                len(targets),
            )

    @classmethod
    def get_dynamic_media_stats(cls, media_path: str) -> Dict[str, Optional[float]]:
        """
        Return lightweight metadata useful for debug logging.

        Keys:
            - media_type: "video", "pdf", or "other"
            - total_items: total frames/pages when known
            - duration_seconds: video duration when available, else None
            - fps: video fps when available, else None
        """
        if media_path in cls.media_stats_cache:
            return cls.media_stats_cache[media_path]

        return {
            "media_type": "other",
            "total_items": None,
            "duration_seconds": None,
            "fps": None,
        }

    @classmethod
    def _stream_pdf_sample_pages(
        cls,
        pdf_path: str,
        sample_ratio: float,
        min_sample_count: int,
        max_sample_count: int,
        cache_key: str,
    ) -> Tuple[int, Iterator[str]]:
        pdf = None
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            total_pages = len(pdf)
            cls.media_stats_cache[pdf_path] = {
                "media_type": "pdf",
                "total_items": total_pages,
                "duration_seconds": None,
                "fps": None,
            }
            page_indices = cls._compute_sample_indices(
                total_items=total_pages,
                sample_ratio=sample_ratio,
                min_sample_count=min_sample_count,
                max_sample_count=max_sample_count,
            )
        except Exception as e:
            logger.warning(f"Error opening PDF for sampling {pdf_path}: {e}")
            if pdf is not None:
                try:
                    pdf.close()
                except Exception:
                    pass

            def gen_open_fail() -> Iterator[str]:
                cls.sampled_cache[cache_key] = [pdf_path]
                yield pdf_path

            return 1, gen_open_fail()

        if len(page_indices) == 0:
            try:
                pdf.close()
            except Exception:
                pass

            def gen_no_pages() -> Iterator[str]:
                cls.sampled_cache[cache_key] = [pdf_path]
                yield pdf_path

            return 1, gen_no_pages()

        basename = os.path.splitext(os.path.basename(pdf_path))[0]
        planned = len(page_indices)
        pdf_ref = pdf

        def gen() -> Iterator[str]:
            accumulated: List[str] = []
            completed = False
            try:
                for page_index in page_indices:
                    page = pdf_ref[page_index]
                    image = page.render(scale=4).to_pil()
                    page_path = os.path.join(
                        cls.temporary_directory.name,
                        f"{basename}_sample_page_{page_index}.jpg",
                    )
                    image.save(page_path, quality=95)
                    accumulated.append(page_path)
                    yield page_path
                if len(accumulated) == 0:
                    accumulated.append(pdf_path)
                    yield pdf_path
                completed = True
            except Exception as e:
                logger.warning(f"Error extracting sampled PDF pages from {pdf_path}: {e}")
            finally:
                try:
                    pdf_ref.close()
                except Exception:
                    pass
                if completed:
                    cls.sampled_cache[cache_key] = accumulated

        return planned, gen()

    @staticmethod
    def _compute_sample_indices(
        total_items: int,
        sample_ratio: float,
        min_sample_count: int,
        max_sample_count: int,
    ) -> List[int]:
        if total_items <= 0:
            return []
        sample_count = max(1, int(total_items * sample_ratio))
        sample_count = max(sample_count, max(1, min_sample_count))
        sample_count = min(sample_count, max(1, max_sample_count))
        sample_count = min(sample_count, total_items)
        step = max(1, total_items // sample_count)
        indices = list(range(0, total_items, step))[:sample_count]
        if len(indices) == 0:
            return [0]
        return indices

    @classmethod
    def get_cached_path(cls, media_path: str) -> Optional[str]:
        """
        Return the cached temp path for a media file (e.g. SVG -> PNG path), if any.
        Returns None if the media is not in the cache or is not a type that uses a temp file.
        """
        return cls.cache.get(media_path)

    @classmethod
    def get_media_path_for_cached(cls, maybe_cached_path: str) -> Optional[str]:
        """
        Resolve a cached frame/page path back to the original media path.

        Returns:
            The original media path if *maybe_cached_path* is known in the cache,
            otherwise None.
        """
        if not maybe_cached_path:
            return None
        for media_path, cached_path in cls.cache.items():
            if cached_path == maybe_cached_path:
                return media_path
        for key, sampled_paths in cls.sampled_cache.items():
            for sampled_path in sampled_paths:
                if sampled_path == maybe_cached_path:
                    media_path = key.split("|", 1)[0]
                    return media_path
        return None

    @classmethod
    def remove_from_cache(cls, media_path: str, delete_temp_file: bool = False) -> None:
        """
        Remove a media path from the cache. If it had a temp file (e.g. generated PNG for SVG),
        optionally delete that temp file from disk. Call this before moving/deleting the source
        file so the temp file is not left behind and no handles are held.
        """
        temp_path = cls.cache.pop(media_path, None)
        cls.media_stats_cache.pop(media_path, None)
        if delete_temp_file and temp_path and os.path.isfile(temp_path):
            try:
                os.remove(temp_path)
                logger.debug(f"Removed cached temp file: {temp_path}")
            except OSError as e:
                logger.warning(f"Could not remove cached temp file {temp_path}: {e}")
        sampled_keys = [k for k in cls.sampled_cache.keys() if k.startswith(f"{media_path}|")]
        for key in sampled_keys:
            sampled_paths = cls.sampled_cache.pop(key, [])
            if delete_temp_file:
                for sampled_path in sampled_paths:
                    if sampled_path and os.path.isfile(sampled_path):
                        try:
                            os.remove(sampled_path)
                        except OSError as e:
                            logger.warning(f"Could not remove sampled cache file {sampled_path}: {e}")

    @classmethod
    def clear(cls) -> None:
        """Clear the frame cache."""
        cls.cache.clear()
        cls.sampled_cache.clear()
        cls.media_stats_cache.clear()

    @classmethod
    def cleanup(cls) -> None:
        """Clean up temporary files and directory."""
        cls.clear()
        cls.temporary_directory.cleanup()
        cls.temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")

