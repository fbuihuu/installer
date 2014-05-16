# -*- coding: utf-8 -*-
#

from . import Step
from installer.partition import mount_rootfs, unmount_rootfs
from installer.settings import settings
from installer.process import monitor_chroot


class PasswordStep(Step):

    requires = ["rootfs"]
    provides = ["password"]

    @property
    def name(self):
        return _("Password")

    def _cancel(self):
        pass

    def _process(self):
        password = settings.password.root

        root = mount_rootfs()
        try:
            self.logger.info(_("setting root's password"))
            cmd = "echo 'root:%s' | chpasswd" % password
            # Make sure to not log root's password ;)
            monitor_chroot(root, cmd, logger=None)
        finally:
            unmount_rootfs()

