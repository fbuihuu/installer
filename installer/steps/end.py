# -*- coding: utf-8 -*-
#

from subprocess import check_call

from . import Step
from installer import partition
from installer.settings import settings


class EndStep(Step):

    # FIXME: this should depends on all existing provides.
    requires = ["password"]

    @property
    def name(self):
        return _("End")

    def _cancel(self):
        return

    def _process(self, action):
        if action == 'quit':
            self._done("quitting...")
            self._exit = True
        elif action == 'reboot':
            self._done("rebooting...")
            # check_call(["systemctl", "reboot"])
        elif action == 'shutdown':
            self._done("shutting down...")
            # check_call(["systemctl", "poweroff"])
        else:
            self._failed("BUG: unknown end action '%s'" % action)
