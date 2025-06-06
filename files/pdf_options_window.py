from tkinter import Toplevel, Frame, Label, BooleanVar, W, StringVar
from tkinter.ttk import Checkbutton, Button, Entry

from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._

class PDFOptionsWindow:
    """
    Window for configuring PDF creation options.
    """
    top_level = None
    COL_0_WIDTH = 400

    @classmethod
    def show(cls, master, app_actions, callback):
        """
        Show the PDF options window.
        
        Args:
            master: Parent window
            app_actions: AppActions instance
            callback: Function to call with selected options
        """
        if cls.top_level is not None:
            cls.top_level.lift()
            return
            
        cls.top_level = Toplevel(master, bg=AppStyle.BG_COLOR)
        cls.top_level.title(_("PDF Creation Options"))
        cls.top_level.geometry("500x250")
        cls.top_level.protocol("WM_DELETE_WINDOW", cls.on_closing)
        cls.top_level.bind("<Escape>", cls.on_closing)
        
        # Main container frame with padding
        main_frame = Frame(cls.top_level, bg=AppStyle.BG_COLOR)
        main_frame.grid(column=0, row=0, padx=20, pady=20, sticky='nsew')
        main_frame.columnconfigure(0, weight=1)
        
        # Title
        title_label = Label(main_frame, font=('Helvetica', 14, 'bold'))
        title_label['text'] = _("PDF Creation Options")
        title_label.grid(column=0, row=0, sticky=W, pady=(0, 15))
        title_label.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        
        # Filename
        filename_label = Label(main_frame, font=('Helvetica', 10))
        filename_label['text'] = _("PDF Filename:")
        filename_label.grid(column=0, row=1, sticky=W, pady=(0, 5))
        filename_label.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        
        filename_var = StringVar(value=_("combined_images"))
        filename_entry = Entry(main_frame, textvariable=filename_var, width=40)
        filename_entry.grid(column=0, row=2, sticky=W, pady=(0, 15))
        
        # Options
        preserve_quality = BooleanVar(value=True)
        quality_check = Checkbutton(
            main_frame,
            text=_("Preserve original image quality and format"),
            variable=preserve_quality,
            style='Switch.TCheckbutton'
        )
        quality_check.grid(column=0, row=3, sticky=W, pady=5)
        
        quality_desc = Label(main_frame, font=('Helvetica', 8))
        quality_desc['text'] = _("If enabled, images will maintain their original quality and format.\nIf disabled, images will be compressed to reduce PDF size.")
        quality_desc.grid(column=0, row=4, sticky=W, pady=(0, 15))
        quality_desc.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        
        # Buttons
        button_frame = Frame(main_frame, bg=AppStyle.BG_COLOR)
        button_frame.grid(column=0, row=5, sticky='ew', pady=(15, 0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        
        cancel_btn = Button(button_frame, text=_("Cancel"), command=cls.on_closing)
        cancel_btn.grid(column=0, row=0, padx=5)
        
        create_btn = Button(button_frame, text=_("Create PDF"), 
                          command=lambda: cls.create_pdf(callback, preserve_quality, filename_var))
        create_btn.grid(column=1, row=0, padx=5)
        
        cls.top_level.after(1, lambda: cls.top_level.focus_force())
        
    @classmethod
    def on_closing(cls, event=None):
        """Handle window closing."""
        cls.top_level.destroy()
        cls.top_level = None
        
    @classmethod
    def create_pdf(cls, callback, preserve_quality_var, filename_var):
        """Create PDF with selected options."""
        options = {
            'preserve_quality': preserve_quality_var.get(),
            'filename': filename_var.get()
        }
        callback(options)
        cls.on_closing() 