from typing import Tuple, Union
from PIL import ImageChops
from PIL import Image
from PIL.Image import Image as PilImage


def is_in_color_range(px: Tuple[int, int, int], minimal_color: int) -> bool:
    return px[0] >= minimal_color and px[1] >= minimal_color and px[2] >= minimal_color

def is_line_color_range(im: PilImage, y: int, minimal_color: int) -> bool:
    width, _ = im.size

    for x in range(0, width-1):
        px = im.getpixel((x,y))
        print(f"{x} {y} {px}")
        if not is_in_color_range(px, minimal_color):
            return False

    return True

def is_column_color_range(im: PilImage, x: int, minimal_color: int) -> bool:
    _, height = im.size

    for y in range(0, height-1):
        px = im.getpixel((x,y))
        print(px)
        if not is_in_color_range(px, minimal_color):
            return False
    
    return True

def remove_bars(im: PilImage, minimal_color: int) -> Tuple[PilImage, bool]:
    width, height = im.size
    top = 0
    bottom = height - 1

    # if left border if same color -- skip, because we have no bars TODO 
    if not is_column_color_range(im, 0, minimal_color):
        print('skip left border')
        return im, False

    # calc white pixel rows from the top
    while top < width and not is_line_color_range(im, top, minimal_color):
        print(f"{top} {width}")
        top += 1
    
    # calc white pixel rows from the bottom
    while bottom > 0 and not is_line_color_range(im, bottom, minimal_color):
        bottom -= 1
    
    # no white bars detected
    if top == 0 or bottom == height - 1:
        print('no white bars detected')
        return im, False
    
    # crop based on bars
    bbox = (0, top, width, bottom)
    print(f"0, {top}, {width}, {bottom}")
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


if __name__ == '__main__':

    im = Image.open('')
    cropped = remove_bars(im, 255)
    if cropped[1]:
        cropped[0].save('test.jpg')
    else:
        print("No cropping")
