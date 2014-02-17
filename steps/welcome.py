# -*- coding: utf-8 -*-
#

from settings import settings
import system
from steps import Step
from l10n import country_dict


class WelcomeStep(Step):

    provides = ["language"]

    @property
    def name(self):
        return _("Language")

    def _cancel(self):
        pass

    def _process(self):
        zone = settings.I18n.timezone.split('/')[0]

        # Switch the keyboard layout accordingly.
        layout = settings.I18n.keyboard
        # if system.keyboard.get_layout() != layout:
        #  self.logger.info(_("switching keyboard layout to %s") % layout)
        #   system.keyboard.set_layout(layout)

        self._done(_("set location to %s") % zone)
