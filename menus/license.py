# -*- coding: utf-8 -*-
#

from menus import BaseMenu


class LicenseMenu(BaseMenu):

    requires = ["language"]
    provides = ["license"]

    def __init__(self, ui, view):
        BaseMenu.__init__(self, ui, view)

    @property
    def name(self):
        return _("License")

    def _cancel(self):
        return

    def _process(self):
        if self._ui.installer.data["license"] == "accepted":
            self._done()
        else:
            self._failed()
