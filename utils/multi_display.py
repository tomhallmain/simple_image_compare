"""
Multi-display utilities for tkinter applications.

This module provides functionality to:
1. Detect which display a tkinter window is currently on
2. Position new Toplevel windows on the same display as their parent
3. Handle multi-monitor setups across different operating systems
4. SmartToplevel class that automatically handles positioning
"""

import tkinter as tk
import platform
import logging

logger = logging.getLogger(__name__)


class MultiDisplayManager:
    """
    Manages multi-display functionality for tkinter applications.
    """
    
    def __init__(self):
        self.system = platform.system().lower()
        self._display_info_cache = {}
    
    def get_window_display_info(self, window):
        """
        Get information about which display a window is currently on.
        
        Args:
            window: A tkinter window (Tk, Toplevel, etc.)
            
        Returns:
            dict: Display information containing:
                - display_index: Index of the display (0-based)
                - is_primary: Whether this is the primary display
                - bounds: (x, y, width, height) of the display
                - window_position: (x, y) of the window on this display
        """
        try:
            # Get window position
            window_x = window.winfo_x()
            window_y = window.winfo_y()
            
            # Get screen dimensions
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            
            # For now, we'll use a simple approach that works for most setups
            # In a true multi-monitor setup, this would need platform-specific code
            
            # Check if window is on primary display (coordinates 0,0 to screen_width, screen_height)
            if (0 <= window_x < screen_width and 0 <= window_y < screen_height):
                display_index = 0
                is_primary = True
                bounds = (0, 0, screen_width, screen_height)
                window_position = (window_x, window_y)
            else:
                # Window appears to be on a secondary display
                # This is a simplified approach - real multi-monitor detection
                # would require platform-specific APIs
                display_index = 1
                is_primary = False
                bounds = (0, 0, screen_width, screen_height)  # Simplified
                window_position = (window_x, window_y)
            
            return {
                'display_index': display_index,
                'is_primary': is_primary,
                'bounds': bounds,
                'window_position': window_position
            }
            
        except Exception as e:
            logger.error(f"Error getting window display info: {e}")
            # Return default primary display info
            return {
                'display_index': 0,
                'is_primary': True,
                'bounds': (0, 0, window.winfo_screenwidth(), window.winfo_screenheight()),
                'window_position': (window.winfo_x(), window.winfo_y())
            }
    
    def position_window_on_same_display(self, parent_window, new_window, 
                                      offset_x=50, offset_y=50, 
                                      center=False, geometry=None):
        """
        Position a new window on the same display as the parent window.
        
        Args:
            parent_window: The parent window to match display for
            new_window: The new window to position
            offset_x: X offset from parent window (default: 50)
            offset_y: Y offset from parent window (default: 50)
            center: If True, center the window on the display (default: False)
            geometry: Custom geometry string (e.g., "400x300"). If None, uses window's natural size
            
        Returns:
            str: The geometry string that was applied
        """
        # logger.debug(f"position_window_on_same_display called with offset_x={offset_x}, offset_y={offset_y}, center={center}")
        try:
            # Get parent window position and size
            parent_x = parent_window.winfo_x()
            parent_y = parent_window.winfo_y()
            parent_width = parent_window.winfo_width()
            parent_height = parent_window.winfo_height()
            
            # logger.debug(f"Parent window - x={parent_x}, y={parent_y}, width={parent_width}, height={parent_height}")
            
            if center:
                # Center the window on the same display as parent
                if geometry:
                    # Parse geometry string to get width and height
                    if 'x' in geometry and '+' in geometry:
                        size_part = geometry.split('+')[0]
                        width, height = map(int, size_part.split('x'))
                    elif 'x' in geometry:
                        width, height = map(int, geometry.split('x'))
                    else:
                        width, height = 400, 300  # Default size
                else:
                    # Use window's natural size
                    width = new_window.winfo_reqwidth()
                    height = new_window.winfo_reqheight()
                
                # Calculate center position
                center_x = parent_x + (parent_width - width) // 2
                center_y = parent_y + (parent_height - height) // 2
                
                # Ensure window stays within screen bounds
                screen_width = parent_window.winfo_screenwidth()
                screen_height = parent_window.winfo_screenheight()
                
                center_x = max(0, min(center_x, screen_width - width))
                center_y = max(0, min(center_y, screen_height - height))
                
                final_geometry = f"{width}x{height}+{center_x}+{center_y}"
            else:
                # Position with offset
                new_x = parent_x + offset_x
                new_y = parent_y + offset_y
                
                # For multi-display setups, we need to allow negative coordinates
                # Only apply minimal bounds checking to prevent windows from being completely off-screen
                # Don't clamp to screen bounds as that breaks multi-display positioning
                new_x = new_x  # Keep the calculated position
                new_y = max(0, new_y)  # Only prevent negative Y (title bar should be visible)
                
                if geometry:
                    # Use provided geometry with calculated position
                    if '+' in geometry:
                        size_part = geometry.split('+')[0]
                        final_geometry = f"{size_part}+{new_x}+{new_y}"
                    else:
                        final_geometry = f"{geometry}+{new_x}+{new_y}"
                else:
                    # Use window's natural size
                    width = new_window.winfo_reqwidth()
                    height = new_window.winfo_reqheight()
                    final_geometry = f"{width}x{height}+{new_x}+{new_y}"
            
            # Apply the geometry
            new_window.geometry(final_geometry)
            return final_geometry
            
        except Exception as e:
            logger.error(f"Error positioning window: {e}")
            # Fallback to simple offset positioning
            try:
                parent_x = parent_window.winfo_x()
                parent_y = parent_window.winfo_y()
                fallback_geometry = f"+{parent_x + offset_x}+{parent_y + offset_y}"
                new_window.geometry(fallback_geometry)
                return fallback_geometry
            except:
                return ""
    
    def get_display_bounds(self, window, display_index=0):
        """
        Get the bounds of a specific display.
        
        Args:
            window: A tkinter window (used to get screen info)
            display_index: Index of the display (0-based)
            
        Returns:
            tuple: (x, y, width, height) of the display
        """
        try:
            if display_index == 0:
                # Primary display
                return (0, 0, window.winfo_screenwidth(), window.winfo_screenheight())
            else:
                # For secondary displays, this is simplified
                # Real implementation would need platform-specific code
                screen_width = window.winfo_screenwidth()
                screen_height = window.winfo_screenheight()
                return (screen_width, 0, screen_width, screen_height)
        except Exception as e:
            logger.error(f"Error getting display bounds: {e}")
            return (0, 0, window.winfo_screenwidth(), window.winfo_screenheight())
    
    def is_window_on_primary_display(self, window):
        """
        Check if a window is on the primary display.
        
        Args:
            window: A tkinter window
            
        Returns:
            bool: True if on primary display, False otherwise
        """
        try:
            x = window.winfo_x()
            y = window.winfo_y()
            screen_width = window.winfo_screenwidth()
            screen_height = window.winfo_screenheight()
            
            return (0 <= x < screen_width and 0 <= y < screen_height)
        except Exception as e:
            logger.error(f"Error checking primary display: {e}")
            return True  # Assume primary if we can't determine


# Global instance for easy access
display_manager = MultiDisplayManager()


class SmartToplevel(tk.Toplevel):
    """
    A Toplevel subclass that automatically positions itself on the same display as its parent.
    
    This class extends tkinter's Toplevel to provide automatic multi-display positioning.
    Simply use SmartToplevel instead of Toplevel, and it will automatically position
    itself on the same display as its parent window.
    
    Usage:
        # Instead of: new_window = tk.Toplevel(parent)
        new_window = SmartToplevel(parent, title="My Window", geometry="400x300")
    """
    
    def __init__(self, parent=None, title=None, geometry=None, 
                 offset_x=50, offset_y=50, center=False, 
                 auto_position=True, **kwargs):
        """
        Initialize a SmartToplevel window.
        
        Args:
            parent: Parent window (used for display detection and positioning)
            title: Window title
            geometry: Window geometry string (e.g., "400x300")
            offset_x: X offset from parent window (default: 50)
            offset_y: Y offset from parent window (default: 50)
            center: If True, center the window on the display (default: False)
            auto_position: If True, automatically position on same display (default: True)
            **kwargs: Additional arguments passed to Toplevel constructor
        """
        
        try:
            # Import AppStyle here to avoid circular imports
            from utils.app_style import AppStyle
            
            # Set default styling if not provided in kwargs
            if 'bg' not in kwargs:
                kwargs['bg'] = AppStyle.BG_COLOR
        except ImportError as e:
            logger.warning(f"Error setting default styling: {e}")
        
        # Initialize the Toplevel
        super().__init__(parent, **kwargs)
        
        # Set title if provided
        if title:
            self.title(title)
        
        # Set geometry if provided
        if geometry:
            self.geometry(geometry)
        
        # Debug logging before positioning condition
        if parent:
            try:
                parent_x = parent.winfo_x()
                parent_y = parent.winfo_y()
            except Exception as e:
                logger.warning(f"Could not get parent position: {e}")
        
        # Position on the same display as parent (if auto_position is True)
        if parent and auto_position:
            try:
                # Debug: Log parent window position
                # parent_x = parent.winfo_x()
                # parent_y = parent.winfo_y()
                # logger.debug(f"Parent window position: ({parent_x}, {parent_y})")
                
                display_manager.position_window_on_same_display(
                    parent, self, 
                    offset_x=offset_x, 
                    offset_y=offset_y, 
                    center=center,
                    geometry=geometry
                )
                
            except Exception as e:
                logger.warning(f"Failed to position SmartToplevel on same display: {e}")
                # Fallback to simple offset positioning
                try:
                    parent_x = parent.winfo_x()
                    parent_y = parent.winfo_y()
                    fallback_geometry = f"+{parent_x + offset_x}+{parent_y + offset_y}"
                    self.geometry(fallback_geometry)
                    logger.debug(f"Fallback positioning: {fallback_geometry}")
                except Exception as fallback_e:
                    logger.warning(f"Fallback positioning also failed: {fallback_e}")
                    pass  # Use default positioning
        else:
            logger.debug(f"Skipping positioning - parent={parent}, auto_position={auto_position}")
    
    def get_display_info(self):
        """
        Get information about which display this window is currently on.
        
        Returns:
            dict: Display information (same format as MultiDisplayManager.get_window_display_info)
        """
        return display_manager.get_window_display_info(self)
    
    def is_on_primary_display(self):
        """
        Check if this window is on the primary display.
        
        Returns:
            bool: True if on primary display, False otherwise
        """
        return display_manager.is_window_on_primary_display(self)
    
    def reposition_on_same_display(self, parent, offset_x=50, offset_y=50, center=False):
        """
        Reposition this window on the same display as the given parent.
        
        Args:
            parent: Parent window to match display for
            offset_x: X offset from parent window (default: 50)
            offset_y: Y offset from parent window (default: 50)
            center: If True, center the window on the display (default: False)
        """
        try:
            display_manager.position_window_on_same_display(
                parent, self, 
                offset_x=offset_x, 
                offset_y=offset_y, 
                center=center
            )
        except Exception as e:
            logger.warning(f"Failed to reposition SmartToplevel: {e}")
    
    def position_on_same_display(self, parent, offset_x=50, offset_y=50, center=False):
        """
        Position this window on the same display as the given parent.
        This is a convenience method that can be called after window creation.
        
        Args:
            parent: Parent window to match display for
            offset_x: X offset from parent window (default: 50)
            offset_y: Y offset from parent window (default: 50)
            center: If True, center the window on the display (default: False)
        """
        self.reposition_on_same_display(parent, offset_x, offset_y, center)
    
    def set_geometry_preserving_position(self, geometry):
        """
        Set the window geometry while preserving the current position.
        
        This is useful when you want to change the size of a window that has
        already been positioned by SmartToplevel, without losing the positioning.
        
        Args:
            geometry: New geometry string (e.g., "700x600" or "500x400")
        """
        current_geometry = self.geometry()
        
        if '+' in current_geometry:
            # Extract position from current geometry and apply new size
            position_part = current_geometry.split('+', 1)[1]  # Get everything after the first '+'
            new_geometry = f"{geometry}+{position_part}"
            self.geometry(new_geometry)
        else:
            # No position set yet, just set size
            self.geometry(geometry)
    
    def center_on_display(self, width=None, height=None):
        """
        Center the window on the same display as its parent.
        
        Args:
            width: Desired width (if None, uses current width)
            height: Desired height (if None, uses current height)
        """
        if not self.master:
            return
            
        try:
            # Get parent window position and size
            parent_x = self.master.winfo_x()
            parent_y = self.master.winfo_y()
            parent_width = self.master.winfo_width()
            parent_height = self.master.winfo_height()
            
            # Get current or specified dimensions
            if width is None:
                width = self.winfo_width()
            if height is None:
                height = self.winfo_height()
            
            # Calculate center position on the same display as parent
            center_x = parent_x + (parent_width - width) // 2
            center_y = parent_y + (parent_height - height) // 2
            
            # Apply the centered geometry
            new_geometry = f"{width}x{height}+{center_x}+{center_y}"
            self.geometry(new_geometry)
            
        except Exception as e:
            logger.warning(f"Failed to center window on display: {e}")


class SmartToplevelFactory:
    """
    Factory class for creating SmartToplevel windows with different positioning strategies.
    
    This provides a convenient way to create windows with common positioning patterns.
    """
    
    @staticmethod
    def create_offset(parent, title=None, geometry=None, offset_x=50, offset_y=50, **kwargs):
        """
        Create a SmartToplevel positioned with an offset from the parent.
        
        Args:
            parent: Parent window
            title: Window title
            geometry: Window geometry
            offset_x: X offset from parent
            offset_y: Y offset from parent
            **kwargs: Additional Toplevel arguments
            
        Returns:
            SmartToplevel: The created window
        """
        return SmartToplevel(parent, title, geometry, offset_x, offset_y, center=False, **kwargs)
    
    @staticmethod
    def create_centered(parent, title=None, geometry=None, **kwargs):
        """
        Create a SmartToplevel centered on the same display as the parent.
        
        Args:
            parent: Parent window
            title: Window title
            geometry: Window geometry
            **kwargs: Additional Toplevel arguments
            
        Returns:
            SmartToplevel: The created window
        """
        return SmartToplevel(parent, title, geometry, center=True, **kwargs)
    
    @staticmethod
    def create_dialog(parent, title=None, geometry="400x300", **kwargs):
        """
        Create a SmartToplevel suitable for dialogs (centered, modal-like).
        
        Args:
            parent: Parent window
            title: Window title
            geometry: Window geometry
            **kwargs: Additional Toplevel arguments
            
        Returns:
            SmartToplevel: The created window
        """
        window = SmartToplevel(parent, title, geometry, center=True, **kwargs)
        # Make it behave more like a dialog
        window.transient(parent)
        window.grab_set()
        return window


def create_window_on_same_display(parent_window, window_class, *args, **kwargs):
    """
    Convenience function to create a new window on the same display as parent.
    
    Args:
        parent_window: The parent window to match display for
        window_class: The window class to instantiate (e.g., tk.Toplevel)
        *args: Arguments to pass to window_class constructor
        **kwargs: Keyword arguments to pass to window_class constructor
        
    Returns:
        The created window instance
    """
    # If using SmartToplevel, it handles positioning automatically
    if window_class == SmartToplevel:
        return window_class(parent_window, *args, **kwargs)
    
    # For other window classes, create and position manually
    new_window = window_class(parent_window, *args, **kwargs)
    display_manager.position_window_on_same_display(parent_window, new_window)
    return new_window


def position_toplevel_on_same_display(parent_window, toplevel, **position_kwargs):
    """
    Convenience function to position an existing Toplevel on the same display.
    
    Args:
        parent_window: The parent window to match display for
        toplevel: The Toplevel window to position
        **position_kwargs: Additional arguments for position_window_on_same_display
    """
    return display_manager.position_window_on_same_display(
        parent_window, toplevel, **position_kwargs
    )


# Example usage and testing functions
def test_multi_display():
    """Test function to demonstrate multi-display functionality."""
    root = tk.Tk()
    root.title("Multi-Display Test")
    root.geometry("400x300")
    
    def create_test_window():
        # Method 1: Using the convenience function
        new_window = create_window_on_same_display(
            root, tk.Toplevel, 
            bg='lightblue'
        )
        new_window.title("Test Window (Method 1)")
        
        # Add some content
        tk.Label(new_window, text="This window should appear on the same display as the parent").pack(pady=20)
        tk.Button(new_window, text="Close", command=new_window.destroy).pack()
    
    def create_centered_window():
        # Method 2: Using the manager directly with centering
        new_window = tk.Toplevel(root, bg='lightgreen')
        new_window.title("Centered Test Window")
        
        # Position it centered on the same display
        display_manager.position_window_on_same_display(
            root, new_window, center=True, geometry="300x200"
        )
        
        # Add some content
        tk.Label(new_window, text="This window is centered on the same display").pack(pady=20)
        tk.Button(new_window, text="Close", command=new_window.destroy).pack()
    
    def show_display_info():
        # Show information about the current display
        info = display_manager.get_window_display_info(root)
        info_text = f"""Display Info:
Index: {info['display_index']}
Primary: {info['is_primary']}
Bounds: {info['bounds']}
Window Position: {info['window_position']}"""
        
        info_window = tk.Toplevel(root, bg='lightyellow')
        info_window.title("Display Information")
        display_manager.position_window_on_same_display(root, info_window, offset_x=100, offset_y=100)
        
        tk.Label(info_window, text=info_text, justify='left').pack(pady=20, padx=20)
        tk.Button(info_window, text="Close", command=info_window.destroy).pack()
    
    # Create test buttons
    tk.Button(root, text="Create Test Window", command=create_test_window).pack(pady=10)
    tk.Button(root, text="Create Centered Window", command=create_centered_window).pack(pady=10)
    tk.Button(root, text="Show Display Info", command=show_display_info).pack(pady=10)
    tk.Button(root, text="Exit", command=root.quit).pack(pady=10)
    
    root.mainloop()


if __name__ == "__main__":
    test_multi_display()
