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

    def __init__(self, ui, view):
        BaseMenu.__init__(self, ui, view)
        self._mounted_partitions = []
        self._pacstrap = None
        self._root = None

    @property
    def name(self):
        return _("Installation")

    def _do_mount_partitions(self):
        lst = [ (p.name, p) for p in partition.partitions if p.device ]
        lst.sort(key=itemgetter(0))

        for name, part in lst:
            mountpoint = self._root + name
            if name != "/" and not os.path.exists(mountpoint):
                os.mkdir(mountpoint)
            self.logger.debug(_("mounting %s") % name)
            part.device.mount(mountpoint)
            self._mounted_partitions.append(part)

    def _do_umount_partitions(self):
        for part in reversed(self._mounted_partitions):
            mntpnt = part.device.umount()

    def _do_pacstrap(self):
        self.logger.info("collecting information...")
        pacstrap = Popen("pacstrap %s base" % self._root, shell=True, stdout=PIPE)
        self._pacstrap = pacstrap

        #
        # Note: don't use an iterate over file object construct since
        # it uses a hidden read-ahead buffer which won't play well
        # with long running process with limited outputs such as
        # pacstrap.  See:
        # http://stackoverflow.com/questions/1183643/unbuffered-read-from-process-using-subprocess-in-python
        #
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
            self.set_completion(2 + count * 97 / total)

        # wait for pacstrap to exit
        self._pacstrap = None
        return pacstrap.wait()

    def __genfstab(self, partitions):
        fstab = []
        for part in partitions:
            if part.device.partuuid:
                source = "PARTUUID=" + part.device.partuuid
            elif part.device.partlabel:
                source = "PARTLABEL=" + part.device.partlabel
            elif part.device.uuid:
                source = "UUID=" + part.device.fsuuid
            elif part.device.label:
                source = "LABEL=" + part.device.fslabel
            else:
                source = part.device.devpath

            options = check_output("findmnt -cvuno OPTIONS " + part.device.devpath, shell=True)
            options = options.split()[0]

            target = part.name
            fstype = part.device.filesystem
            dump   = 0
            passno = 1 if target == "/" else 2

            fstab.append("%-20s\t%-10s %-10s %-10s\t%d %d" % (source, target,
                                                              fstype, options,
                                                              dump, passno))
        return fstab

    def _do_fstab(self):
        with open(os.path.join(self._root, 'etc/fstab'), 'w') as f:
            for entry in self.__genfstab(self._mounted_partitions):
                print >>f, entry, '\n'

    def _cancel_debug(self):
        self._should_stop = True

    def _process_debug(self):
        import time

        self._should_stop = False
        for i in range(2, 101):
            self.set_completion(i)
            time.sleep(0.2)
            if self._should_stop:
                self.set_completion(0)
                self._failed()
                return
        self._done()
        return

    def _cancel(self):
        if self._pacstrap:
            self._pacstrap.terminate()

    def _process(self):
        self.set_completion(1)

        self._root = mkdtemp()
        self.logger.debug(_("creating temp dir at %s") % self._root)

        self._do_mount_partitions()
        rv = self._do_pacstrap()
        if rv:
            self.logger.debug("pacstrap failed with status %d" % rv)
            self.logger.critical("failed")
            self.state = self._STATE_FAILED
        else:
            self._do_fstab()
        self._do_umount_partitions()

        os.rmdir(self._root)
        self._root = None

        self.set_completion(100)
        #self.logger.info("done.")
        self.state = self._STATE_DONE

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

