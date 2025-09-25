"""
Custom dialog implementations for the application.

This module contains custom dialog implementations that provide enhanced
functionality beyond what's available in standard Tkinter messagebox.
"""

from tkinter import Frame, Label, Button, messagebox

from lib.multi_display import SmartToplevel
from utils.translations import I18N

_ = I18N._

def show_high_severity_dialog(master, title, message):
    """
    Show a custom dialog with red warning colors for high severity operations.
    
    Args:
        master: The parent window (Toplevel or Tk instance)
        title: The dialog title
        message: The dialog message
        
    Returns:
        messagebox.OK or messagebox.CANCEL depending on user choice
    """
    # Create custom dialog using SmartToplevel for multi-display positioning
    dialog = SmartToplevel(persistent_parent=master, center=True)
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.transient(master)
    dialog.grab_set()
    
    # Create main frame with red warning colors
    main_frame = Frame(dialog, bg="#ff4444", relief="raised", bd=2)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Warning icon and title
    title_frame = Frame(main_frame, bg="#ff4444")
    title_frame.pack(fill="x", padx=15, pady=(15, 10))
    
    warning_label = Label(title_frame, text="⚠️", font=("Arial", 24), bg="#ff4444", fg="white")
    warning_label.pack(side="left")
    
    title_label = Label(title_frame, text=title, font=("Arial", 14, "bold"), 
                       bg="#ff4444", fg="white", anchor="w")
    title_label.pack(side="left", padx=(10, 0))
    
    # Message
    message_label = Label(main_frame, text=message, font=("Arial", 10), 
                         bg="#ff4444", fg="white", wraplength=350, justify="left")
    message_label.pack(fill="both", expand=True, padx=15, pady=(0, 15))
    
    # Buttons
    button_frame = Frame(main_frame, bg="#ff4444")
    button_frame.pack(fill="x", padx=15, pady=(0, 15))
    
    result = [None]  # Use list to store result from button callbacks
    
    def on_ok():
        result[0] = messagebox.OK
        dialog.destroy()
        
    def on_cancel():
        result[0] = messagebox.CANCEL
        dialog.destroy()
    
    # OK button (red background)
    ok_button = Button(button_frame, text=_("OK"), command=on_ok, 
                      bg="#cc0000", fg="white", font=("Arial", 10, "bold"),
                      relief="raised", bd=2, padx=20, pady=5)
    ok_button.pack(side="right", padx=(10, 0))
    
    # Cancel button (gray background)
    cancel_button = Button(button_frame, text=_("Cancel"), command=on_cancel,
                          bg="#666666", fg="white", font=("Arial", 10),
                          relief="raised", bd=2, padx=20, pady=5)
    cancel_button.pack(side="right")
    
    # Set focus to cancel button for safety
    cancel_button.focus_set()
    
    # Bind Enter key to OK and Escape key to Cancel
    dialog.bind('<Return>', lambda e: on_ok())
    dialog.bind('<Escape>', lambda e: on_cancel())
    
    # Calculate dynamic geometry based on content
    dialog.update_idletasks()
    
    # Get the required size for the content
    required_width = max(400, title_label.winfo_reqwidth() + warning_label.winfo_reqwidth() + 100)
    required_height = (title_label.winfo_reqheight() + 
                      message_label.winfo_reqheight() + 
                      button_frame.winfo_reqheight() + 80)  # Add padding
    
    # Ensure minimum dimensions
    dialog_width = max(400, min(required_width, 600))
    dialog_height = max(200, min(required_height, 500))
    
    # Set the geometry - SmartToplevel with center=True will handle positioning
    dialog.set_geometry_preserving_position(f"{dialog_width}x{dialog_height}")
    
    # Wait for dialog to close
    dialog.wait_window()
    return result[0] 