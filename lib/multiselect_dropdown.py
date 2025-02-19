from tkinter import Tk, Toplevel, Listbox, BOTH, END, LEFT, RIGHT, MULTIPLE, VERTICAL, Y
from tkinter.ttk import Button, Scrollbar

class MultiSelectDropdown:
    def __init__(self, parent, options, select_text="Select...", width=20, listbox_height=5,
                 row=1, column=1, sticky=None, selected=None, command=None):
        self.parent = parent
        self._options = options
        self.selected = list(selected) if selected else []
        self.select_text = select_text
        self.on_selection = command  # Custom callback storage

        # Validate initial selections
        self.selected = [item for item in self.selected if item in self._options]
        
        # Main button
        self.button = Button(
            parent, 
            text=self._get_button_text(), 
            width=width, 
            command=self.toggle_dropdown
        )
        if sticky is not None:
            self.button.grid(row=row, column=column, sticky=sticky)
        else:
            self.button.grid(row=row, column=column)

        # Popup management
        self.popup = None
        self.listbox = None
        self.listbox_height = listbox_height

    # New property for options with automatic UI update
    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, value):
        self._options = value
        self._sync_options_with_ui()  # Automatic UI update when options change

    def _get_button_text(self):
        return ', '.join(self.selected) if len(self.selected) > 0 else self.select_text

    def _sync_options_with_ui(self):
        """Update the Listbox contents and maintain valid selections"""
        # Filter out invalid selections
        self.selected = [item for item in self.selected if item in self._options]

        # Update button text
        self.button.config(text=self._get_button_text())

        # Update Listbox if it exists
        if self.listbox and self.popup.winfo_exists():
            self.listbox.delete(0, END)
            for option in self._options:
                self.listbox.insert(END, option)

            # Reselect valid items
            for i, option in enumerate(self._options):
                if option in self.selected:
                    self.listbox.selection_set(i)

    def set_options_and_selection(self, new_options, new_selection):
        """Atomically update both options and selections with validation"""
        self._options = new_options
        
        # Filter selections to only include valid options
        valid_selection = [item for item in new_selection if item in new_options]
        self.selected = valid_selection
        
        # Force UI synchronization
        self._sync_options_with_ui()

    def toggle_dropdown(self):
        if self.popup is None or not self.popup.winfo_exists():
            self.create_dropdown()
        else:
            self.destroy_dropdown()

    def create_dropdown(self):
        self.popup = Toplevel(self.parent)
        self.popup.overrideredirect(True)
        self._set_popup_position()

        self.listbox = Listbox(
            self.popup,
            selectmode=MULTIPLE,
            height=self.listbox_height,
            exportselection=False
        )
        
        # Insert current options
        for option in self._options:
            self.listbox.insert(END, option)

        # Set initial selections
        for i, option in enumerate(self._options):
            if option in self.selected:
                self.listbox.selection_set(i)

        scrollbar = Scrollbar(self.popup, orient=VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)

        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Event bindings
        self.listbox.bind('<<ListboxSelect>>', self.update_selection)
        self.popup.bind('<FocusOut>', self.on_focus_out)
        self.parent.bind('<Button-1>', self.check_click_outside)
        self.listbox.focus_set()

    def update_selection(self, event=None):
        selected_indices = self.listbox.curselection()
        self.selected = [self.listbox.get(i) for i in selected_indices]
        self.button.config(text=self._get_button_text())

        # Execute custom callback if provided
        if self.on_selection:
            self.on_selection()

    # Existing geometry management methods remain the same
    def _set_popup_position(self):
        x = self.button.winfo_rootx()
        y = self.button.winfo_rooty() + self.button.winfo_height()
        self.popup.geometry(f"+{x}+{y}")
        self.popup.geometry(f"{self.button.winfo_width()}x{y}")

    def destroy_dropdown(self, event=None):
        if self.popup:
            self.popup.destroy()
            self.popup = None
            self.parent.unbind('<Button-1>')

    def on_focus_out(self, event):
        if self.popup and not self.popup.focus_get():
            self.destroy_dropdown()

    def check_click_outside(self, event):
        x, y = event.x_root, event.y_root
        if not (self.button.winfo_containing(x, y) or 
                (self.popup and self.popup.winfo_containing(x, y))):
            self.destroy_dropdown()

    def get_selected(self):
        return self.selected

    def destroy(self):
        self.destroy_dropdown()
        if self.listbox is not None:
            self.listbox.destroy()
        self.button.destroy()

# Example Usage with new features
if __name__ == "__main__":
    root = Tk()
    root.title("Enhanced Multi-Select Dropdown")
    
    # 1. With default selections
    initial_options = ["Apple", "Banana", "Cherry"]
    dropdown = MultiSelectDropdown(
        root, 
        options=initial_options,
        selected=["Apple", "Banana"],  # Default values
        listbox_height=4,
        command=lambda: print("Selection changed:", dropdown.get_selected())
    )
    
    # 2. Update options later (automatically reflects in UI)
    def update_options():
        new_options = ["Grapes", "Mango", "Orange", "Pineapple"]
        dropdown.options = new_options  # Property setter handles UI update
    
    Button(root, text="Update Options", command=update_options).pack(pady=5)
    
    root.mainloop()