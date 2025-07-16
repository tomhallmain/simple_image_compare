class AppStyle:
    IS_DEFAULT_THEME = False
    LIGHT_THEME = "light"
    DARK_THEME = "dark"
    BG_COLOR = "#26242f"
    FG_COLOR = "white"

    @staticmethod
    def get_theme_name():
        return AppStyle.DARK_THEME if AppStyle.IS_DEFAULT_THEME else AppStyle.LIGHT_THEME
