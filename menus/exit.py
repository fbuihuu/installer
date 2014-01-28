# -*- coding: utf-8 -*-
#

from menus import BaseMenu
import partition
from subprocess import check_call


class ExitMenu(BaseMenu):

    # FIXME: this should depends on all existing provides.
    requires = ["rootfs"]

    def __init__(self, ui, view):
        BaseMenu.__init__(self, ui, view)

    @property
    def name(self):
        return _("Exit")

    def _cancel(self):
        return

    def _process(self):
        action = self._ui.installer.data["exit/action"]
        if action == "Quit":
            self._done("quitting...")
            self._ui.quit()
        elif action == "Reboot":
            self._done("rebooting...")
            # check_call("systemctl reboot", shell=True)
        elif action == "Shutdown":
            self._done("shutting down...")
            # check_call("systemctl poweroff", shell=True)
