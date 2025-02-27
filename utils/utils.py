from enum import Enum
import logging
import re
import os
import psutil
import shutil
import subprocess
import sys

from utils.custom_formatter import CustomFormatter
from utils.running_tasks_registry import start_thread

# create logger
logger = logging.getLogger("simple_image_compare")
logger.setLevel(logging.DEBUG)

# create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

ch.setFormatter(CustomFormatter())

logger.addHandler(ch)


class Utils:
    @staticmethod
    def log(message, level=logging.INFO):
        logger.log(level, message)
    
    @staticmethod
    def log_debug(message):
        Utils.log(message, logging.DEBUG)

    @staticmethod
    def log_red(message):
        Utils.log(message, logging.ERROR)
    
    @staticmethod
    def log_yellow(message):
        Utils.log(message, logging.WARNING)

    @staticmethod
    def trace(frame, event, arg):
        if event != 'call':
            return
        co = frame.f_code
        func_name = co.co_name
        if func_name == 'write':  # Ignore write() calls from print statements
            return
        func_filename = co.co_filename
        func_line_no = frame.f_lineno
        caller = frame.f_back
        app_name = "simple_image_compare"
        site_packages = "site-packages"
        lib = "\\Lib\\"
        if caller is None:
            if app_name in func_filename:
                func_simple_name = os.path.splitext(os.path.basename(func_filename))[0]
                print(f'{func_simple_name}:{func_line_no}:{func_name}()')
            return
        caller_filename = caller.f_code.co_filename
        if app_name in func_filename or app_name in caller_filename:
            if app_name in func_filename:
                func_simple_name = os.path.splitext(os.path.basename(func_filename))[0]
            elif site_packages in func_filename:
                func_simple_name = func_filename[func_filename.find(site_packages)+len(site_packages)+1:]
            elif lib in func_filename:
                func_simple_name = func_filename[func_filename.find(lib)+len(lib):]
            else:
                func_simple_name = func_filename
            if app_name in caller_filename:
                caller_simple_name = os.path.splitext(os.path.basename(func_filename))[0]
            elif site_packages in caller_filename:
                caller_simple_name = caller_filename[caller_filename.find(site_packages)+len(site_packages)+1:]
            elif lib in func_filename:
                func_simple_name = func_filename[func_filename.find(lib)+len(lib):]
            else:
                caller_simple_name = caller_filename
            caller_line_no = caller.f_lineno
            print(f'{caller_simple_name}:{caller_line_no} called {func_simple_name}:{func_line_no}:{func_name}()')

    @staticmethod
    def get_user_dir():
        return os.path.expanduser("~")

    @staticmethod
    def calculate_available_ram():
        return psutil.virtual_memory().available / (1024 ** 3)

    @staticmethod
    def alphanumeric_sort(l, text_lambda=lambda i: i, reverse=False):
        """ Sort the given iterable in the way that humans expect."""
        def convert(text): return int(text) if text.isdigit() else text
        def alphanum_key(item): return [convert(c)
                                        for c in re.split('([0-9]+)', text_lambda(item))]
        return sorted(l, key=alphanum_key, reverse=reverse)

    @staticmethod
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

    @staticmethod
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
                    last_space_block_index = test_new_text.rfind(
                        last_space_block)
                    new_text += text[:last_space_block_index]
                    text = text[(last_space_block_index
                                 + len(last_space_block)):]
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

    @staticmethod
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

    @staticmethod
    def get_relative_dirpath(base_dir, levels=1):
        # get relative dirpath from base directory
        if "/" not in base_dir and "\\" not in base_dir:
            return base_dir
        if "/" in base_dir:
            # temp = base_dir
            # if "/" == base_dir[0]:
            #     temp = base_dir[1:]
            dir_parts = base_dir.split("/")
        else:
            dir_parts = base_dir.split("\\")
        if len(dir_parts) <= levels:
            return base_dir
        relative_dirpath = ""
        for i in range(len(dir_parts) - 1, len(dir_parts) - levels - 1, -1):
            if relative_dirpath == "":
                relative_dirpath = dir_parts[i]
            else:
                relative_dirpath = dir_parts[i] + "/" + relative_dirpath
        return relative_dirpath

    @staticmethod
    def get_centrally_truncated_string(s, maxlen):
        # get centrally truncated string
        if len(s) <= maxlen:
            return s
        max_left_index = int((maxlen)/2-2)
        min_right_index = int(-(maxlen)/2-1)
        return s[:max_left_index] + "..." + s[min_right_index:]

    @staticmethod
    # NOTE: Maybe want to raise Exception if either existing filepath or target dir are not valid
    def move_file(existing_filepath, target_dir, overwrite_existing=False):
        new_filepath = os.path.join(
            target_dir, os.path.basename(existing_filepath))
        if not overwrite_existing and os.path.exists(new_filepath):
            raise Exception("File already exists: " + new_filepath)
        return shutil.move(existing_filepath, new_filepath)

    @staticmethod
    def copy_file(existing_filepath, target_dir, overwrite_existing=False):
        new_filepath = os.path.join(
            target_dir, os.path.basename(existing_filepath))
        if not overwrite_existing and os.path.exists(new_filepath):
            raise Exception("File already exists: " + new_filepath)
        return shutil.copy2(existing_filepath, new_filepath)

    @staticmethod
    def open_file_location(filepath):
        if sys.platform == 'win32':
            os.startfile(filepath)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', filepath])
        else:
            try:
                subprocess.Popen(['xdg-open', filepath])
            except OSError:
                # er, think of something else to try
                # xdg-open *should* be supported by recent Gnome, KDE, Xfce
                raise Exception(
                    "Unsupported distribution for opening file location.")

    @staticmethod
    def open_file_in_gimp(filepath, gimp_exe_loc="gimp-2.10"):
        def gimp_process():
            command = ["set", "LANG=en", "&&", gimp_exe_loc, filepath]
            process = subprocess.call(command, shell=True)
            if process != 0:
                raise Exception("Could not open file in GIMP")
        start_thread(gimp_process)

    @staticmethod
    def is_external_drive(filepath):
        if sys.platform == 'win32':
            return os.path.splitdrive(filepath)[0] != 'C:'
        else:
            # TODO figure out how to detect external drives on other platforms
            return False

    @staticmethod
    def get_default_user_language():
        if sys.platform == 'win32':
            import ctypes
            import locale
            windll = ctypes.windll.kernel32
            windll.GetUserDefaultUILanguage()
            _locale = locale.windows_locale[windll.GetUserDefaultUILanguage()]
            if _locale is not None and "_" in _locale:
                return _locale[:_locale.index("_")]
        # TODO support finding default languages on other platforms
        return 'en'

    @staticmethod
    def modifier_key_pressed(event, keys_to_check=[]):
        if not event:
            return (False)
        is_pressed = []
        for key in keys_to_check:
            if not isinstance(key, ModifierKey):
                raise Exception("Invalid modifier key: " + str(key))
            is_pressed.append(event.state & key.value != 0)
        if len(keys_to_check) == 1:
            return is_pressed[0]
        return tuple(is_pressed)

    @staticmethod
    def round_up(number, to):
        if number % to == 0:
            return number
        else:
            return number - (number % to) + to

    @staticmethod
    def is_invalid_file(file_path, counter, run_search, inclusion_pattern):
        if file_path is None:
            return True
        elif run_search and counter == 0:
            return False
        elif inclusion_pattern is not None:
            return inclusion_pattern not in file_path
        else:
            return False

    @staticmethod
    def get_valid_file(base_dir, input_filepath):
        if (not isinstance(input_filepath, str) or input_filepath is None
                or input_filepath.strip() == ""):
            return None
        if input_filepath.startswith('"') and input_filepath.endswith('"'):
            input_filepath = input_filepath[1:-1]
        elif input_filepath.startswith("'") and input_filepath.endswith("'"):
            input_filepath = input_filepath[1:-1]
        if os.path.exists(input_filepath):
            return input_filepath
        elif base_dir is not None and os.path.exists(os.path.join(base_dir, input_filepath)):
            return base_dir + "/" + input_filepath
        else:
            return None

    @staticmethod
    def split(string, delimiter=","):
        # Split the string by the delimiter and clean any delimiter escapes present in the string
        parts = []
        i = 0
        while i < len(string):
            if string[i] == delimiter:
                if i == 0 or string[i-1] != "\\":
                    parts.append(string[:i])
                    string = string[i+1:]
                    i = -1
                elif i != 0 and string[i-1] == "\\":
                    string = string[:i-1] + delimiter + string[i+1:]
            elif i == len(string) - 1:
                parts.append(string[:i+1])
            i += 1
        if len(parts) == 0 and len(string) != 0:
            parts.append(string)
        return parts


class ModifierKey(Enum):
    SHIFT = 0x1
    CTRL = 0x4
    ALT = 0x20000
