# -*- coding: utf-8 -*-
#

from subprocess import check_call

from . import Step
from installer import partition
from installer.settings import settings


class ExitStep(Step):

    # FIXME: this should depends on all existing provides.
    requires = ["password"]

    def __init__(self, ui):
        Step.__init__(self, ui)

    @property
    def name(self):
        return _("Exit")

    def _cancel(self):
        return

    def _process(self):
        action = settings.exit.action
        if action == "Quit":
            self._done("quitting...")
            self._exit = True
        elif action == "Reboot":
            self._done("rebooting...")
            # check_call(["systemctl", "reboot"])
        elif action == "Shutdown":
            self._done("shutting down...")
            # check_call(["systemctl", "poweroff"])
