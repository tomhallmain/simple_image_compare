class AppStyle:
    IS_DEFAULT_THEME = False
    LIGHT_THEME = "light"
    DARK_THEME = "dark"
    BG_COLOR = "#26242f"
    FG_COLOR = "white"
    TOAST_COLOR_WARNING = "#8B4513"  # (dark orange/saddle brown)
    TOAST_COLOR_SUCCESS = "#2d5016"  # (dark green)
    
    # Custom button style names
    HEADER_BUTTON_STYLE = "Header.TButton"

    @staticmethod
    def get_theme_name():
        return AppStyle.DARK_THEME if AppStyle.IS_DEFAULT_THEME else AppStyle.LIGHT_THEME
    
    @staticmethod
    def setup_custom_button_styles(style_instance):
        """Setup custom button styles for the application."""
        style_instance.configure(AppStyle.HEADER_BUTTON_STYLE,
                              background=AppStyle.BG_COLOR, 
                              foreground=AppStyle.FG_COLOR,
                              borderwidth=2,
                              focuscolor=AppStyle.BG_COLOR)
    
    @staticmethod
    def setup_combobox_style(combobox, style_instance=None):
        """
        Setup combobox style for the application and apply it to the given combobox.
        
        Args:
            combobox: The ttk.Combobox widget to style
            style_instance: Optional ttk.Style instance. If None, creates a new one.
        """
        from tkinter.ttk import Style
        if style_instance is None:
            style_instance = Style()
        style_instance.configure("TCombobox", 
                                fieldbackground=AppStyle.BG_COLOR, 
                                foreground=AppStyle.FG_COLOR, 
                                background=AppStyle.BG_COLOR)
        combobox.configure(style="TCombobox")
        return style_instance