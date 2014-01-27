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
            self._done(_("you accepted the terms of the license"))
        else:
            self._failed(_("you rejected the terms of the license, aborting"))
            self._ui.quit(3)
