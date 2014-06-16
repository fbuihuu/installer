# -*- coding: utf-8 -*-
#

from . import Step
from installer.settings import settings
import installer.system


class LanguageStep(Step):

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
        #  self.logger.info(_("switching keyboard layout to %s"), layout)
        #   system.keyboard.set_layout(layout)

        self._done(_("set location to %s") % zone)
