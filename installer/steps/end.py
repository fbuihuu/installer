# -*- coding: utf-8 -*-
#

from subprocess import check_call

from . import Step
from installer import partition
from installer.settings import settings


class EndStep(Step):

    requires = ["rootfs"]

    @property
    def name(self):
        return _("End")

    def _cancel(self):
        return

    def _process(self):
        #
        # Installer exit is handled by the installer itself: urwid frontend
        # actually never calls this method.
        #
        return

