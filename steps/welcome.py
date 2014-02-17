# -*- coding: utf-8 -*-
#

from settings import settings
import system
from steps import Step
from l10n import country_dict


class WelcomeStep(Step):

    provides = ["language"]

    def __init__(self, ui):
        Step.__init__(self, ui)
        self._country = settings.I18n.country

    @property
    def name(self):
        return _("Language")

    def _do_country(self, place):
        self._country = place

        # Switch the keyboard layout accordingly.
        layout = settings.I18n.keyboard
        # if system.keyboard.get_layout() != layout:
        #  self.logger.info(_("switching keyboard layout to %s") % layout)
        #   system.keyboard.set_layout(layout)

        self.logger.info(_("set location to %s"), place)

    def _cancel(self):
        pass

    def _process(self):
        place = settings.I18n.country
        if self._country != place:
            self._do_country(place)
        self._done()
