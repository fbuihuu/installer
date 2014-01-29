# -*- coding: utf-8 -*-
#

import system
from steps import Step


class WelcomeStep(Step):

    provides = ["language"]

    def __init__(self, ui, view):
        Step.__init__(self, ui, view)

        self._country = None
        if self._ui.installer.data["localization/country"]:
            self.country = self._ui.installer.data["localization/country"]

    @property
    def name(self):
        return _("Language")

    def _do_country(self, place):
        self._country = place

        # Change the language of the whole ui.
        lang = self._ui.installer.data["localization/locale"]
        self._ui.language = lang

        # Switch the keyboard layout accordingly.
        layout = self._ui.installer.data["localization/keyboard"]
        # if system.keyboard.get_layout() != layout:
        #  self.logger.info(_("switching keyboard layout to %s") % layout)
        #   system.keyboard.set_layout(layout)

        self.logger.info(_("set location to %s"), place)

    def _cancel(self):
        pass

    def _process(self):
        place = self._ui.installer.data["localization/country"]
        if self._country != place:
            self._do_country(place)
        self._done()
