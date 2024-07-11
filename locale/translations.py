import gettext
import os

localedir = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'locale')
translate = gettext.translation('simple_image_compare', localedir, fallback=True)

def i18n(s, *args):
    return translate.gettext(s).format(*args)
