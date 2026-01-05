"""
Simple tooltip implementation for Tkinter widgets.
"""
from tkinter import Toplevel, Label


class ToolTip:
    """Create a tooltip for a given widget."""
    
    def __init__(self, widget, text='widget info'):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0
        self._bind_events()
    
    def _bind_events(self):
        """Bind mouse events to show/hide tooltip."""
        self.widget.bind('<Enter>', self.enter)
        self.widget.bind('<Leave>', self.leave)
        self.widget.bind('<ButtonPress>', self.leave)
    
    def enter(self, event=None):
        """Show tooltip on mouse enter."""
        self.schedule()
    
    def leave(self, event=None):
        """Hide tooltip on mouse leave."""
        self.unschedule()
        self.hidetip()
    
    def schedule(self):
        """Schedule tooltip to appear after delay."""
        self.unschedule()
        self.id = self.widget.after(500, self.showtip)  # 500ms delay
    
    def unschedule(self):
        """Cancel scheduled tooltip."""
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)
    
    def showtip(self, event=None):
        """Display the tooltip."""
        x, y, cx, cy = self.widget.bbox("insert") if hasattr(self.widget, 'bbox') else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        # Create tooltip window
        self.tipwindow = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(True)  # Remove window decorations
        tw.wm_geometry("+%d+%d" % (x, y))
        
        label = Label(tw, text=self.text, justify='left',
                     background="#ffffe0", relief='solid', borderwidth=1,
                     font=("tahoma", "8", "normal"), wraplength=300)
        label.pack(ipadx=1)
    
    def hidetip(self):
        """Hide the tooltip."""
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def create_tooltip(widget, text):
    """Create a tooltip for the given widget."""
    return ToolTip(widget, text)

