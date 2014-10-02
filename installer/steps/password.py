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

    def _process(self):
        self.logger.info(_("setting root's password"))
        password = settings.Password.root
        args = ['sh', '-c', 'echo root:%s | chpasswd' % password]
        self._chroot(args, logger=None) # do not log root's password ;)

