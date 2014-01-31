# -*- coding: utf-8 -*-
#

import os
from subprocess import *
from steps import Step


class PasswordStep(Step):

    requires = []
    provides = ["password"]

    def __init__(self, ui):
        Step.__init__(self, ui)

    @property
    def name(self):
        return _("Password")

    def _cancel(self):
        pass

    def _process(self):
        # mount rootfs

        # echo "root:<password>" | chpasswd (-g)

        # umount rootfs
        return
