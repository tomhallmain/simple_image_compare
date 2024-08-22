import os
import random

import cv2
import numpy as np

from PIL import Image, ImageDraw, ImageEnhance

#from utils.utils import Utils

class ImageOps:
    COLORS = ["red", "green", "blue", "yellow", "purple", "orange"]

    @staticmethod
    def new_filepath(image_path: str, new_filename: str, append_part: str | None) -> str:
        dirname = os.path.dirname(image_path)
        if new_filename is None or new_filename == "" or append_part is not None:
            basename = os.path.basename(image_path)
            filename_part, ext = os.path.splitext(basename)
            if append_part is not None:
                new_filename = filename_part + append_part + ext
            else:
                new_filename = filename_part + "_cropped" + ext
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
            temp_filepath = os.path.join(os.path.dirname(image_path), 'temp' + current_extension)
            cv2.imwrite(temp_filepath, rotated)
            Utils.move_file(temp_filepath, image_path, overwrite_existing=True)
        except Exception as e:
            print(f'Error in rotate image: {e}')

    @staticmethod
    def enhance_image(image_path):
        dirname = os.path.dirname(image_path)
        filename_parts = os.path.splitext(os.path.basename(image_path))
        new_filename = filename_parts[0] + "_brightened" + filename_parts[1]
        new_file = os.path.join(dirname, new_filename)
        if os.path.exists(new_file):
            raise Exception("File already exists: " + new_filename) # TODO maybe remove this
        image = Image.open(image_path)
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
    def flip_left_right(image_path):
        original_img = Image.open(image_path)
        horz_img = original_img.transpose(method=Image.FLIP_LEFT_RIGHT)
        new_filepath = ImageOps.new_filepath(image_path, "", "_flipped")
        horz_img.save(new_filepath)
        original_img.close()
        horz_img.close()

    @staticmethod
    def random_crop_and_upscale(image_path, allowable_proportions=0.4, shortest_side=1200):
        im = Image.open(image_path)
        width, height = im.size
        midpoint_x = int(width / 2)
        midpoint_y = int(height / 2)
        allowable_range_x = midpoint_x * allowable_proportions
        allowable_range_y = midpoint_y * allowable_proportions
        x0 = int(allowable_range_x * random.random())
        x1 = int(width - (allowable_range_x * random.random()))
        y0 = int(allowable_range_y * random.random())
        y1 = int(height - (allowable_range_y * random.random()))
        bbox = (x0, y0, x1, y1)
        cropped = im.crop(bbox)
        im.close()
        new_filepath = ImageOps.new_filepath(image_path, "", "_cropped")
        cropped.save(new_filepath)
        cropped.close()
        im = Image.open(new_filepath)
        width = x1 - x0
        height = y1 - y0
        if width > height:
            if height < shortest_side:
                im = im.resize((int(width * shortest_side / height), shortest_side))
            else:
                return
        elif width < shortest_side:
            im = im.resize((shortest_side, int(height * shortest_side / width)))
        else:
            return
        im.save(new_filepath)
        print("Resized image")
        im.close()

    # @staticmethod
    # def _random_crop_and_upscale(image_path, allowable_proportions=0.4, shortest_side=1200):
    #     im = Image.open(image_path)
    #     width, height = im.size
    #     midpoint_x = int(width / 2)
    #     midpoint_y = int(height / 2)
    #     allowable_range_x = midpoint_x * allowable_proportions
    #     allowable_range_y = midpoint_y * allowable_proportions
    #     x0 = int(allowable_range_x * random.random())
    #     x1 = int(width - (allowable_range_x * random.random()))
    #     y0 = int(allowable_range_y * random.random())
    #     y1 = int(height - (allowable_range_y * random.random()))
    #     bbox = (x0, y0, x1, y1)
    #     cropped = im.crop(bbox)
    #     im.close()
    #     new_filepath = ImageOps.new_filepath(image_path, "", "_cropped")
    #     cropped.save(new_filepath)
    #     cropped.close()
    #     im = Image.open(new_filepath)
    #     width = x1 - x0
    #     height = y1 - y0
    #     if width > height:
    #         if height < shortest_side:
    #             im = im.resize((int(width * shortest_side / height), shortest_side))
    #         else:
    #             return
    #     elif width < shortest_side:
    #         im = im.resize((shortest_side, int(height * shortest_side / width)))
    #     else:
    #         return
    #     im.save(new_filepath)
    #     print("Resized image")
    #     im.close()

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
        new_filepath = ImageOps.new_filepath(image_path, "", "_upscaled")
        # Save the image
        cv2.imwrite(new_filepath, result)

    @staticmethod
    def randomly_modify_image(image_path):
        pass

    @staticmethod
    def random_draw(image_path):
        image = Image.open(image_path)
        draw = ImageDraw.Draw(image)
        for i in range(random.randint(1, 5)):
            choice = random.randint(0, 4)
            if choice == 0:
                ImageOps._arc(image, draw)
            elif choice == 1:
                ImageOps._line(image, draw)
            elif choice == 2:
                ImageOps._chord(image, draw)
        new_filepath = ImageOps.new_filepath(image_path, "", "_drawn")
        image.save(new_filepath)
        image.close()

    @staticmethod
    def _line(image, image_draw):
        if random.randint(0, 1) == 0:
            for i in range(0, 100, 20):
                image_draw.line((i, 0) + image.size, width=random.randint(2, 20), fill=random.choice(ImageOps.COLORS))
        else:
            points = []
            for i in range(random.randint(2, 4)):
                points.append((random.randint(0, image.size[0]), random.randint(0, image.size[1])))
            image_draw.line(points, width=random.randint(2, 40), fill=random.choice(ImageOps.COLORS), joint="curve")

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
            image_draw.arc(bounds, start=start, end=end, fill=random.choice(ImageOps.COLORS), width=random.randint(2, 40))

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
            image_draw.chord(bounds, start=start, end=end, fill=random.choice(ImageOps.COLORS), outline=random.choice(ImageOps.COLORS), width=random.randint(2, 40))

if __name__ == "__main__":
   ImageOps.random_draw("C:\\Users\\tehal\\ComfyUI\\output\\CUI_17243419353918715.png")
