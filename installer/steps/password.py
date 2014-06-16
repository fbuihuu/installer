# -*- coding: utf-8 -*-
#

from . import Step
from installer.settings import settings


class PasswordStep(Step):

    requires = ["rootfs"]
    provides = ["password"]

    @property
    def name(self):
        return _("Password")

    def _cancel(self):
        pass

    def _process(self):
        self.logger.info(_("setting root's password"))
        password = settings.password.root
        cmd = "echo 'root:%s' | chpasswd" % password
        self._chroot(cmd, logger=None) # do not log root's password ;)

