# -*- coding: utf-8 -*-
#

from subprocess import check_call
from steps import Step
from partition import mount_rootfs, unmount_rootfs


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
        password = self._ui.installer.data['password/root']

        root = mount_rootfs()
        try:
            cmd = "echo 'root:%s' | chpasswd --root %s" % (password, root)
            check_call(cmd, shell=True)
            self.logger.info(_("root password updated"))
        finally:
            unmount_rootfs()

