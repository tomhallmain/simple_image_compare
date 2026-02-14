import os

from PIL import Image
import pypdfium2 as pdfium

from image.frame_cache import FrameCache
from utils.logging_setup import get_logger
from utils.translations import I18N

_ = I18N._
logger = get_logger("pdf_creator")


class PDFCreator:
    """
    Handles creation of PDFs from various file types.
    Each file will be added as a page in the PDF.
    Images will be added directly, while other file types will be converted to images first.
    """
    
    @staticmethod
    def create_pdf_from_files(file_paths, app_actions, output_path=None, options=None,
                              save_file_callback=None):
        """
        Create a PDF from a list of files. Each file will be added as a page in the PDF.
        
        Args:
            file_paths: List of file paths to include in the PDF
            app_actions: AppActions instance for UI feedback
            output_path: Optional path to save the PDF. If None, will prompt user
                         via *save_file_callback*.
            options: Dictionary of PDF creation options:
                - preserve_quality: If True, maintain original image quality and format
                                  If False, compress images to reduce PDF size
                - filename: Base filename for the PDF
            save_file_callback: A callable(default_dir, default_name) -> str|None
                that shows a "Save As" dialog and returns the chosen path, or
                None if the user cancelled.  Required when *output_path* is None.
            
        Returns:
            bool: True if PDF was created successfully, False otherwise
        """
        if not file_paths:
            app_actions.toast(_("No files to create PDF"))
            return False

        if output_path is None:
            # Get the directory of the first file
            default_dir = os.path.dirname(file_paths[0])
            
            # Use the filename from options if provided, otherwise use default
            combined_images = _('combined_images')
            default_name = options.get('filename', combined_images) if options else combined_images
            
            if save_file_callback is None:
                logger.error("save_file_callback is required when output_path is not provided")
                return False
            output_path = save_file_callback(default_dir, default_name)
            if not output_path:
                return False

        try:
            # Create a new PDF document
            pdf = pdfium.PdfDocument.new()
            successful_pages = 0
            
            for file_path in file_paths:
                try:
                    # Get image path (handles conversion of various file types)
                    image_path = FrameCache.get_image_path(file_path)
                    
                    # Create a new image object in the PDF
                    image_obj = pdfium.PdfImage.new(pdf)
                    
                    # Check if it's a JPEG
                    if image_path.lower().endswith(('.jpg', '.jpeg')):
                        # For JPEGs, we can load directly
                        image_obj.load_jpeg(image_path, inline=True)
                    else:
                        # For other formats, convert using PIL
                        with Image.open(image_path) as img:
                            if options and not options.get('preserve_quality', True):
                                # Compressed mode - convert to JPEG with reduced quality
                                if img.mode in ('RGBA', 'LA'):
                                    background = Image.new('RGB', img.size, (255, 255, 255))
                                    background.paste(img, mask=img.split()[-1])
                                    img = background
                                elif img.mode != 'RGB':
                                    img = img.convert('RGB')
                                # Create a temporary file for the compressed image
                                temp_path = os.path.join(os.path.dirname(output_path), f"temp_{os.path.basename(image_path)}")
                                try:
                                    img.save(temp_path, format='JPEG', quality=85)
                                    image_obj.load_jpeg(temp_path, inline=True)
                                finally:
                                    # Ensure temp file is cleaned up even if an error occurs
                                    if os.path.exists(temp_path):
                                        try:
                                            os.remove(temp_path)
                                        except Exception as e:
                                            logger.error(f"Error cleaning up temp file {temp_path}: {str(e)}")
                            else:
                                # Quality preservation mode - use PIL to convert to bitmap
                                bitmap = pdfium.PdfBitmap.from_pil(img)
                                image_obj.set_bitmap(bitmap)
                                bitmap.close()
                    
                    # Get image dimensions and create page
                    w, h = image_obj.get_size()
                    image_obj.set_matrix(pdfium.PdfMatrix().scale(w, h))
                    page = pdf.new_page(w, h)
                    page.insert_obj(image_obj)
                    page.gen_content()
                    
                    # Clean up
                    image_obj.close()
                    page.close()
                    successful_pages += 1
                        
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {str(e)}")
                    continue

            if successful_pages > 0:
                # Save the PDF
                pdf.save(output_path)
                pdf.close()
                mode = _("compressed") if options and not options.get('preserve_quality', True) else _("high quality")
                app_actions.success(_("Created {0} PDF with {1} pages").format(mode, successful_pages))
                return True
            else:
                app_actions.alert(_("Error"), _("No pages could be added to the PDF"), kind="error")
                return False
            
        except ImportError:
            app_actions.alert(_("Error"), _("PDF creation requires pypdfium2 package"), kind="error")
            return False
        except Exception as e:
            app_actions.alert(_("Error"), str(e), kind="error")
            return False 