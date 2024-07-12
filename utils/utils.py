import re
import os
import shutil
import subprocess
import sys


from utils.running_tasks_registry import start_thread

class Utils:
    @staticmethod
    def trace(frame, event, arg):
        if event == "call":
            filename = frame.f_code.co_filename
            if "file_browser" in filename:
                lineno = frame.f_lineno
                # you can examine the frame, locals, etc too.
                print("%s @ %s" % (filename, lineno))
        return Utils.trace

    @staticmethod
    def get_user_dir():
        return os.path.expanduser("~")

    @staticmethod
    def alphanumeric_sort(l, text_lambda=lambda i: i, reverse=False): 
        """ Sort the given iterable in the way that humans expect."""
        convert = lambda text: int(text) if text.isdigit() else text
        alphanum_key = lambda item: [ convert(c) for c in re.split('([0-9]+)', text_lambda(item)) ] 
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
    # NOTE: Maybe want to raise Exception if either existing filepath or target dir are not valid
    def move_file(existing_filepath, target_dir, overwrite_existing=False):
        new_filepath = os.path.join(target_dir, os.path.basename(existing_filepath))
        if not overwrite_existing and os.path.exists(new_filepath):
            raise Exception("File already exists: " + new_filepath)
        shutil.move(existing_filepath, new_filepath)

    @staticmethod
    def copy_file(existing_filepath, target_dir, overwrite_existing=False):
        new_filepath = os.path.join(target_dir, os.path.basename(existing_filepath))
        if not overwrite_existing and os.path.exists(new_filepath):
            raise Exception("File already exists: " + new_filepath)
        shutil.copy2(existing_filepath, new_filepath)


    @staticmethod
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

    @staticmethod
    def open_file_in_gimp(filepath):
        def gimp_process():
            command = ["gimp-2.10", filepath]
            process = subprocess.call(command, shell=True)
            if process!=0:
                raise Exception("Could not open file in GIMP")
        start_thread(gimp_process)

    @staticmethod
    def is_external_drive(filepath):
        if sys.platform=='win32':
            return os.path.splitdrive(filepath)[0]!='C:'
        else:
            # TODO figure out how to detect external drives on other platforms
            return False

    @staticmethod
    def get_default_user_language():
        if sys.platform=='win32':
            import ctypes
            import locale
            windll = ctypes.windll.kernel32
            windll.GetUserDefaultUILanguage()
            _locale = locale.windows_locale[ windll.GetUserDefaultUILanguage() ]
            if _locale is not None and "_" in _locale:
                return _locale[:_locale.index("_")]
        # TODO support finding default languages on other platforms
        return 'en'
