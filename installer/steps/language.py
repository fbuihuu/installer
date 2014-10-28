# -*- coding: utf-8 -*-
#

from . import Step
from installer import l10n
from installer.settings import settings


class LanguageStep(Step):

    provides = ["language"]

    @property
    def name(self):
        return _("Language")

    def _process(self):
        # Nothing to do here since most of the actions are done later
        # by localization step. Even changing the keyboard layout
        # depends on the frontend used.
        country = l10n.country_names[settings.Localization.country]
        self.logger.info(_("set location to %s") % country)
