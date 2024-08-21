import os
import sys
from typing import Tuple, Union

from PIL import ImageChops
from PIL import Image
from PIL.Image import Image as PilImage

from utils.config import config

class Cropper:
    @staticmethod
    def smart_crop_simple(image_path: str, new_filename: str) -> None:
        new_filepath = Cropper.new_filepath(image_path, new_filename, None)
        if os.path.exists(new_filepath):
            print("Skipping crop already run: " + new_filepath)
            return
        im = Image.open(image_path)
        cropped_image, is_cropped = Cropper.remove_borders(im)
        im.close()
        if is_cropped:
            cropped_image.save(new_filepath)
            cropped_image.close()
            print("Cropped image: " + new_filepath)
        else:
            print("No cropping")

    @staticmethod
    def smart_crop_multi_detect(image_path: str, new_filename: str) -> list[str]:
        '''
        The image file may contain multiple divisions, that is, multiple valid images.
        The challenge is to determine whether the parts separating a division on the exteriors
        of the image are simply borders or images by themselves. Depending on the answer
        we can crop the image and save valid images accordingly.
        '''
        saved_files = []
        new_filepath = Cropper.new_filepath(image_path, new_filename, None)
        if os.path.exists(new_filepath):
            print("Skipping crop already run: " + new_filepath)
            return saved_files
        im = Image.open(image_path)
        cropped_images, is_cropped = Cropper.remove_borders_by_division_detection(im)
        im.close()
        if is_cropped:
            index_filepaths = len(cropped_images) > 1
            for i in range(len(cropped_images)):
                cropped_image = cropped_images[i]
                if index_filepaths:
                    new_filepath = Cropper.new_filepath(image_path, new_filename, "_" + str(i))
                cropped_image.save(new_filepath)
                cropped_image.close()
            print("Cropped image: " + new_filepath)
        else:
            print("No cropping")
        return saved_files

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
    def is_in_color_range(px: Tuple[int, int, int], minimal_color: int) -> bool:
        return px[0] >= minimal_color and px[1] >= minimal_color and px[2] >= minimal_color

    @staticmethod
    def is_close_color(px: Tuple[int, int, int], color: Tuple[int, int, int], tolerance=5) -> bool:
        return abs(px[0] - color[0]) <= tolerance and \
                abs(px[1] - color[1]) <= tolerance and \
                abs(px[2] - color[2]) <= tolerance

    @staticmethod
    def remove_borders(im: PilImage) -> Tuple[PilImage, bool]:
        '''
        A crude way to remove borders from an image using the top left pixel color.
        '''
        width, height = im.size
        left = 0
        top = 0
        right = width - 1
        bottom = height - 1
        top_left_color = im.getpixel((0, 0))
    #    top_right_color = im.getpixel((width - 1, 0))
    #    bottom_left_color = im.getpixel((0, height - 1))
    #    bottom_right_color = im.getpixel((width - 1, height - 1))

        while left < right and Cropper.is_column_color(im, left, top_left_color):
            if config.debug:
                print(f"LEFT: {left} RIGHT: {right}")
            left += 1
        while right > left and Cropper.is_column_color(im, right, top_left_color):
            if config.debug:
                print(f"RIGHT: {right} LEFT: {left}")
            right -= 1
        while top < bottom and Cropper.is_line_color(im, top, top_left_color):
            if config.debug:
                print(f"TOP: {top} BOTTOM: {bottom}")
            top += 1
        while bottom > top and Cropper.is_line_color(im, bottom, top_left_color):
            if config.debug:
                print(f"BOTTOM: {bottom} TOP: {top}")
            bottom -= 1

        if top == 0 and left == 0 and right == width - 1 and bottom == height - 1:
            print('no borders detected')
            return im, False

        # Crop based on found borders
        bbox = (left, top, right, bottom)
        if config.debug:
            print(f"ORIGINAL IMAGE BOX: 0, 0, {width}, {height}")
            print(f"CROPPED IMAGE BOX: {left}, {top}, {right}, {bottom}")
        return im.crop(bbox), True

    @staticmethod
    def find_standard_deviation_of_pixel_color_in_image(im: PilImage):
        '''
        Returns the standard deviation of the pixel color in the image.
        '''
        width, height = im.size
#        total_pixels = width * height
#        pixel_colors = im.getcolors(total_pixels)

    @staticmethod
    def remove_borders_by_division_detection(im: PilImage, tolerance: int = 100) -> Tuple[list[PilImage], bool]:
        '''
        Find vertical and horizontal divisions in an image and remove borders or split the image based on these.
        '''
        width, height = im.size
        midpoint_x, midpoint_y = int(width / 2), int(height / 2)
        horizontal_diffs, h_diffs_copy = Cropper.detect_perfectly_horizontal_divisions(im)
        vertical_diffs, v_diffs_copy = Cropper.detect_perfectly_vertical_divisions(im)

        # If initial detection test fails, try with successively lower tolerances before giving up.
        # TODO set tolerance dynamically using something like find_standard_deviation_of_pixel_color_in_image
        if len(horizontal_diffs) == 0 and len(vertical_diffs) == 0:
            horizontal_diffs, h_diffs_copy = Cropper.detect_perfectly_horizontal_divisions(im, tolerance=60, diffs=h_diffs_copy)
            vertical_diffs, v_diffs_copy = Cropper.detect_perfectly_vertical_divisions(im, tolerance=60, diffs=v_diffs_copy)
        if len(horizontal_diffs) == 0 and len(vertical_diffs) == 0:
            horizontal_diffs, h_diffs_copy = Cropper.detect_perfectly_horizontal_divisions(im, tolerance=30, diffs=h_diffs_copy)
            vertical_diffs, v_diffs_copy = Cropper.detect_perfectly_vertical_divisions(im, tolerance=30, diffs=v_diffs_copy)
        if len(horizontal_diffs) == 0 and len(vertical_diffs) == 0:
            print('No borders or subimages detected')
            return [im], False

        if config.debug:
            print(f'found horizontal diffs: {horizontal_diffs}')
            print(f'found vertical diffs: {vertical_diffs}')

        # If the image is divided down the middle, test both the left and right images for entropy.
        if len(horizontal_diffs) == 1 and \
                abs(max(horizontal_diffs.keys()) - midpoint_y) < int(height/10):
            horizontal_diffs[0] = 0
            horizontal_diffs[height] = height
        elif len(vertical_diffs) == 1 and \
                abs(max(vertical_diffs.keys()) - midpoint_x) < int(width/10):
            vertical_diffs[0] = 0
            vertical_diffs[width] = width

        if len(horizontal_diffs) > 2 or len(vertical_diffs) > 2:
            print('Multiple subimages detected!')
            print(f"horizontal diffs {horizontal_diffs}")
            print(f"vertical diffs {vertical_diffs}")
            return Cropper.split_image(im, horizontal_diffs, vertical_diffs), True
        else:
            if len(vertical_diffs) == 0 or (len(vertical_diffs) == 1 and min(vertical_diffs.keys()) > midpoint_x):
                left = 0
            else:
                left = min(vertical_diffs.keys())
            if len(vertical_diffs) == 0 or (len(vertical_diffs) == 1 and max(vertical_diffs.keys()) < midpoint_x):
                right = width - 1
            else:
                right = max(vertical_diffs.keys())
            if len(horizontal_diffs) == 0 or (len(horizontal_diffs) == 1 and min(horizontal_diffs.keys()) > midpoint_y):
                top = 0
            else:
                top = min(horizontal_diffs.keys())
            if len(horizontal_diffs) == 0 or (len(horizontal_diffs) == 1 and max(horizontal_diffs.keys()) < midpoint_y):
                bottom = height - 1
            else:
                bottom = max(horizontal_diffs.keys())
            bbox = (left, top, right, bottom)
            if config.debug:
                print(f"ORIGINAL IMAGE BOX: 0, 0, {width}, {height}")
                print(f"CROPPED IMAGE BOX: {left}, {top}, {right}, {bottom}")
            return [im.crop(bbox)], True

    @staticmethod
    def split_image(im, horizontal_diffs, vertical_diffs) -> list[PilImage]:
        '''
        Splits the image into a list of images based on known horizontal and vertical divisions.
        '''
        width, height = im.size
        print(f"{width}x{height}")
        subimages = []
        xs = list(vertical_diffs.keys())
        ys = list(horizontal_diffs.keys())
        xs.sort()
        ys.sort()
        if len(xs) == 0 and len(ys) == 0:
            return [im]
        if 0 not in xs:
            xs.insert(0, 0)
        if width not in xs:
            xs.append(width)
        if 0 not in ys:
            ys.insert(0, 0)
        if height not in ys:
            ys.append(height)
        if config.debug:
            print(f"SUBIMAGE CROP Xs: {xs}")
            print(f"SUBIMAGE CROP Ys: {ys}")
        for x in range(len(xs) - 1):
            for y in range(len(ys) - 1):
                subimages.append(im.crop((xs[x], ys[y], xs[x + 1], ys[y + 1])))
        i = 0
        subimage_count = 0
        while i < len(subimages):
            subimage = subimages[i]
            if Cropper.is_small(subimage):
                print(f"Subimage {subimage_count} is invalid due to being too small.")
                del subimages[i]
            elif Cropper.is_low_entropy(subimage):
                print(f"Subimage {subimage_count} is invalid due to low entropy.")
                del subimages[i]
            else:
                i += 1
            subimage_count += 1
        return subimages

    @staticmethod
    def is_low_entropy(im):
        '''
        Checks the image to see if it is low entropy.
        '''
        entropy = im.entropy()
        if config.debug:
            print(f"Entropy of {im} is {entropy}.")
        return entropy < 5

    @staticmethod
    def is_small(im):
        width, height = im.size
        return width < 30 or height < 30

    @staticmethod
    def is_line_color(im: PilImage, y: int, color: Tuple[int, int, int]) -> bool:
        width, _ = im.size
        print_counts = 0
        if config.debug:
            print("Comparison for line: " + str(y))
        for x in range(0, width - 1):
            px = im.getpixel((x,y))
            if not Cropper.is_close_color(px, color):
                if config.debug:
                    print(f"{px} <> {color} (unmatched on x {x})")
                return False
            if config.debug and print_counts < 10:
                print(f"{px} <> {color}")
                print_counts += 1
        return True

    @staticmethod
    def is_column_color(im: PilImage, x: int, color: Tuple[int, int, int]) -> bool:
        _, height = im.size
        print_counts = 0
        if config.debug:
            print("Comparison for column: " + str(x))
        for y in range(0, height-1):
            px = im.getpixel((x,y))
            if not Cropper.is_close_color(px, color):
                if config.debug:
                    print(f"{px} <> {color} (unmatched on y {y})")
                return False
            if config.debug and print_counts < 10:
                print(f"{px} <> {color}")
                print_counts += 1
        return True

    @staticmethod
    def get_crop_box_by_px_color(
            im: PilImage,
            px: Tuple[int, int],
            scale: float,
            offset: int) -> Tuple[int, int, int, int]:
        bg = Image.new(im.mode, im.size, px)
        diff = ImageChops.difference(im, bg)
        diff = ImageChops.add(diff, diff, scale, offset)
        return diff.getbbox()

    @staticmethod
    def crop_by_background(
            im: PilImage,
            minimal_light_background_color_value: int) -> Tuple[int, int, int, int]:
        width, height = im.size
        original_box = (0, 0, width, height)

        # crop by top left pixel color
        px = im.getpixel((0, height-1))
        if Cropper.is_in_color_range(px, minimal_light_background_color_value):
            bbox1 = Cropper.get_crop_box_by_px_color(im, px, 2.0, -100)
        else:
            bbox1 = original_box
        
        # crop by bottom right pixel color
        px = im.getpixel((width-1, height-1))
        if Cropper.is_in_color_range(px, minimal_light_background_color_value):
            bbox2 = Cropper.get_crop_box_by_px_color(im, px, 2.0, -100)
        else:
            bbox2 = original_box

        crop = (
            max(bbox1[0], bbox2[0]),
            max(bbox1[1], bbox2[1]),
            min(bbox1[2], bbox2[2]),
            min(bbox1[3], bbox2[3])
        )

        return crop

    def calculate_optimal_crop(
            self,
            im_width: int,
            im_height: int,
            inner_rect: Tuple[int, int, int, int],
            ratio: float
    ) -> Union[Tuple[int, int, int, int], None]:
        im_ratio = im_width / im_height

        # not all images have to be cropped
        if im_ratio == ratio:
            return None
        
        left, upper, right, bottom = inner_rect

        # calculate with max height
        height = im_height
        width = int(im_height * ratio)

        # crop width
        if width <= im_width:
            c_left, c_right = Cropper.expand(left, right, width, im_width-1)
            c_upper = 0; c_bottom = height-1

        # crop height
        else:
            width = im_width
            height = int(im_width / ratio)
            c_upper, c_bottom = Cropper.expand(upper, bottom, height, im_height-1)
            c_left = 0; c_right = im_width-1

        return (c_left, c_upper, c_right, c_bottom)

    @staticmethod
    def expand(m1: int, m2: int, value: int, max_size: int) -> Tuple[int, int]:
        value = int((value - (m2-m1)) / 2)
        m1 -= value; m2 += value

        if m1 < 0:
            m2 += abs(m1); m1 = 0
        elif m2 > max_size:
            m1 -= m2 - max_size; m2 = max_size
        
        return m1, m2

    @staticmethod
    def detect_perfectly_vertical_divisions(im: PilImage, tolerance: int = 100, diffs: dict = {}) -> Tuple[dict, dict]:
        '''
        Some images have borders that use gradient colors, making a simple
        test for the presence of a vertical line not matching a color insufficient.
        This function detects the presence of such a vertical division.
        Finds the average difference between left and right pixels.
        '''
        width, height = im.size
        x = 1
        if len(diffs) == 0:
            while x < width:
                diffs_for_x = []
                y = 0
                while y < height:
                    px1 = im.getpixel((x-1, y))
                    px2 = im.getpixel((x, y))
                    diff = abs(px2[0] - px1[0]) + \
                        abs(px2[1] - px1[1]) + \
                        abs(px2[2] - px1[2])
                    y += 1
                    diffs_for_x.append(diff)
                if len(diffs_for_x) == 0:
                    raise Exception(f"Failed to parse diffs for x={x}")
                diffs[x] = sum(diffs_for_x) / len(diffs_for_x)
                x += 1
        diffs_copy = {k:v for k, v in diffs.items()}
        for x, avg_diff in sorted(diffs.items(), key=lambda x:x[1], reverse=True):
            if config.debug and avg_diff > int(tolerance / 2):
                print(f"x = {x}, avg diff = {avg_diff}, tolerance = {tolerance}")
            if avg_diff < tolerance:
                del diffs[x]
        Cropper.consolidate_close_diffs(width, diffs, tolerance=max(10, int(width/10)))
        for x, avg_diff in diffs.items():
            print(f"FINAL x = {x}, avg diff = {avg_diff}")
        return diffs, diffs_copy

    @staticmethod
    def detect_perfectly_horizontal_divisions(im: PilImage, tolerance: int = 100, diffs: dict = {}) -> Tuple[dict, dict]:
        '''
        Some images have borders that use gradient colors, making a simple
        test for the presence of a horizontal line matching a color insufficient.
        This function detects the presence of such a horizontal division.
        Finds the average difference between top and bottom pixels.
        '''
        width, height = im.size
        y = 1
        diffs = {}
        if len(diffs) == 0:
            while y < height:
                diffs_for_y = []
                x = 0
                while x < width:
                    px1 = im.getpixel((x, y-1))
                    px2 = im.getpixel((x, y))
                    diff = abs(px2[0] - px1[0]) + \
                        abs(px2[1] - px1[1]) + \
                        abs(px2[2] - px1[2])
                    x += 1
                    diffs_for_y.append(diff)
                if len(diffs_for_y) == 0:
                    raise Exception(f"Failed to parse diffs for y={y}")
                diffs[y] = sum(diffs_for_y) / len(diffs_for_y)
                y += 1
        diffs_copy = {k:v for k, v in diffs.items()}
        for y, avg_diff in sorted(diffs.items(), key=lambda y:y[1], reverse=True):
            if avg_diff > int(tolerance / 2):
                print(f"y = {y}, avg diff = {avg_diff}")
            if avg_diff < tolerance:
                del diffs[y]
        Cropper.consolidate_close_diffs(height, diffs, tolerance=max(10, int(height/10)))
        for y, avg_diff in diffs.items():
            print(f"FINAL y = {y}, avg diff = {avg_diff}")
        return diffs, diffs_copy

    @staticmethod
    def consolidate_close_diffs(_max, diffs, tolerance=10):
        '''
        Consolidate the diffs dict by merging close entries. Identifies which 
        entries are close enough to each other and then selects the most likely
        candidate based on its proximity to the edges of the image (the max).
        If the diff position is close to 0, select the higher value, and if it's
        close to the max, select the lower value -- We only want to preserve 
        the valid part of the image, which is probably not inclusive of small
        slivers that the interior of these grouped diff positions would represent.
        '''
        midpoint = int(_max / 2)
        keys = list(diffs.keys())
        keys.sort()
        matches = {}
        def is_close_to_existing_match(key):
            if config.debug:
                print(f"key = {key}, match values = {matches}")
            for match_id, match_values in matches.items():
                for match_value in match_values:
                    if key == match_value:
                        return -2 # The key is already in a group.
            for match_id, match_values in matches.items():
                for match_value in match_values:
                    if abs(key - match_value) < tolerance:
                        return match_id
            return -1
        match_id = -1
        for i in range(len(keys)):
            for j in range(i+1, len(keys)):
                existing_match = False
                test_match_id = is_close_to_existing_match(keys[i])
                if test_match_id != -1:
                    if test_match_id != -2:
                        matches[test_match_id].append(keys[i])
                    existing_match = True
                test_match_id = is_close_to_existing_match(keys[j])
                if test_match_id > -1:
                    if test_match_id != -2:
                        matches[test_match_id].append(keys[j])
                    existing_match = True
                if not existing_match and abs(keys[j] - keys[i]) < tolerance:
                    match_id += 1
                    matches[match_id] = [keys[i], keys[j]]
        for match in matches.values():
            match.sort()
        match_keys = list(matches.keys())
        match_keys.sort()
        for match_values in matches.values():
            avg_value = sum(match_values)/len(match_values)
            winning_value = min(match_values) if avg_value > midpoint else max(match_values)
            for val in match_values:
                if val != winning_value:
                    if config.debug:
                        print(f'Consolidated value = {val} Winning value = {winning_value} Max = {_max}')
                    del diffs[val]
        return diffs

    @staticmethod
    def random_crop(image, allowable_proportions):
        pass


if __name__ == '__main__':


#   Cropper.smart_crop_simple(sys.argv[1], "")
    Cropper.smart_crop_multi_detect(sys.argv[1], "")
    exit()

    extensions = [".jpg", ".jpeg", ".png", ".webp", ".tiff"]
    directory_to_process = sys.argv[1]
    if not os.path.isdir(directory_to_process):
        print('not a directory: "' + directory_to_process + '"')
        exit()
    files_to_crop = []
    for f in os.listdir(directory_to_process):
        for ext in extensions:
            if f[-len(ext):] == ext:
                files_to_crop.append(os.path.join(directory_to_process, f))

    for f in files_to_crop:
        try:
            Cropper.smart_crop_multi_detect(f, "")
        except Exception as e:
            print("Error processing file " + f)
            print(e)

