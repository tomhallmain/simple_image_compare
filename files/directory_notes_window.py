import os
from tkinter import Label, Text, LEFT, W, END, font, filedialog
from tkinter.ttk import Button, Frame, Separator

from utils.app_style import AppStyle
from lib.tk_scroll_demo import ScrollFrame
from lib.multi_display import SmartToplevel
from utils.translations import I18N
from files.directory_notes import DirectoryNotes

_ = I18N._


class DirectoryNotesWindow:
    COL_0_WIDTH = 600
    MAX_ROWS = 30
    
    def __init__(self, app_master, app_actions, base_dir: str, geometry="900x800"):
        self.app_master = app_master
        self.app_actions = app_actions
        self.base_dir = base_dir
        
        # Get parent window position to determine which display to use
        parent_x = app_master.winfo_x()
        parent_y = app_master.winfo_y()
        
        # Position window offset from parent
        offset_x = 50
        offset_y = 50
        new_x = parent_x + offset_x
        new_y = parent_y + offset_y
        
        # Create geometry string with custom positioning
        positioned_geometry = f"{geometry}+{new_x}+{new_y}"
        
        self.master = SmartToplevel(
            persistent_parent=app_master,
            title=_("Directory Notes - {0}").format(os.path.basename(base_dir) or base_dir),
            geometry=positioned_geometry,
            auto_position=False
        )
        self.frame = ScrollFrame(self.master, bg_color=AppStyle.BG_COLOR)
        self.frame.pack(side="top", fill="both", expand=True)
        
        self.marked_file_widgets = []
        self.note_widgets = []
        self._add_widgets()
        self.master.bind("<Escape>", self.close_window)
        self.frame.after(1, lambda: self.frame.focus_force())
    
    def _add_widgets(self):
        """Add all widgets to the window."""
        row = 0
        
        # Header
        header = Label(self.frame.viewPort)
        header_text = _("Directory: {0}").format(self.base_dir)
        self._add_label(header, header_text, row=row, column=0, wraplength=self.COL_0_WIDTH, header=True)
        row += 1
        
        # Buttons frame
        buttons_frame = Frame(self.frame.viewPort)
        buttons_frame.grid(row=row, column=0, sticky=W, pady=5)
        
        # Export button
        export_btn = Button(buttons_frame, text=_("Export to Text File"), command=self.export_to_file)
        export_btn.pack(side=LEFT, padx=5)
        
        # Import buttons
        import_text_btn = Button(buttons_frame, text=_("Import from Text File"), command=self.import_from_text_file)
        import_text_btn.pack(side=LEFT, padx=5)
        
        import_json_btn = Button(buttons_frame, text=_("Import from JSON File"), command=self.import_from_json_file)
        import_json_btn.pack(side=LEFT, padx=5)
        
        row += 1
        
        # Separator
        sep1 = Separator(self.frame.viewPort, orient="horizontal")
        sep1.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1
        
        # Marked Files section
        marked_header = Label(self.frame.viewPort)
        self._add_label(marked_header, _("MARKED FILES"), row=row, column=0, wraplength=self.COL_0_WIDTH, header=True)
        row += 1
        
        marked_files = DirectoryNotes.get_marked_files(self.base_dir)
        if marked_files:
            for filepath in marked_files:
                self._add_marked_file_widget(filepath, row)
                row += 1
        else:
            help_label = Label(self.frame.viewPort)
            self._add_label(help_label, _("(No marked files)"), row=row, column=0, wraplength=self.COL_0_WIDTH)
            row += 1
        
        # Separator
        sep2 = Separator(self.frame.viewPort, orient="horizontal")
        sep2.grid(row=row, column=0, sticky="ew", pady=10)
        row += 1
        
        # File Notes section
        notes_header = Label(self.frame.viewPort)
        self._add_label(notes_header, _("FILE NOTES"), row=row, column=0, wraplength=self.COL_0_WIDTH, header=True)
        row += 1
        
        file_notes = DirectoryNotes.get_all_file_notes(self.base_dir)
        if file_notes:
            for filepath, note in sorted(file_notes.items()):
                self._add_note_widget(filepath, note, row)
                row += 1
        else:
            help_label = Label(self.frame.viewPort)
            self._add_label(help_label, _("(No file notes)"), row=row, column=0, wraplength=self.COL_0_WIDTH)
            row += 1
    
    def _add_marked_file_widget(self, filepath: str, row: int):
        """Add a widget row for a marked file."""
        basename = os.path.basename(filepath)
        
        # File label
        file_label = Label(self.frame.viewPort)
        self._add_label(file_label, basename, row=row, column=0, wraplength=self.COL_0_WIDTH)
        
        # Path label (smaller, grayed out)
        path_label = Label(self.frame.viewPort)
        path_label['text'] = filepath
        path_label.grid(column=0, row=row + 1, sticky=W, padx=(20, 0))
        base_font = font.nametofont(path_label.cget("font"))
        small_font = base_font.copy()
        small_font.configure(size=int(base_font['size'] * 0.85))
        path_label.config(font=small_font, wraplength=self.COL_0_WIDTH - 20, justify=LEFT,
                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, foreground="gray")
        
        # Remove button
        remove_btn = Button(self.frame.viewPort, text=_("Remove"))
        remove_btn.grid(row=row, column=1, padx=5)
        
        def remove_handler(filepath=filepath):
            DirectoryNotes.remove_marked_file(self.base_dir, filepath)
            self.app_actions.toast(_("Removed marked file: {0}").format(basename))
            self._refresh_widgets()
        
        remove_btn.config(command=remove_handler)
        
        # Open button
        open_btn = Button(self.frame.viewPort, text=_("Open"))
        open_btn.grid(row=row, column=2, padx=5)
        
        def open_handler(filepath=filepath):
            if hasattr(self.app_actions, "get_window"):
                window = self.app_actions.get_window(base_dir=self.base_dir)
                if window is not None:
                    window.go_to_file(search_text=os.path.basename(filepath), exact_match=True)
                    window.media_canvas.focus()
                    self.app_actions.toast(_("Opened file: {0}").format(basename))
                    return
            # Fallback: open new window
            if hasattr(self.app_actions, "new_window"):
                self.app_actions.new_window(base_dir=self.base_dir, image_path=filepath)
                self.app_actions.toast(_("Opened file in new window: {0}").format(basename))
        
        open_btn.config(command=open_handler)
        
        self.marked_file_widgets.extend([file_label, path_label, remove_btn, open_btn])
    
    def _add_note_widget(self, filepath: str, note: str, row: int):
        """Add a widget row for a file note."""
        basename = os.path.basename(filepath)
        
        # File label
        file_label = Label(self.frame.viewPort)
        self._add_label(file_label, basename, row=row, column=0, wraplength=self.COL_0_WIDTH)
        
        # Path label
        path_label = Label(self.frame.viewPort)
        path_label['text'] = filepath
        path_label.grid(column=0, row=row + 1, sticky=W, padx=(20, 0))
        base_font = font.nametofont(path_label.cget("font"))
        small_font = base_font.copy()
        small_font.configure(size=int(base_font['size'] * 0.85))
        path_label.config(font=small_font, wraplength=self.COL_0_WIDTH - 20, justify=LEFT,
                         bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR, foreground="gray")
        
        # Note text (read-only display)
        note_frame = Frame(self.frame.viewPort)
        note_frame.grid(row=row + 2, column=0, columnspan=3, sticky="ew", padx=(20, 0), pady=5)
        
        note_text = Text(note_frame, height=3, wrap="word", width=70)
        note_text.insert("1.0", note)
        note_text.config(state="disabled", bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                        insertbackground=AppStyle.FG_COLOR)
        note_text.pack(side=LEFT, fill="both", expand=True)
        
        # Edit button
        edit_btn = Button(self.frame.viewPort, text=_("Edit Note"))
        edit_btn.grid(row=row, column=1, padx=5)
        
        def edit_handler(filepath=filepath, current_note=note):
            self._edit_note_dialog(filepath, current_note)
        
        edit_btn.config(command=edit_handler)
        
        # Remove button
        remove_btn = Button(self.frame.viewPort, text=_("Remove Note"))
        remove_btn.grid(row=row, column=2, padx=5)
        
        def remove_handler(filepath=filepath):
            DirectoryNotes.remove_file_note(self.base_dir, filepath)
            self.app_actions.toast(_("Removed note for: {0}").format(basename))
            self._refresh_widgets()
        
        remove_btn.config(command=remove_handler)
        
        # Open button
        open_btn = Button(self.frame.viewPort, text=_("Open"))
        open_btn.grid(row=row + 1, column=1, padx=5)
        
        def open_handler(filepath=filepath):
            if hasattr(self.app_actions, "get_window"):
                window = self.app_actions.get_window(base_dir=self.base_dir)
                if window is not None:
                    window.go_to_file(search_text=os.path.basename(filepath), exact_match=True)
                    window.media_canvas.focus()
                    self.app_actions.toast(_("Opened file: {0}").format(basename))
                    return
            # Fallback: open new window
            if hasattr(self.app_actions, "new_window"):
                self.app_actions.new_window(base_dir=self.base_dir, image_path=filepath)
                self.app_actions.toast(_("Opened file in new window: {0}").format(basename))
        
        open_btn.config(command=open_handler)
        
        self.note_widgets.extend([file_label, path_label, note_frame, note_text, edit_btn, remove_btn, open_btn])
    
    def _edit_note_dialog(self, filepath: str, current_note: str):
        """Open a dialog to edit a file note."""
        from tkinter import Toplevel, messagebox
        
        dialog = Toplevel(self.master)
        dialog.title(_("Edit Note - {0}").format(os.path.basename(filepath)))
        dialog.geometry("600x400")
        dialog.configure(bg=AppStyle.BG_COLOR)
        
        # File path label
        path_label = Label(dialog, text=filepath, wraplength=580, justify=LEFT,
                          bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
        path_label.pack(pady=10, padx=10, anchor=W)
        
        # Note text area
        note_text = Text(dialog, wrap="word", height=15, width=70)
        note_text.insert("1.0", current_note)
        note_text.pack(pady=10, padx=10, fill="both", expand=True)
        note_text.config(bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR,
                        insertbackground=AppStyle.FG_COLOR)
        note_text.focus_set()
        
        # Buttons frame
        btn_frame = Frame(dialog)
        btn_frame.pack(pady=10)
        
        def save_note():
            new_note = note_text.get("1.0", END).strip()
            DirectoryNotes.set_file_note(self.base_dir, filepath, new_note)
            self.app_actions.toast(_("Note saved for: {0}").format(os.path.basename(filepath)))
            dialog.destroy()
            self._refresh_widgets()
        
        def cancel():
            dialog.destroy()
        
        save_btn = Button(btn_frame, text=_("Save"), command=save_note)
        save_btn.pack(side=LEFT, padx=5)
        
        cancel_btn = Button(btn_frame, text=_("Cancel"), command=cancel)
        cancel_btn.pack(side=LEFT, padx=5)
        
        # Bind Enter to save (Ctrl+Enter)
        def on_ctrl_enter(event):
            save_note()
        
        note_text.bind("<Control-Return>", on_ctrl_enter)
        dialog.bind("<Escape>", lambda e: cancel())
    
    def _add_label(self, label_ref, text, row=0, column=0, wraplength=500, header=False):
        """Helper to add a label with consistent styling."""
        label_ref['text'] = text
        label_ref.grid(column=column, row=row, sticky=W, padx=5, pady=2)
        base_font = font.nametofont(label_ref.cget("font"))
        if header:
            label_font = base_font.copy()
            label_font.configure(weight="bold")
            label_ref.config(font=label_font)
        label_ref.config(wraplength=wraplength, justify=LEFT, bg=AppStyle.BG_COLOR, fg=AppStyle.FG_COLOR)
    
    def _clear_widgets(self):
        """Clear all widgets."""
        for widget in self.marked_file_widgets + self.note_widgets:
            try:
                widget.destroy()
            except Exception:
                pass
        self.marked_file_widgets = []
        self.note_widgets = []
    
    def _refresh_widgets(self):
        """Refresh all widgets."""
        self._clear_widgets()
        # Clear the frame and rebuild
        for widget in self.frame.viewPort.winfo_children():
            widget.destroy()
        self._add_widgets()
        self.master.update()
    
    def export_to_file(self):
        """Export notes to a text file."""
        default_filename = os.path.join(self.base_dir, f"{os.path.basename(self.base_dir) or 'root'}_notes.txt")
        output_path = filedialog.asksaveasfilename(
            title=_("Export Directory Notes"),
            defaultextension=".txt",
            initialfile=os.path.basename(default_filename),
            initialdir=self.base_dir
        )
        if output_path:
            try:
                exported_path = DirectoryNotes.export_to_text(self.base_dir, output_path)
                self.app_actions.toast(_("Exported notes to: {0}").format(exported_path))
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror(_("Export Error"), _("Failed to export notes: {0}").format(str(e)))
    
    def import_from_text_file(self):
        """Import marked files from a text file."""
        from tkinter import messagebox
        
        file_path = filedialog.askopenfilename(
            title=_("Import Marked Files from Text File"),
            filetypes=[(_("Text files"), "*.txt"), (_("All files"), "*.*")],
            initialdir=self.base_dir
        )
        if not file_path:
            return
        
        try:
            # Ask if user wants recursive search
            recursive = messagebox.askyesno(
                _("Import Options"),
                _("Search recursively in subdirectories for matching filenames?")
            )
            
            added_count, not_found_count, not_found_filenames = DirectoryNotes.import_from_text_file(
                self.base_dir, file_path, recursive=recursive
            )
            
            message = _("Imported {0} files.").format(added_count)
            if not_found_count > 0:
                message += "\n\n" + _("{0} filenames not found:").format(not_found_count)
                # Show first 10 not found filenames
                display_not_found = not_found_filenames[:10]
                message += "\n" + "\n".join(display_not_found)
                if len(not_found_filenames) > 10:
                    message += "\n" + _("... and {0} more").format(len(not_found_filenames) - 10)
            
            messagebox.showinfo(_("Import Complete"), message)
            self.app_actions.toast(_("Imported {0} marked files").format(added_count))
            self._refresh_widgets()
        except Exception as e:
            messagebox.showerror(_("Import Error"), _("Failed to import from text file: {0}").format(str(e)))
    
    def import_from_json_file(self):
        """Import marked files from a JSON file."""
        from tkinter import messagebox
        
        file_path = filedialog.askopenfilename(
            title=_("Import Marked Files from JSON File"),
            filetypes=[(_("JSON files"), "*.json"), (_("All files"), "*.*")],
            initialdir=self.base_dir
        )
        if not file_path:
            return
        
        try:
            added_count, invalid_count, invalid_paths = DirectoryNotes.import_from_json_file(
                self.base_dir, file_path
            )
            
            message = _("Imported {0} files.").format(added_count)
            if invalid_count > 0:
                message += "\n\n" + _("{0} invalid or missing file paths:").format(invalid_count)
                # Show first 10 invalid paths
                display_invalid = invalid_paths[:10]
                message += "\n" + "\n".join(display_invalid)
                if len(invalid_paths) > 10:
                    message += "\n" + _("... and {0} more").format(len(invalid_paths) - 10)
            
            messagebox.showinfo(_("Import Complete"), message)
            self.app_actions.toast(_("Imported {0} marked files").format(added_count))
            self._refresh_widgets()
        except Exception as e:
            messagebox.showerror(_("Import Error"), _("Failed to import from JSON file: {0}").format(str(e)))
    
    def close_window(self, event=None):
        """Close the window."""
        self.master.destroy()

