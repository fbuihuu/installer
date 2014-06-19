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

    def _cancel(self):
        pass

    def _process(self):
        country = l10n.country_names[settings.I18n.country]

        # Switch the keyboard layout accordingly.
        layout = settings.I18n.keyboard
        # if system.keyboard.get_layout() != layout:
        #  self.logger.info(_("switching keyboard layout to %s"), layout)
        #   system.keyboard.set_layout(layout)

        self._done(_("set location to %s") % country)
