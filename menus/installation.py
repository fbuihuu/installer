# -*- coding: utf-8 -*-
#

import os
import re
from operator import itemgetter
from subprocess import *
from tempfile import mkdtemp
from menus import BaseMenu
import partition


class InstallMenu(BaseMenu):

    requires = ["license"]
    provides = ["rootfs"]

    def __init__(self, ui, callback):
        BaseMenu.__init__(self, ui, callback)
        self._mounted_partitions = []
        self._pacstrap = None

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
            self._mounted_partitions.append(part)

    def _do_umount_partitions(self, tmpdir):
        for part in reversed(self._mounted_partitions):
            mntpnt = part.device.umount()
            os.rmdir(mntpnt)

    def _do_pacstrap(self, tmpdir):
        self.logger.info("collecting information...")
        pacstrap = Popen("pacstrap -c %s base" % tmpdir, shell=True, stdout=PIPE)

        # Note: don't use an iterate over file object construct since
        # it uses a hidden read-ahead buffer which won't play well
        # with long running process with few outputs such as pacstrap.
        # See:
        # http://stackoverflow.com/questions/1183643/unbuffered-read-from-process-using-subprocess-in-python
        total = 0
        pattern = re.compile(r'Packages \(([0-9]+)\)')
        while pacstrap.poll() is None:
            line = pacstrap.stdout.readline()
            if not line:
                break
            match = pattern.search(line)
            if match:
                total = int(match.group(1))
                self.set_completion(2)
                break

        count = 0
        total = total * 2
        pattern = re.compile(r'downloading |(re)?installing ')
        while pacstrap.poll() is None:
            line = pacstrap.stdout.readline()
            if not line:
                break
            match = pattern.match(line)
            if not match:
                continue

            self.logger.info(line.rstrip())
            if not line.startswith('downloading '):
                count = max(count, total/2)
            count += 1
            self.set_completion(count * 99 / total)

        # wait for pacstrap to exit
        return pacstrap.wait()

    def _do_fstab(self):
        pass

    def process(self):
        self.set_completion(1)

        tmpdir = mkdtemp()
        self.logger.debug(_("creating temp dir at %s") % tmpdir)

        self._do_mount_partitions(tmpdir)
        rv = self._do_pacstrap(tmpdir)
        if rv:
            self.logger.critical("pacstrap failed with status %d" % rv)
        else:
            self._do_fstab()
        self._do_umount_partitions(tmpdir)

        self.set_completion(100)
        return rv

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

