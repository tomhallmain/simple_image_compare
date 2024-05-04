import asyncio
import re
import os
import shutil
import sys
import threading


def start_thread(callable, use_asyncio=True, args=None):
    if use_asyncio:
        def asyncio_wrapper():
            asyncio.run(callable())

        target_func = asyncio_wrapper
    else:
        target_func = callable

    if args:
        thread = threading.Thread(target=target_func, args=args)
    else:
        thread = threading.Thread(target=target_func)

    thread.daemon = True  # Daemon threads exit when the main process does
    thread.start()


def periodic(run_obj, sleep_attr="", run_attr=None):
    def scheduler(fcn):
        async def wrapper(*args, **kwargs):
            while True:
                asyncio.create_task(fcn(*args, **kwargs))
                period = int(run_obj) if isinstance(run_obj, int) else getattr(run_obj, sleep_attr)
                await asyncio.sleep(period)
                if run_obj and run_attr and not getattr(run_obj, run_attr):
                    print(f"Ending periodic task: {run_obj.__name__}.{run_attr} = False")
                    break
        return wrapper
    return scheduler


def trace(frame, event, arg):
    if event == "call":
        filename = frame.f_code.co_filename
        #if "simple_image_compare" in filename:
        lineno = frame.f_lineno
        # you can examine the frame, locals, etc too.
        print("%s @ %s" % (filename, lineno))
    return trace


def get_user_dir():
    return os.path.expanduser("~")


def alphanumeric_sort(l, text_lambda=lambda i: i, reverse=False): 
    """ Sort the given iterable in the way that humans expect."""
    convert = lambda text: int(text) if text.isdigit() else text
    alphanum_key = lambda item: [ convert(c) for c in re.split('([0-9]+)', text_lambda(item)) ] 
    return sorted(l, key=alphanum_key, reverse=reverse)


def scale_dims(dims, max_dims, maximize=False):
    x = dims[0]
    y = dims[1]
    max_x = max_dims[0]
    max_y = max_dims[1]
    if x <= max_x and y <= max_y:
        if maximize:
            if x < max_x:
                return (int(x * max_y/y), max_y)
            elif y < max_y:
                return (max_x, int(y * max_x/x))
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


def get_relative_dirpath_split(base_dir, filepath):
   # split the filepath from base directory
    relative_filepath = filepath.split(base_dir)[-1]
    
    # remove leading slash if exists 
    if relative_filepath[0] == '/' or relative_filepath[0] == "\\":
        relative_filepath = relative_filepath[1:]

    basename = os.path.basename(relative_filepath)
    relative_dirpath = relative_filepath.replace(basename, "")

    if len(relative_dirpath) > 0 and (relative_dirpath[-1] == '/' or relative_dirpath[-1] == "\\"):
        relative_dirpath = relative_dirpath[:-1]

    return relative_dirpath, basename


def move_file(existing_filepath, target_dir, overwrite_existing=False):
    new_filepath = os.path.join(target_dir, os.path.basename(existing_filepath))
    if not overwrite_existing and os.path.exists(new_filepath):
        raise Exception("File already exists: " + new_filepath)
    shutil.move(existing_filepath, new_filepath)

def copy_file(existing_filepath, target_dir, overwrite_existing=False):
    new_filepath = os.path.join(target_dir, os.path.basename(existing_filepath))
    if not overwrite_existing and os.path.exists(new_filepath):
        raise Exception("File already exists: " + new_filepath)
    shutil.copy2(existing_filepath, new_filepath)


def open_file_location(filepath):
    if sys.platform=='win32':
        os.startfile(filepath)
    elif sys.platform=='darwin':
        subprocess.Popen(['open', filepath])
    else:
        try:
            subprocess.Popen(['xdg-open', filepath])
        except OSError:
            # er, think of something else to try
            # xdg-open *should* be supported by recent Gnome, KDE, Xfce
            raise Exception("Unsupported distribution for opening file location.")
