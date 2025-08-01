"""
Custom dialog implementations for the application.

This module contains custom dialog implementations that provide enhanced
functionality beyond what's available in standard Tkinter messagebox.
"""

from tkinter import Toplevel, Frame, Label, Button, messagebox

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
    # Create custom dialog
    dialog = Toplevel(master)
    dialog.title(title)
    dialog.geometry("400x200")
    dialog.resizable(False, False)
    dialog.transient(master)
    dialog.grab_set()
    
    # Center the dialog
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
    y = (dialog.winfo_screenheight() // 2) - (200 // 2)
    dialog.geometry(f"400x200+{x}+{y}")
    
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
    
    # Wait for dialog to close
    dialog.wait_window()
    return result[0] 