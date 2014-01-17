# -*- coding: utf-8 -*-
#

import os
from operator import itemgetter
from subprocess import check_output, check_call, CalledProcessError
from tempfile import mkdtemp
from menus import BaseMenu
import partition


class InstallMenu(BaseMenu):

    def __init__(self, ui, callback):
        BaseMenu.__init__(self, ui, callback)

    def _do_mount_partitions(self, tmpdir):
        # Mount partitions starting with /
        lst = [ (p.name, p) for p in partition.partitions if p.device ]
        lst.sort(key=itemgetter(0))

        for name, part in lst:
            mountpoint = tmpdir + name
            if name != "/":
                os.mkdir(mountpoint)
            self.logger.debug(_("mounting %s") % name)
            part.device.mount(mountpoint)

    def process(self):
        self.logger.info(_("starting installation"))

        import time
        for i in range(101):
            self.set_completion(i)
            self.ui.redraw()
            time.sleep(0.1)
        return

        tmpdir = mkdtemp()
        self.logger.debug(_("creating temp dir at %s") % tmpdir)
        self._do_mount_partitions(tmpdir)

        # urpmi --root /mnt
        check_call("pacstrap %s base" % tmpdir, shell=True)

        # generate fstab

        # complete installation
        #    1/ root password
        #    2/ setup locale
        #    3/ setup timezone
        #    4/ regenerer initramfs (archlinux)
        #    5/ bootloader :(

        #for mntpnt, dev in mandatory_mountpoints.items():
        #    if mntpnt == "/":
        #        mntpnt = "/root"
        #    self.installer.data["partition" + mntpnt] = dev
        #
        #for mntpnt, dev in mandatory_mountpoints.items():
        #    if dev:
        #        self.installer.data["partition" + mntpnt] = dev

