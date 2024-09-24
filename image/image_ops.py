import os
import random
import sys

import cv2
import numpy as np

from PIL import ImageDraw, ImageEnhance
import PIL.Image

from utils.config import config


class ImageOps:
    COLORS = ["red", "green", "blue", "yellow", "purple", "orange", "black", "white", "gray", "pink", "brown"]

    @staticmethod
    def new_filepath(image_path: str, new_filename: str, append_part: str | None) -> str:
        dirname = os.path.dirname(image_path)
        if new_filename is None or new_filename == "" or append_part is not None:
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
            new_filepath = ImageOps.new_filepath(image_path, "", "_rot")
            cv2.imwrite(new_filepath, rotated)
        except Exception as e:
            print(f'Error in rotate image: {e}')

    @staticmethod
    def rotate_image_partial(image_path, angle=90, center=None, scale=1.0):
        image = cv2.imread(image_path)
        rotated = ImageOps._rotate_image_partial(image, angle=angle, center=center, scale=scale)
        new_filepath = ImageOps.new_filepath(image_path, "", "_rot")
        rotated.imsave(new_filepath)
        image.close()

    @staticmethod
    def get_random_color():
        return tuple([random.randint(0, 255) for i in range(3)])

    @staticmethod
    def _rotate_image_partial(image, angle=90, center=None, scale=1.0):
        # grab the dimensions of the image
        (h, w) = image.shape[:2]
        # if the center is None, initialize it as the center of the image
        if center is None:
            center = (w // 2, h // 2)
        # perform the rotation
        M = cv2.getRotationMatrix2D(center, angle, scale)
        rotated = cv2.warpAffine(image, M, (w, h),
                                 borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=ImageOps.get_random_color())
        # return the rotated image
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

    @staticmethod
    def flip_image(image_path, top_bottom=False):
        original_img = PIL.Image.open(image_path)
        mod_img, original_img = ImageOps._flip_image(original_img, top_bottom=top_bottom)
        new_filepath = ImageOps.new_filepath(image_path, "", "_flip")
        mod_img.save(new_filepath)
        original_img.close()
        mod_img.close()

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
        new_filepath = ImageOps.new_filepath(image_path, "", "_crop")
        cropped.save(new_filepath)

    @staticmethod
    def random_rotate_and_crop():
        pass

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
        new_filepath = ImageOps.new_filepath(image_path, "", "_up")
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
            print("No modifications made to image!")
        new_filepath = ImageOps.new_filepath(image_path, "", "_edit")
        im_final.save(new_filepath)
        im.close()
        try:
            im_final.close()
        except Exception:
            pass

    @staticmethod
    def random_draw(image_path):
        image = PIL.Image.open(image_path)
        ImageOps._random_draw(image)
        new_filepath = ImageOps.new_filepath(image_path, "", "_drawn")
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

if __name__ == "__main__":
   ImageOps.randomly_modify_image(sys.argv[1])
