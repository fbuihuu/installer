# -*- coding: utf-8 -*-
#

from settings import settings
from steps import Step


class LicenseStep(Step):

    requires = ["language"]
    provides = ["license"]

    def __init__(self, ui):
        Step.__init__(self, ui)

    @property
    def name(self):
        return _("License")

    def _cancel(self):
        return

    def _process(self):
        if settings.License.status == "accepted":
            self._done(_("you accepted the terms of the license"))
        else:
            self._failed(_("you rejected the terms of the license, aborting"))
            self._ui.quit(3)
