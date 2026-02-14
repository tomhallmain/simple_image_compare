"""
Tkinter OCR text viewer window.

Displays text extracted via Surya OCR with copy-to-clipboard support.
The user can select and copy a portion of the text or copy all of it
with a single button press.
"""

from tkinter import Text, Label, LEFT, W, END, WORD
from tkinter.ttk import Button

from lib.multi_display import SmartToplevel
from utils.app_style import AppStyle
from utils.translations import I18N

_ = I18N._


class OCRTextWindow:
    """Window that shows OCR-extracted text with copy support."""

    top_level = None

    def __init__(self, master, app_actions, ocr_text, image_path,
                 confidence=None, dimensions="600x500"):
        OCRTextWindow.top_level = SmartToplevel(
            persistent_parent=master, geometry=dimensions,
        )
        OCRTextWindow.set_title(image_path, confidence)
        self.master = OCRTextWindow.top_level
        self.app_actions = app_actions
        self.ocr_text = ocr_text
        self.has_closed = False

        # -- Top row: copy button + header label -------------------------
        self._copy_btn = None
        self._add_btn("_copy_btn", _("Copy All Text"),
                       self.copy_text_to_clipboard, row=0, column=0)

        header_text = _("OCR Result")
        if confidence is not None:
            header_text += f"  ({_('avg confidence')}: {confidence:.1%})"
        self._label_info = Label(self.master)
        self._add_label(self._label_info, header_text, row=0, column=1,
                        wraplength=400)

        # -- Text widget (read-only, selectable, scrollable) -------------
        self._text_widget = Text(
            self.master,
            wrap=WORD,
            bg=AppStyle.BG_COLOR,
            fg=AppStyle.FG_COLOR,
            insertbackground=AppStyle.FG_COLOR,
            relief="flat",
            padx=6,
            pady=6,
        )
        self._text_widget.insert(END, ocr_text)
        self._text_widget.config(state="disabled")  # read-only
        self._text_widget.grid(row=1, column=0, columnspan=2,
                               sticky="nsew", padx=4, pady=4)

        self.master.grid_rowconfigure(1, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.master.grid_columnconfigure(1, weight=1)

        # -- Bindings ----------------------------------------------------
        self.master.bind("<Escape>", self.close_windows)
        self.master.bind("<Control-c>", self._copy_shortcut)
        self.master.protocol("WM_DELETE_WINDOW", self.close_windows)
        self.master.after(1, lambda: self._text_widget.focus_force())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_text(self, ocr_text, image_path, confidence=None):
        """Refresh with new OCR results."""
        self.ocr_text = ocr_text
        self._text_widget.config(state="normal")
        self._text_widget.delete("1.0", END)
        self._text_widget.insert(END, ocr_text)
        self._text_widget.config(state="disabled")
        OCRTextWindow.set_title(image_path, confidence)
        self.master.update()

    def copy_text_to_clipboard(self):
        """Copy all OCR text to the system clipboard."""
        try:
            self.master.clipboard_clear()
            self.master.clipboard_append(self.ocr_text)
            if self.app_actions:
                self.app_actions.success(_("Copied OCR text to clipboard"))
        except Exception as e:
            if self.app_actions:
                self.app_actions.warn(
                    _("Error copying OCR text: ") + str(e)
                )

    @staticmethod
    def set_title(image_path, confidence=None):
        title = _("OCR Text") + " - " + image_path
        if confidence is not None:
            title += f"  ({_('avg confidence')}: {confidence:.1%})"
        OCRTextWindow.top_level.title(title)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _copy_shortcut(self, event=None):
        """Ctrl+C: copy selection if any, otherwise copy all."""
        try:
            sel = self._text_widget.get("sel.first", "sel.last")
            if sel:
                # Let normal Ctrl+C handle the selection
                return
        except Exception:
            pass
        # No selection -> copy all
        self.copy_text_to_clipboard()

    def close_windows(self, event=None):
        self.master.destroy()
        self.has_closed = True

    def _add_label(self, label_ref, text, row=0, column=0, wraplength=500):
        label_ref["text"] = text
        label_ref.grid(column=column, row=row, sticky=W, padx=4, pady=2)
        label_ref.config(wraplength=wraplength, justify=LEFT,
                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)

    def _add_btn(self, button_ref_name, text, command, row=0, column=0):
        if getattr(self, button_ref_name) is None:
            button = Button(master=self.master, text=text, command=command)
            setattr(self, button_ref_name, button)
            button.grid(row=row, column=column, padx=4, pady=2)
