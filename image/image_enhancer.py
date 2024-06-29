import os
import sys

from PIL import Image
from PIL import ImageEnhance


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

if __name__ == "__main__":
    enhance_image(sys.argv[1])
