import os
import gettext

from .settings import settings

this_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(this_dir)
locale_dir = os.path.join(parent_dir, "locales")

gettext.bindtextdomain(settings.APP_LOCALE, localedir=locale_dir)
gettext.textdomain(settings.APP_LOCALE)
