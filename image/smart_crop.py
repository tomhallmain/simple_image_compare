import os
import sys
from typing import Tuple, Union

from PIL import ImageChops
from PIL import Image
from PIL.Image import Image as PilImage


debug = False


def is_in_color_range(px: Tuple[int, int, int], minimal_color: int) -> bool:
    return px[0] >= minimal_color and px[1] >= minimal_color and px[2] >= minimal_color

def is_close_color(px: Tuple[int, int, int], color: Tuple[int, int, int], tolerance=5) -> bool:
    return abs(px[0] - color[0]) <= tolerance and \
            abs(px[1] - color[1]) <= tolerance and \
            abs(px[2] - color[2]) <= tolerance

def is_line_color(im: PilImage, y: int, color: Tuple[int, int, int]) -> bool:
    width, _ = im.size
    print_counts = 0
    if debug:
        print("Comparison for line: " + str(y))
    for x in range(0, width - 1):
        px = im.getpixel((x,y))
        if not is_close_color(px, color):
            if debug:
                print(f"{px} <> {color} (unmatched on x {x})")
            return False
        if debug and print_counts < 5:
            print(f"{px} <> {color}")
            print_counts += 1
    return True

def is_column_color(im: PilImage, x: int, color: Tuple[int, int, int]) -> bool:
    _, height = im.size
    print_counts = 0
    if debug:
        print("Comparison for column: " + str(x))
    for y in range(0, height-1):
        px = im.getpixel((x,y))
        if not is_close_color(px, color):
            if debug:
                print(f"{px} <> {color} (unmatched on y {y})")
            return False
        if debug and print_counts < 5:
            print(f"{px} <> {color}")
            print_counts += 1
    return True

def detect_perfectly_vertical_division(im: PilImage) -> int:
    # Some images have borders that use gradient colors, making a simple
    # check for the presence of a vertical line not matching the color
    # invalid. This function detects the presence of such a vertical division.
    # Need to find the average difference between left and right pixels
    return -1

def detect_perfectly_horizontal_division(im: PilImage) -> int:
    # Some images have borders that use gradient colors, making a simple
    # check for the presence of a vertical line not matching the color
    # invalid. This function detects the presence of such a horizontal division.
    # These are somewhat less common in practice.
    # Need to find the average difference between left and right pixels
    return -1


def remove_bars(im: PilImage) -> Tuple[PilImage, bool]:
    width, height = im.size
    left = 0
    top = 0
    right = width - 1
    bottom = height - 1
    top_left_color = im.getpixel((0, 0))
#    top_right_color = im.getpixel((width - 1, 0))
#    bottom_left_color = im.getpixel((0, height - 1))
#    bottom_right_color = im.getpixel((width - 1, height - 1))

    while left < right and is_column_color(im, left, top_left_color):
        if debug:
            print(f"LEFT: {left} RIGHT: {right}")
        left += 1
    while right > left and is_column_color(im, right, top_left_color):
        if debug:
            print(f"RIGHT: {right} LEFT: {left}")
        right -= 1
    while top < bottom and is_line_color(im, top, top_left_color):
        if debug:
            print(f"TOP: {top} BOTTOM: {bottom}")
        top += 1
    while bottom > top and is_line_color(im, bottom, top_left_color):
        if debug:
            print(f"BOTTOM: {bottom} TOP: {top}")
        bottom -= 1

    if top == 0 and left == 0 and right == width - 1 and bottom == height - 1:
        print('no bars detected')
        return im, False

    # crop based on bars
    bbox = (left, top, right, bottom)
    if debug:
        print(f"ORIGINAL IMAGE BOX: 0, 0, {width}, {height}")
        print(f"CROPPED IMAGE BOX: {left}, {top}, {right}, {bottom}")
    return im.crop(bbox), True


def get_crop_box_by_px_color(
        im: PilImage,
        px: Tuple[int, int],
        scale: float,
        offset: int) -> Tuple[int, int, int, int]:
    bg = Image.new(im.mode, im.size, px)
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, scale, offset)
    return diff.getbbox()

def crop_by_background(
        im: PilImage,
        minimal_light_background_color_value: int) -> Tuple[int, int, int, int]:
    width, height = im.size
    original_box = (0, 0, width, height)

    # crop by top left pixel color
    px = im.getpixel((0, height-1))
    if is_in_color_range(px, minimal_light_background_color_value):
        bbox1 = get_crop_box_by_px_color(im, px, 2.0, -100)
    else:
        bbox1 = original_box
    
    # crop by bottom right pixel color
    px = im.getpixel((width-1, height-1))
    if is_in_color_range(px, minimal_light_background_color_value):
        bbox2 = get_crop_box_by_px_color(im, px, 2.0, -100)
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
        c_left, c_right = expand(left, right, width, im_width-1)
        c_upper = 0; c_bottom = height-1

    # crop height
    else:
        width = im_width
        height = int(im_width / ratio)
        c_upper, c_bottom = expand(upper, bottom, height, im_height-1)
        c_left = 0; c_right = im_width-1

    return (c_left, c_upper, c_right, c_bottom)

def expand(m1: int, m2: int, value: int, max_size: int) -> Tuple[int, int]:
    value = int((value - (m2-m1)) / 2)
    m1 -= value; m2 += value

    if m1 < 0:
        m2 += abs(m1); m1 = 0
    elif m2 > max_size:
        m1 -= m2 - max_size; m2 = max_size
    
    return m1, m2

def smart_crop(image_path: str, new_filename: str) -> None:
    dirname = os.path.dirname(image_path)
    if new_filename is None or new_filename == "":
        basename = os.path.basename(image_path)
        filename_part, ext = os.path.splitext(basename)
        new_filename = filename_part + "_cropped" + ext
    new_filepath = os.path.join(dirname, new_filename)
    if os.path.exists(new_filepath):
        print("Skipping crop already run: " + new_filepath)
        return
    im = Image.open(image_path)
    cropped = remove_bars(im)
    if cropped[1]:
        cropped[0].save(new_filepath)
        cropped[0].close()
        print(f"Cropped image: " + new_filename)
    else:
        print("No cropping")
    im.close()


if __name__ == '__main__':
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
            smart_crop(f, "")
        except Exception as e:
            print("Error processing file " + f)
            print(e)

