import re
import os


def get_user_dir():
    return os.path.expanduser("~")


def basename(filepath):
    return os.path.basename(filepath)


def scale_dims(dims, max_dims):
    x = dims[0]
    y = dims[1]
    max_x = max_dims[0]
    max_y = max_dims[1]
    if x <= max_x and y <= max_y:
        return (x, y)
    elif x <= max_x:
        return (int(x * max_y/y), max_y)
    elif y <= max_y:
        return (max_x, int(y * max_x/x))
    else:
        x_scale = max_x / x
        y_scale = max_y / y
        if x_scale < y_scale:
            return (int(x * x_scale), int(y * x_scale))
        else:
            return (int(x * y_scale), int(y * y_scale))


def _wrap_text_to_fit_length(text: str, fit_length: int):
    if len(text) <= fit_length:
        return text

    if " " in text and text.index(" ") < len(text) - 2:
        test_new_text = text[:fit_length]
        if " " in test_new_text:
            last_space_block = re.findall(" +", test_new_text)[-1]
            last_space_block_index = test_new_text.rfind(last_space_block)
            new_text = text[:last_space_block_index]
            text = text[(last_space_block_index+len(last_space_block)):]
        else:
            new_text = test_new_text
            text = text[fit_length:]
        while len(text) > 0:
            new_text += "\n"
            test_new_text = text[:fit_length]
            if len(test_new_text) <= fit_length:
                new_text += test_new_text
                text = text[fit_length:]
            elif " " in test_new_text and test_new_text.index(" ") < len(test_new_text) - 2:
                last_space_block = re.findall(" +", test_new_text)[-1]
                last_space_block_index = test_new_text.rfind(last_space_block)
                new_text += text[:last_space_block_index]
                text = text[(last_space_block_index+len(last_space_block)):]
            else:
                new_text += test_new_text
                text = text[fit_length:]
    else:
        new_text = text[:fit_length]
        text = text[fit_length:]
        while len(text) > 0:
            new_text += "\n"
            new_text += text[:fit_length]
            text = text[fit_length:]

    return new_text
