class AppStyle:
    IS_DEFAULT_THEME = False
    LIGHT_THEME = "light"
    DARK_THEME = "dark"
    BG_COLOR = "#26242f"
    FG_COLOR = "white"
    
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
