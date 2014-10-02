# -*- coding: utf-8 -*-
#

import atexit

from . import Step
from installer import partition
from installer.settings import settings, SettingsError
from installer.process import check_call


def reboot():
    check_call(["systemctl", "reboot"])

def poweroff():
    check_call(["systemctl", "poweroff"])

def quit():
    pass


class EndStep(Step):

    requires = ["rootfs"]

    @property
    def name(self):
        return _("End")

    def _process(self):
        action = settings.End.action
        if action == 'quit':
            func = quit
        elif action == 'reboot':
            func = reboot
        elif action == 'shutdown':
            func = poweroff
        else:
            raise SettingsError(_("Invalid end action '%s' specified" % self.name))

        atexit.register(func)

