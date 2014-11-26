# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

from . import Step
from installer import l10n
from installer.settings import settings


class LanguageStep(Step):

    provides = ["language"]

    @property
    def name(self):
        return _("Language")

    def _process(self, locale):
        #
        # Set the current locale and language of the installer. This
        # also initializes the Localization's setting default values
        # if the user hasn't through the config file.
        #
        # Setting the locale may fail if it's not installed on the
        # host system, but that's not an issue since we're interested
        # mostly in setting up the language.
        #
        l10n.set_locale(locale)
        l10n.set_language(locale)
