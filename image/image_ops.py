import os
import random
import sys

import cv2
import numpy as np

from PIL import Image, ImageDraw, ImageEnhance
import PIL.Image

from utils.config import config
from utils.logging_setup import get_logger
from extensions.gimp.gimp_gegl_client import GimpGeglClient

logger = get_logger("image_ops")


class ImageOps:
    COLORS = ["red", "green", "blue", "yellow", "purple", "orange", "black", "white", "gray", "pink", "brown"]
    
    # Class-level cache for GEGL validation
    _gegl_validation_cache = None

    @staticmethod
    def new_filepath(image_path: str, new_filename: str = "", append_part: str | None = None) -> str:
        dirname = os.path.dirname(image_path)
        if new_filename == "" or append_part is not None:
            basename = os.path.basename(image_path)
            filename_part, ext = os.path.splitext(basename)
            if append_part is not None:
                new_filename = filename_part + append_part + ext
            else:
                new_filename = filename_part + "_crop" + ext
        new_filepath = os.path.join(dirname, new_filename)
        return new_filepath

    @staticmethod
    def rotate_image(image_path, right=False):
        try:
            #loading the image into a numpy array 
            img = cv2.imread(image_path)
            #rotating the image
            if right:
                rotated = np.rot90(img, k=-1)
            else:
                rotated = np.rot90(img, k=1)

            current_extension = os.path.splitext(image_path)[-1]
            new_filepath = ImageOps.new_filepath(image_path, append_part="_rot")
            cv2.imwrite(new_filepath, rotated)
            return new_filepath
        except Exception as e:
            logger.error(f'Error in rotate image: {e}')
            return None

    @staticmethod
    def rotate_image_partial(image_path, angle=90, center=None, scale=1.0, texture_probability=0.75):
        """
        Rotate image with random texture or solid color background.
        
        Args:
            image_path: Path to the image file
            angle: Rotation angle in degrees
            center: Rotation center point (defaults to image center)
            scale: Scale factor for rotation
            texture_probability: Probability of using texture (0.0-1.0, default 0.75)
        """
        image = cv2.imread(image_path)
        
        # Randomly decide whether to use texture based on probability
        use_texture = random.random() < texture_probability
        
        rotated = ImageOps._rotate_image_partial(image, angle=angle, center=center, scale=scale, use_texture=use_texture)
        new_filepath = ImageOps.new_filepath(image_path, append_part="_rot")
        cv2.imwrite(new_filepath, rotated)
        image.close()

    @staticmethod
    def get_random_color(true_random_chance=0.75):
        if random.random() < true_random_chance:
            return tuple([random.randint(0, 255) for i in range(3)])
        else:
            return (0, 0, 0) if random.random() > 0.5 else (255, 255, 255)

    @staticmethod
    def generate_noise_texture(width, height, texture_type="perlin"):
        """Generate various types of random textures for background filling."""
        if texture_type == "perlin":
            return ImageOps._generate_perlin_noise(width, height)
        elif texture_type == "gaussian":
            return ImageOps._generate_gaussian_noise(width, height)
        elif texture_type == "gradient":
            return ImageOps._generate_gradient_texture(width, height)
        elif texture_type == "cellular":
            return ImageOps._generate_cellular_texture(width, height)
        else:
            # Default to solid color if unknown type
            return ImageOps._generate_solid_color(width, height)

    @staticmethod
    def _generate_perlin_noise(width, height):
        """Generate Perlin-like noise texture using OpenCV."""
        # Create multiple octaves of noise
        texture = np.zeros((height, width, 3), dtype=np.uint8)
        
        for octave in range(3):
            scale = 2 ** octave
            noise = np.random.rand(height // scale, width // scale, 3) * 255
            noise_resized = cv2.resize(noise, (width, height), interpolation=cv2.INTER_LINEAR)
            texture = cv2.addWeighted(texture, 0.7, noise_resized.astype(np.uint8), 0.3, 0)
        
        return texture

    @staticmethod
    def _generate_gaussian_noise(width, height):
        """Generate Gaussian noise texture."""
        # Generate noise with controlled variance
        noise = np.random.normal(128, 50, (height, width, 3))
        noise = np.clip(noise, 0, 255).astype(np.uint8)
        return noise

    @staticmethod
    def _generate_gradient_texture(width, height):
        """Generate radial or linear gradient texture."""
        texture = np.zeros((height, width, 3), dtype=np.uint8)
        
        if random.random() > 0.5:
            # Radial gradient
            center_x, center_y = width // 2, height // 2
            y, x = np.ogrid[:height, :width]
            distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            max_distance = np.sqrt(center_x**2 + center_y**2)
            gradient = (distance / max_distance * 255).astype(np.uint8)
            
            # Apply random color tinting
            color = ImageOps.get_random_color()
            for i in range(3):
                texture[:, :, i] = (gradient * color[i] / 255).astype(np.uint8)
        else:
            # Linear gradient
            direction = random.choice(['horizontal', 'vertical', 'diagonal'])
            if direction == 'horizontal':
                gradient = np.linspace(0, 255, width)
                gradient = np.tile(gradient, (height, 1))
            elif direction == 'vertical':
                gradient = np.linspace(0, 255, height)
                gradient = np.tile(gradient, (width, 1)).T
            else:  # diagonal
                gradient = np.zeros((height, width))
                for i in range(height):
                    for j in range(width):
                        gradient[i, j] = ((i + j) / (height + width)) * 255
            
            # Apply random color tinting
            color = ImageOps.get_random_color()
            for i in range(3):
                texture[:, :, i] = (gradient * color[i] / 255).astype(np.uint8)
        
        return texture

    @staticmethod
    def _generate_cellular_texture(width, height):
        """Generate cellular/Voronoi-like texture."""
        # Create random points
        num_points = random.randint(5, 15)
        points = np.random.rand(num_points, 2) * [width, height]
        
        # Create distance map
        y, x = np.ogrid[:height, :width]
        texture = np.zeros((height, width, 3), dtype=np.uint8)
        
        for i in range(height):
            for j in range(width):
                distances = np.sqrt((points[:, 0] - j)**2 + (points[:, 1] - i)**2)
                min_dist = np.min(distances)
                # Normalize and apply color
                intensity = int((min_dist / max(width, height)) * 255)
                color = ImageOps.get_random_color()
                texture[i, j] = [int(c * intensity / 255) for c in color]
        
        return texture

    @staticmethod
    def _generate_solid_color(width, height):
        """Generate solid color texture (fallback)."""
        color = ImageOps.get_random_color()
        texture = np.full((height, width, 3), color, dtype=np.uint8)
        return texture

    @staticmethod
    def get_random_texture_type():
        """Get a random texture type for variety."""
        texture_types = ["perlin", "gaussian", "gradient", "cellular"]
        return random.choice(texture_types)

    @staticmethod
    def _rotate_image_partial(image, angle=90, center=None, scale=1.0, use_texture=True):
        # grab the dimensions of the image
        (h, w) = image.shape[:2]
        # if the center is None, initialize it as the center of the image
        if center is None:
            center = (w // 2, h // 2)
        
        if use_texture:
            # Create a background texture
            texture_type = ImageOps.get_random_texture_type()
            background_texture = ImageOps.generate_noise_texture(w, h, texture_type)
            
            # Perform rotation with transparent border (we'll handle the background ourselves)
            M = cv2.getRotationMatrix2D(center, angle, scale)
            rotated = cv2.warpAffine(image, M, (w, h),
                                   borderMode=cv2.BORDER_TRANSPARENT)
            
            # Create a mask to identify the transparent areas (where the original image wasn't)
            # We'll use a different approach: rotate a white image to create a mask
            white_image = np.ones((h, w, 3), dtype=np.uint8) * 255
            rotated_mask = cv2.warpAffine(white_image, M, (w, h),
                                        borderMode=cv2.BORDER_CONSTANT,
                                        borderValue=(0, 0, 0))
            
            # Convert mask to grayscale and normalize
            mask_gray = cv2.cvtColor(rotated_mask, cv2.COLOR_BGR2GRAY)
            mask_normalized = mask_gray.astype(np.float32) / 255.0
            
            # Composite the rotated image with the background texture
            # Where mask is 1 (original image), use rotated image
            # Where mask is 0 (background), use texture
            result = np.zeros_like(image)
            for i in range(3):  # For each color channel
                result[:, :, i] = (rotated[:, :, i] * mask_normalized + 
                                 background_texture[:, :, i] * (1 - mask_normalized)).astype(np.uint8)
            
            return result
        else:
            # Original behavior with solid color
            M = cv2.getRotationMatrix2D(center, angle, scale)
            rotated = cv2.warpAffine(image, M, (w, h),
                                   borderMode=cv2.BORDER_CONSTANT,
                                   borderValue=ImageOps.get_random_color())
            return rotated

    @staticmethod
    def enhance_image(image_path):
        dirname = os.path.dirname(image_path)
        filename_parts = os.path.splitext(os.path.basename(image_path))
        new_filename = filename_parts[0] + "_b" + filename_parts[1]
        new_file = os.path.join(dirname, new_filename)
        if os.path.exists(new_file):
            raise Exception("File already exists: " + new_filename) # TODO maybe remove this
        image = PIL.Image.open(image_path)
        brightness_enhancer = ImageEnhance.Brightness(image)
        brightened = brightness_enhancer.enhance(1.3)
        image.close()
        image = brightened
        contrast_enhancer = ImageEnhance.Contrast(image)
        contrasted = contrast_enhancer.enhance(1.1)
        brightened.close()
        image = contrasted
        image.save(new_file)
        image.close()
        return new_file

    @staticmethod
    def flip_image(image_path, top_bottom=False):
        original_img = PIL.Image.open(image_path)
        mod_img, original_img = ImageOps._flip_image(original_img, top_bottom=top_bottom)
        new_filepath = ImageOps.new_filepath(image_path, append_part="_flip")
        mod_img.save(new_filepath)
        original_img.close()
        mod_img.close()
        return new_filepath

    @staticmethod
    def convert_to_jpg(image_path, quality=85):
        """
        Convert lossless image formats to JPG to reduce file size.
        Preserves original dimensions and removes EXIF data.
        
        Args:
            image_path: Path to the source image
            quality: JPG quality (1-100, default 85)
        """
        try:
            # Open the image
            image = PIL.Image.open(image_path)
            
            # Convert to RGB if necessary (JPG doesn't support alpha channel)
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create a white background for transparent images
                background = PIL.Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode in ('RGBA', 'LA') else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Create new filepath with .jpg extension
            new_filepath = ImageOps.new_filepath(image_path, append_part="")
            # Ensure the extension is .jpg
            base_path = os.path.splitext(new_filepath)[0]
            new_filepath = base_path + ".jpg"
            
            # Save as JPG without EXIF data
            image.save(new_filepath, 'JPEG', quality=quality, optimize=True)
            image.close()
            
            logger.info(f"Converted {image_path} to JPG: {new_filepath}")
            return new_filepath
            
        except Exception as e:
            logger.error(f"Error converting image to JPG: {e}")
            raise

    @staticmethod
    def _flip_image(im, top_bottom=False):
        return im.transpose(method=PIL.Image.FLIP_TOP_BOTTOM if top_bottom else PIL.Image.FLIP_LEFT_RIGHT), im

    @staticmethod
    def _upscale(im, shortest_side=1200):
        width, height = im.size
        if width > height:
            if height < shortest_side:
                im = im.resize((int(width * shortest_side / height), shortest_side))
        elif width < shortest_side:
            im = im.resize((shortest_side, int(height * shortest_side / width)))
        return im

    @staticmethod
    def _random_crop_and_upscale(im, allowable_proportions=0.4, shortest_side=1200):
        width, height = im.size
        landscape = width > height
        midpoint_x = int(width / 2)
        midpoint_y = int(height / 2)
        if landscape:
            allowable_range_x = midpoint_x * allowable_proportions * 2
            allowable_range_y = midpoint_y * allowable_proportions
        else:
            allowable_range_x = midpoint_x * allowable_proportions
            allowable_range_y = midpoint_y * allowable_proportions * 2
        x0 = int(allowable_range_x * random.random())
        x1 = int(width - (allowable_range_x * random.random()))
        y0 = int(allowable_range_y * random.random())
        y1 = int(height - (allowable_range_y * random.random()))
        bbox = (x0, y0, x1, y1)
        cropped = im.crop(bbox)
        return ImageOps._upscale(cropped, shortest_side)

    @staticmethod
    def random_crop_and_upscale(image_path, allowable_proportions=0.4, shortest_side=1200):
        im = PIL.Image.open(image_path)
        cropped = ImageOps._random_crop_and_upscale(im, allowable_proportions, shortest_side)
        im.close()
        new_filepath = ImageOps.new_filepath(image_path, append_part="_crop")
        cropped.save(new_filepath)
        return new_filepath

    @staticmethod
    def random_rotate_and_crop():
        pass

    @staticmethod
    def rotate_and_shear_image(im, angle=30, x_shear=.7, y_shear=.7):
        """
        Rotates an image (angle in degrees) and expands image to avoid cropping
        change from https://stackoverflow.com/a/51109152
        https://gist.github.com/hsuRush/b2def27c98ce7ba3eb84a42e6d01328c
        """
        #logger.debug(im.shape)
        height, width = im.shape[:2] # image shape has 3 dimensions
        image_center = (width/2, height/2) # getRotationMatrix2D needs coordinates in reverse order (width, height) compared to shape

        rotation_im = cv2.getRotationMatrix2D(image_center, angle, 1.)
        rotation_im[0,1] += x_shear
        rotation_im[1,0] += y_shear

        # rotation calculates the cos and sin, taking absolutes of those.
        abs_cos_x = abs(rotation_im[0,0]) 
        abs_sin_x = abs(rotation_im[0,1])
        abs_cos_y = abs(rotation_im[1,0]) 
        abs_sin_y = abs(rotation_im[1,1])

        # find the new width and height bounds
        bound_w = int(width * abs_cos_x +  height *  abs_sin_x )
        bound_h = int(height * abs_sin_y  + width * abs_cos_y )

        # subtract old image center (bringing image back to origo) and adding the new image center coordinates
        rotation_im[0, 2] += bound_w/2 - image_center[0] - image_center[1] * x_shear
        rotation_im[1, 2] += bound_h/2 - image_center[1] - image_center[0] * y_shear

        # rotate image with the new bounds and translated rotation imrix
        im = cv2.warpAffine(im, rotation_im, (bound_w, bound_h), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=ImageOps.get_random_color())
        im = cv2.resize(im, (width, height))

        #logger.debug(rotated_im.shape)
        return im

    @staticmethod
    def upscale(image_path):
        from cv2 import dnn_superres
        # Create an SR object
        sr = dnn_superres.DnnSuperResImpl_create()
        # Read image
        image = cv2.imread(image_path)
        # Read the desired model
        path = "EDSR_x3.pb"
        sr.readModel(path)
        # Set the desired model and scale to get correct pre- and post-processing
        sr.setModel("edsr", 3)
        # Upscale the image
        result = sr.upsample(image)
        new_filepath = ImageOps.new_filepath(image_path, append_part="_up")
        # Save the image
        cv2.imwrite(new_filepath, result)

    @staticmethod
    def randomly_modify_image(image_path):
        im = PIL.Image.open(image_path)
        has_modified_image = False
        while not has_modified_image:
            if random.random() < config.image_edit_configuration.random_rotation_chance:
                cv2_image = ImageOps.pil_to_cv2(im)
                angle_diff = int(random.random() * 55)
                angle = angle_diff if random.random() > 0.5 else 360 - angle_diff
                cv2_image = ImageOps._rotate_image_partial(cv2_image, angle=angle)
                im.close()
                im = ImageOps.cv2_to_pil(cv2_image)
                has_modified_image = True
            if random.random() < config.image_edit_configuration.random_flip_chance:
                im, original_im = ImageOps._flip_image(im)
                original_im.close()
                has_modified_image = True
            if random.random() < config.image_edit_configuration.random_shear_chance:
                cv2_image = ImageOps.pil_to_cv2(im)
                angle = random.randint(0, 25)
                x_shear = int(random.random() * 2 - 1)
                y_shear = int(random.random() * 2 - 1)
                cv2_image = ImageOps.rotate_and_shear_image(cv2_image, angle=angle, x_shear=x_shear, y_shear=y_shear)
                im.close()
                im = ImageOps.cv2_to_pil(cv2_image)
                temp_im = ImageOps._random_crop_and_upscale(im)
                im.close()
                im = temp_im
                has_modified_image = True
            if random.random() < config.image_edit_configuration.random_draw_chance:
                ImageOps._random_draw(im)
                has_modified_image = True
            if random.random() < config.image_edit_configuration.random_crop_chance:
                temp_im = ImageOps._random_crop_and_upscale(im)
                im.close()
                im = temp_im
                has_modified_image = True
        im_final = im
        if not has_modified_image:
            logger.warning("No modifications made to image!")
        new_filepath = ImageOps.new_filepath(image_path, append_part="_edit")
        im_final.save(new_filepath)
        im.close()
        try:
            im_final.close()
        except Exception:
            pass
        
        return new_filepath

    @staticmethod
    def random_draw(image_path):
        image = PIL.Image.open(image_path)
        ImageOps._random_draw(image)
        new_filepath = ImageOps.new_filepath(image_path, append_part="_drawn")
        image.save(new_filepath)
        image.close()

    @staticmethod
    def _random_draw(image):
        draw = ImageDraw.Draw(image)
        for i in range(random.randint(1, 5)):
            choice = random.randint(0, 4)
            if choice == 0:
                ImageOps._arc(image, draw)
            elif choice == 1:
                ImageOps._line(image, draw)
            elif choice == 2:
                ImageOps._chord(image, draw)

    @staticmethod
    def _color():
        return random.choice(ImageOps.COLORS)

    @staticmethod
    def _opacity():
        return random.uniform(0.5, 1.0)

    @staticmethod
    def _line(image, image_draw):
        if random.randint(0, 1) == 0:
            for i in range(0, 100, 20):
                image_draw.line((i, 0) + image.size, width=random.randint(2, 20), fill=ImageOps._color())
        else:
            points = []
            for i in range(random.randint(2, 4)):
                points.append((random.randint(0, image.size[0]), random.randint(0, image.size[1])))
            image_draw.line(points, width=random.randint(2, 40), fill=ImageOps._color(), joint="curve")

    @staticmethod
    def _arc(image, image_draw):
        for i in range(random.randint(1, 5)):
            start = random.randint(0, image.size[0])
            end = random.randint(start, image.size[0])            
            start0 = random.randint(0, image.size[0])
            end0 = random.randint(start0, image.size[0])
            start1 = random.randint(0, image.size[1])
            end1 = random.randint(start1, image.size[1])
            bounds = (start0, start1, end0, end1)
            image_draw.arc(bounds, start=start, end=end, fill=ImageOps._color(), width=random.randint(2, 40))

    @staticmethod
    def _chord(image, image_draw):
        for i in range(random.randint(1, 5)):
            start = random.randint(0, image.size[0])
            end = random.randint(start, image.size[0])            
            start0 = random.randint(0, image.size[0])
            end0 = random.randint(start0, image.size[0])
            start1 = random.randint(0, image.size[1])
            end1 = random.randint(start1, image.size[1])
            bounds = (start0, start1, end0, end1)
            image_draw.chord(bounds, start=start, end=end, fill=ImageOps._color(), outline=ImageOps._color(), width=random.randint(2, 40))

    @staticmethod
    def pil_to_cv2(pil_image):
        # use numpy to convert the pil_image into a numpy array
        numpy_image = np.array(pil_image)
        # convert to a openCV2 image, notice the COLOR_RGB2BGR which means that
        # the color is converted from RGB to BGR format
        opencv_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)
        return opencv_image

    @staticmethod
    def cv2_to_pil(opencv_image):
        # convert from openCV2 to PIL. Notice the COLOR_BGR2RGB which means that
        # the color is converted from BGR to RGB
        color_converted = cv2.cvtColor(opencv_image, cv2.COLOR_BGR2RGB)
        pil_image = PIL.Image.fromarray(color_converted)
        return pil_image

    # GIMP GEGL Integration Methods
    @staticmethod
    def is_gimp_gegl_available():
        """Check if GIMP GEGL integration is available."""
        # Check if we've already validated this session
        if ImageOps._gegl_validation_cache is not None:
            return ImageOps._gegl_validation_cache
        
        # Trigger lazy GIMP validation if not already done
        config.validate_and_find_gimp()
        
        # If GIMP is not available, GEGL is not available
        if not config.gimp_gegl_enabled:
            ImageOps._gegl_validation_cache = False
            return False
        
        # Perform comprehensive GEGL validation
        try:
            from extensions.gimp.gimp_gegl_validator import GimpGeglValidator
            validator = GimpGeglValidator()
            is_valid, errors = validator.validate_complete_setup()
            
            if is_valid:
                logger.debug("GEGL setup validation successful")
                ImageOps._gegl_validation_cache = True
                return True
            else:
                logger.warning(f"GEGL setup validation failed: {', '.join(errors)}")
                # Update config to disable GEGL for this session
                config.gimp_gegl_enabled = False
                ImageOps._gegl_validation_cache = False
                return False
                
        except Exception as e:
            logger.error(f"Failed to validate GEGL setup: {e}")
            # Update config to disable GEGL for this session
            config.gimp_gegl_enabled = False
            ImageOps._gegl_validation_cache = False
            return False

    @staticmethod
    def clear_gegl_validation_cache():
        """Clear the GEGL validation cache to force re-validation on next check."""
        ImageOps._gegl_validation_cache = None
        logger.debug("GEGL validation cache cleared")

    @staticmethod
    def apply_gegl_operation(image_path: str, operation_name: str, parameters: dict, output_path: str = None, 
                           opacity: float = None, blend_mode = None) -> str:
        """
        Apply a GEGL operation to an image using GIMP 3.
        
        Args:
            image_path: Path to the input image
            operation_name: Name of the GEGL operation (e.g., "gegl:brightness-contrast")
            parameters: Dictionary of parameters for the operation
            output_path: Optional output path. If None, generates one automatically
            opacity: Opacity for the operation (0.0 to 1.0). If None, uses default (1.0)
            blend_mode: Blend mode for the operation. If None, uses default (normal)
            
        Returns:
            Path to the processed image
            
        Raises:
            RuntimeError: If GIMP GEGL is not available or operation fails
        """
        if not ImageOps.is_gimp_gegl_available():
            raise RuntimeError("GIMP GEGL integration is not available. Check GIMP installation and configuration.")
        
        try:
            with GimpGeglClient() as client:
                return client.apply_gegl_operation(image_path, operation_name, parameters, output_path, opacity, blend_mode)
        except Exception as e:
            logger.error(f"GEGL operation failed: {e}")
            raise RuntimeError(f"GEGL operation '{operation_name}' failed: {e}")

    @staticmethod
    def gegl_brightness_contrast(image_path: str, brightness: float = 0.0, contrast: float = 0.0, output_path: str = None) -> str:
        """
        Apply brightness and contrast adjustment using GEGL.
        
        Args:
            image_path: Path to the input image
            brightness: Brightness adjustment (-1.0 to 1.0)
            contrast: Contrast adjustment (-1.0 to 1.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path, 
            "gegl:brightness-contrast", 
            {"brightness": brightness, "contrast": contrast},
            output_path
        )

    @staticmethod
    def gegl_color_balance(image_path: str, cyan_red: float = 0.0, magenta_green: float = 0.0, 
                          yellow_blue: float = 0.0, output_path: str = None) -> str:
        """
        Apply color balance adjustment using GEGL.
        
        Args:
            image_path: Path to the input image
            cyan_red: Cyan-Red balance (-1.0 to 1.0)
            magenta_green: Magenta-Green balance (-1.0 to 1.0)
            yellow_blue: Yellow-Blue balance (-1.0 to 1.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:color-balance",
            {"cyan-red": cyan_red, "magenta-green": magenta_green, "yellow-blue": yellow_blue},
            output_path
        )

    @staticmethod
    def gegl_hue_saturation(image_path: str, hue: float = 0.0, saturation: float = 0.0, 
                           lightness: float = 0.0, output_path: str = None) -> str:
        """
        Apply hue, saturation, and lightness adjustment using GEGL.
        
        Args:
            image_path: Path to the input image
            hue: Hue shift (-180.0 to 180.0 degrees)
            saturation: Saturation adjustment (-100.0 to 100.0)
            lightness: Lightness adjustment (-100.0 to 100.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:hue-saturation",
            {"hue": hue, "saturation": saturation, "lightness": lightness},
            output_path
        )

    @staticmethod
    def gegl_gaussian_blur(image_path: str, std_dev_x: float = 1.0, std_dev_y: float = 1.0, 
                          output_path: str = None) -> str:
        """
        Apply Gaussian blur using GEGL.
        
        Args:
            image_path: Path to the input image
            std_dev_x: Standard deviation in X direction (0.0 to 100.0)
            std_dev_y: Standard deviation in Y direction (0.0 to 100.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:gaussian-blur",
            {"std-dev-x": std_dev_x, "std-dev-y": std_dev_y},
            output_path
        )

    @staticmethod
    def gegl_unsharp_mask(image_path: str, std_dev: float = 1.0, scale: float = 0.5, 
                         output_path: str = None) -> str:
        """
        Apply unsharp mask using GEGL.
        
        Args:
            image_path: Path to the input image
            std_dev: Standard deviation (0.0 to 10.0)
            scale: Scale factor (0.0 to 10.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:unsharp-mask",
            {"std-dev": std_dev, "scale": scale},
            output_path
        )

    @staticmethod
    def gegl_noise_reduce(image_path: str, iterations: int = 1, spatial_radius: float = 1.0, 
                         temporal_radius: float = 0.0, output_path: str = None) -> str:
        """
        Apply noise reduction using GEGL.
        
        Args:
            image_path: Path to the input image
            iterations: Number of iterations (1 to 10)
            spatial_radius: Spatial radius (0.0 to 10.0)
            temporal_radius: Temporal radius (0.0 to 10.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:noise-reduce",
            {"iterations": iterations, "spatial-radius": spatial_radius, "temporal-radius": temporal_radius},
            output_path
        )

    @staticmethod
    def gegl_levels(image_path: str, in_low: float = 0.0, in_high: float = 1.0, 
                   out_low: float = 0.0, out_high: float = 1.0, gamma: float = 1.0, 
                   output_path: str = None) -> str:
        """
        Apply levels adjustment using GEGL.
        
        Args:
            image_path: Path to the input image
            in_low: Input low level (0.0 to 1.0)
            in_high: Input high level (0.0 to 1.0)
            out_low: Output low level (0.0 to 1.0)
            out_high: Output high level (0.0 to 1.0)
            gamma: Gamma correction (0.0 to 10.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:levels",
            {"in-low": in_low, "in-high": in_high, "out-low": out_low, "out-high": out_high, "gamma": gamma},
            output_path
        )

    @staticmethod
    def gegl_exposure(image_path: str, black: float = 0.0, exposure: float = 0.0, 
                     gamma: float = 1.0, output_path: str = None) -> str:
        """
        Apply exposure adjustment using GEGL.
        
        Args:
            image_path: Path to the input image
            black: Black point (0.0 to 1.0)
            exposure: Exposure adjustment (-10.0 to 10.0)
            gamma: Gamma correction (0.0 to 10.0)
            output_path: Optional output path
            
        Returns:
            Path to the processed image
        """
        return ImageOps.apply_gegl_operation(
            image_path,
            "gegl:exposure",
            {"black": black, "exposure": exposure, "gamma": gamma},
            output_path
        )

    @staticmethod
    def get_available_gegl_operations():
        """Get list of available GEGL operations."""
        if not ImageOps.is_gimp_gegl_available():
            return []
        
        try:
            with GimpGeglClient() as client:
                return client.get_available_operations()
        except Exception as e:
            logger.error(f"Failed to get GEGL operations: {e}")
            return []

    @staticmethod
    def get_gegl_operation_schema(operation_name: str):
        """Get parameter schema for a GEGL operation."""
        if not ImageOps.is_gimp_gegl_available():
            return {}
        
        try:
            with GimpGeglClient() as client:
                return client.get_operation_schema(operation_name)
        except Exception as e:
            logger.error(f"Failed to get GEGL operation schema: {e}")
            return {}

    @staticmethod
    def get_gegl_validation_report():
        """
        Get a comprehensive validation report for GIMP GEGL setup.
        
        Returns:
            Formatted validation report string
        """
        try:
            from extensions.gimp.gimp_gegl_validator import get_validation_report
            return get_validation_report()
        except Exception as e:
            logger.error(f"Failed to generate validation report: {e}")
            return f"Error generating validation report: {e}"

    @staticmethod
    def get_available_blend_modes():
        """Get list of available GIMP blend modes."""
        if not ImageOps.is_gimp_gegl_available():
            return []
        
        try:
            from extensions.gimp.gimp_gegl_client import GimpBlendMode
            return [mode.value for mode in GimpBlendMode]
        except Exception as e:
            logger.error(f"Failed to get blend modes: {e}")
            return []

    @staticmethod
    def create_gegl_client_with_settings(default_opacity: float = 1.0, default_blend_mode = None):
        """
        Create a GimpGeglClient with custom default settings.
        
        Args:
            default_opacity: Default opacity for operations (0.0 to 1.0)
            default_blend_mode: Default blend mode for operations
            
        Returns:
            Configured GimpGeglClient instance
        """
        if not ImageOps.is_gimp_gegl_available():
            raise RuntimeError("GIMP GEGL integration is not available")
        
        try:
            return GimpGeglClient(default_opacity=default_opacity, default_blend_mode=default_blend_mode)
        except Exception as e:
            logger.error(f"Failed to create GEGL client: {e}")
            raise RuntimeError(f"Failed to create GEGL client: {e}")

    @staticmethod
    def compare_image_content_without_exif(filepath1, filepath2):
        """
        Compare two images for exact pixel content equality without considering EXIF data.
        This is useful when images have identical visual content but different metadata.
        
        Args:
            filepath1: Path to first image
            filepath2: Path to second image
            
        Returns:
            bool: True if images have identical pixel content, False otherwise
        """
        try:
            # Open images and convert to RGB to normalize format
            img1 = Image.open(filepath1).convert('RGB')
            img2 = Image.open(filepath2).convert('RGB')
            
            # Check if dimensions are identical
            if img1.size != img2.size:
                img1.close()
                img2.close()
                return False
            
            # Convert to numpy arrays for pixel-by-pixel comparison
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            
            # Close images to free memory
            img1.close()
            img2.close()
            
            # Check for exact pixel equality
            return np.array_equal(arr1, arr2)
            
        except Exception as e:
            logger.error(f"Error comparing image content: {e}")
            return False

if __name__ == "__main__":
   ImageOps.randomly_modify_image(sys.argv[1])
