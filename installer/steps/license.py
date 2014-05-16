# -*- coding: utf-8 -*-
#

from installer.settings import settings
from . import Step


class LicenseStep(Step):

    requires = ["language"]
    provides = ["license"]

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
            self._exit = True
            self._exit_delay = 3
