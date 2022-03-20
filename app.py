import tkinter as tk
from tkinter import Canvas, PhotoImage, filedialog, messagebox
# from tkinter.constants import BOTH, DISABLED, NORMAL, LEFT, RAISED, W, X, Y
from tkinter.constants import W
import tkinter.font as fnt
from tkinter.ttk import Button, Entry, Frame, Label, OptionMenu
from PIL import ImageTk, Image
from compare import Compare, get_valid_file

_input = None


'''
if run_search:
    try:
        while True:

    except KeyboardInterrupt:
        exit(0)
    except Exception as e:
        print("Encountered an error while identifying similar image files."
              + " Run with -v flag for more details.")
        if verbose:
            print(e)
'''


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


class ResizingCanvas(Canvas):
    def __init__(self, parent, **kwargs):
        Canvas.__init__(self, parent, **kwargs)
        self.bind("<Configure>", self.on_resize)
        self.height = parent.winfo_height()
        self.width = parent.winfo_width() * 9/10

    def on_resize(self, event):
        # determine the ratio of old width/height to new width/height
        wscale = float(event.width)/self.width
        hscale = float(event.height)/self.height
        self.width = event.width
        self.height = event.height
        # resize the canvas
        self.config(width=self.width, height=self.height)
        # rescale all the objects tagged with the "all" tag
        self.scale("all", 0, 0, wscale, hscale)

    def get_size(self):
        return (self.width, self.height)

    def get_center_coordinates(self):
        return (self.width/2, (self.height)/2)


class App():
    def __init__(self, master):
        self.master = master
        self.base_dir = "."
        self.frameFiledetails = Frame(self.master)
        self.frameFiledetails.columnconfigure(0, weight=1)
        self.row_counter = 0
        self.frameFiledetails.grid(column=0, row=self.row_counter)
        self.label1 = Label(self.frameFiledetails, text="Controls & Settings")
        self.label1.grid(pady=20)
        self.row_counter += 1
        self.labelFiles = Label(self.frameFiledetails, text="")
        self.set_base_dir_btn = Button(self.frameFiledetails,
                                       text="Set directory",
                                       command=self.set_base_dir)
        self.set_base_dir_btn.grid(column=0, row=self.row_counter)
        self.row_counter += 1
        self.set_base_dir_box = Entry(self.frameFiledetails,
                                      text="Add dirpath...",
                                      width=30,
                                      font=fnt.Font(size=8))
        self.set_base_dir_box.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.create_img_btn = Button(self.frameFiledetails,
                                     text="Set search file",
                                     command=self.show_searched_image)
        self.create_img_btn.grid(column=0, row=self.row_counter)
        self.row_counter += 1
        self.create_img_txt = tk.StringVar()
        self.create_img_path_box = Entry(self.frameFiledetails,
                                         textvariable=self.create_img_txt,
                                         width=30,
                                         font=fnt.Font(size=8))
        self.create_img_path_box.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.label_color_diff_threshold = Label(
            self.frameFiledetails, text="Color diff threshold")
        self.label_color_diff_threshold.grid(
            column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.color_diff_threshold = tk.StringVar(master)
        self.color_diff_threshold_choice = OptionMenu(
            self.frameFiledetails, self.color_diff_threshold,
            *[str(i) for i in list(range(31))])
        self.color_diff_threshold.set("15")  # default value
        self.color_diff_threshold_choice.grid(
            column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.label_compare_faces = Label(
            self.frameFiledetails, text="Compare faces")
        self.label_compare_faces.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.compare_faces = tk.StringVar(master)
        self.compare_faces.set("Yes")  # default value
        self.compare_faces_choice = OptionMenu(
            self.frameFiledetails, self.compare_faces, "Yes", "No")
        self.compare_faces_choice.grid(
            column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.label_counter_limit = Label(
            self.frameFiledetails, text="Max # of files to compare")
        self.label_counter_limit.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.set_counter_limit = Entry(self.frameFiledetails,
                                       text="Add file path...",
                                       width=30,
                                       font=fnt.Font(size=8))
        self.set_counter_limit.insert(0, "10000")
        self.set_counter_limit.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.label_inclusion_pattern = Label(
            self.frameFiledetails, text="Filter files by string in name")
        self.label_inclusion_pattern.grid(
            column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.inclusion_pattern = tk.StringVar()
        self.set_inclusion_pattern = Entry(self.frameFiledetails,
                                           textvariable=self.inclusion_pattern,
                                           width=30,
                                           font=fnt.Font(size=8))
        self.set_inclusion_pattern.grid(
            column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.run_compare_btn = Button(self.frameFiledetails,
                                      text="Run image compare",
                                      command=self.run_compare)
        self.run_compare_btn.grid(column=0, row=self.row_counter, sticky=W)
        self.row_counter += 1
        self.prev_image_match_btn = None
        self.next_image_match_btn = None

        self.match_index = 0
        self.master.update()
        self.canvas = ResizingCanvas(self.master)
        self.canvas.grid(column=1, row=0)
        self.files_grouped = None
        self.files_matched = None
        self.compare = None
        self.master.update()

    def set_base_dir(self) -> None:
        base_dir = self.set_base_dir_box.get()
        if base_dir == "" or base_dir == "Add dirpath...":
            base_dir = filedialog.askdirectory(
                initialdir=self.get_base_dir(), title="Select image file")
        self.base_dir = get_valid_file(self.base_dir, base_dir)
        if base_dir is None:
            return
        if self.compare is not None and self.base_dir != self.compare.base_dir:
            self.compare = None
        self.set_base_dir_box.delete(0, "end")
        self.set_base_dir_box.insert(0, base_dir)

    def get_base_dir(self) -> str:
        return "." if (self.base_dir is None
                       or self.base_dir == "") else self.base_dir

    def get_search_file_path(self) -> str:
        search_file_str = self.create_img_txt.get()
        if search_file_str == "":
            return None
        search_file = get_valid_file(self.base_dir, search_file_str)
        if search_file is None:
            self.alert("Invalid search file",
                       "Search file is not a valid file for base dir.",
                       kind="error")
            raise AssertionError(
                "Search file is not a valid file for base dir.")
        return search_file

    def get_counter_limit(self) -> int:
        counter_limit_str = self.set_counter_limit.get()
        if counter_limit_str == "":
            return None
        try:
            return int(counter_limit_str)
        except Exception:
            self.alert("Invalid Setting",
                       "Counter limit must be an integer value.", kind="error")
            raise AssertionError("Counter limit must be an integer value.")

    def get_compare_faces(self) -> bool:
        compare_faces_str = self.compare_faces.get()
        if compare_faces_str == "" or compare_faces_str == "Yes":
            return True
        else:
            return False

    def get_color_diff_threshold(self) -> int:
        color_diff_threshold_str = self.color_diff_threshold.get()
        if color_diff_threshold_str == "":
            return None
        try:
            return int(color_diff_threshold_str)
        except Exception:
            return 20

    def get_inclusion_pattern(self) -> str:
        inclusion_pattern = self.inclusion_pattern.get()
        if inclusion_pattern == "":
            return None
        else:
            return inclusion_pattern

    def get_image_to_fit(self, filename) -> ImageTk.PhotoImage:
        img = Image.open(filename)
        fit_dims = scale_dims((img.width, img.height), self.canvas.get_size())
        img = img.resize(fit_dims)
        return ImageTk.PhotoImage(img)

    def show_searched_image(self) -> None:
        image_path = self.create_img_txt.get()
        print(self.get_base_dir())
        image_path = get_valid_file(self.base_dir, image_path)
        if image_path is None:
            image_path = filedialog.askopenfilename(
                initialdir=self.get_base_dir(), title="Select image file",
                filetypes=(("jpg files", "*.jpg"),
                           ("jpeg files", "*.jpeg"),
                           ("png files", "*.png"),
                           ("tiff files", "*.tiff")))
        self.create_img_txt.set(image_path)
        self.create_image(image_path)

    def show_prev_image(self) -> None:
        if self.files_grouped is None or len(self.files_grouped) == 0:
            self.alert("Search required",
                       "No matches found. Search again to find potential matches.",
                       kind="info")
        if self.match_index > 0:
            self.match_index -= 1
        self.create_image(self.files_matched[self.match_index])

    def show_next_image(self) -> None:
        if self.files_matched is None or len(self.files_matched) == 0:
            self.alert("Search required",
                       "No matches found. Search again to find potential matches.",
                       kind="info")
        if len(self.files_matched) > self.match_index + 1:
            self.match_index += 1
        self.create_image(self.files_matched[self.match_index])

    def create_image(self, image_path) -> None:
        self.img = self.get_image_to_fit(image_path)
        self.canvas.create_image(self.canvas.get_center_coordinates(),
                                 image=self.img, anchor="center")

    def alert(self, title, message, kind="info", hidemain=True) -> None:
        if kind not in ("error", "warning", "info"):
            raise ValueError("Unsupported alert kind.")

        show_method = getattr(messagebox, "show{}".format(kind))
        show_method(title, message)

    def run_compare(self) -> None:
        search_file_path = self.get_search_file_path()
        counter_limit = self.get_counter_limit()
        compare_faces = self.get_compare_faces()
        color_diff_threshold = self.get_color_diff_threshold()
        inclusion_pattern = self.get_inclusion_pattern()
        return

        if self.compare is None or self.compare.base_dir != self.base_dir:
            self.compare = Compare(self.base_dir, search_file_path, counter_limit,
                                   True, compare_faces, color_diff_threshold,
                                   inclusion_pattern, False, True)
            self.compare.get_files()
            self.compare.get_data()
        else:
            self.compare.search_file_path = search_file_path
            self.compare.counter_limit = counter_limit
            self.compare.compare_faces = compare_faces
            self.compare.color_diff_threshold = color_diff_threshold
            self.compare.inclusion_pattern = inclusion_pattern

        if search_file_path is None or search_file_path == "":
            self.files_grouped, self.file_groups = self.compare.run()
            # Not sure what to do here...
        else:
            self.files_grouped = self.compare.run_search(search_file_path)
            if len(self.files_grouped) == 0:
                self.alert("No Match Found",
                           "None of the files match the search file with current settings.",
                           kind="info")
                return

            for f in sorted(self.files_grouped,
                            key=lambda f: self.files_grouped[f]):
                if self.files_grouped[f] < 1000:
                    self.files_matched.append(f)

            self.match_index = 0
            self.files_matched[0]

            if self.prev_image_match_btn is None:
                self.prev_image_match_btn = Button(master=self.frameFiledetails,
                                                   text="Previous Image Match",
                                                   command=self.show_prev_image)
                self.prev_image_match_btn.grid(
                    column=0, row=self.row_counter, sticky=W)
                self.row_counter += 1
                self.next_image_match_btn = Button(master=self.frameFiledetails,
                                                   text="Next Image Match",
                                                   command=self.show_next_image)
                self.next_image_match_btn.grid(
                    column=0, row=self.row_counter, sticky=W)
                self.row_counter += 1


if __name__ == "__main__":
    root = tk.Tk()
    root.title(" Image Compare ")
    root.geometry("1400x950")
    # root.attributes('-fullscreen', True)
    root.resizable(1, 1)
    root.columnconfigure(0, weight=1)
    root.columnconfigure(1, weight=9)
    root.rowconfigure(0, weight=1)
    app = App(root)
    root.mainloop()
    exit()
