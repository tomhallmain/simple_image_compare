import gettext
import os

from utils.utils import Utils

_locale = os.environ['LANG']
if not _locale or _locale == '':
    _locale = Utils.get_default_user_language()
elif _locale is not None and "_" in _locale:
    _locale = _locale[:_locale.index("_")]

class I18N:
    localedir = os.path.join(os.path.dirname(os.path.abspath(os.path.dirname(__file__))), 'locale')
    translate = gettext.translation('base', localedir, languages=[_locale])

    @staticmethod
    def install_locale(locale):
        translate = gettext.translation('base', I18N.localedir, languages=[locale], fallback=True)
        translate.install()
        print("Switched locale to: " + locale)

    @staticmethod
    def _(s):
#        return gettext.gettext(s)
        return I18N.translate.gettext(s)

    '''
    NOTE when gathering the translation strings, set _() == to gettext.gettext() instead of the above, and run:
    ```python C:\Python310\Tools\i18n\pygettext.py -d base -o locale\base.pot .```
    in the base directory. The POT output file can be used as source for the PO files in each locale.
    Then for each locale once the PO files are set up as desired, run:
    ```python C:\Python310\Tools\i18n\msgfmt.py -o base.mo base```
    in the deepest locale directory to produce the MO file from the PO file.
    '''
    