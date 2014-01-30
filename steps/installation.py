# -*- coding: utf-8 -*-
#

import os
import re
from operator import itemgetter
from subprocess import *
from tempfile import mkdtemp
from steps import Step
import partition


class InstallStep(Step):

    requires = ["license"]
    provides = ["rootfs"]

    def __init__(self, ui):
        Step.__init__(self, ui)
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

        cmd = "pacstrap %s base" % self._root
        self._pacstrap = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT)
        pacstrap = self._pacstrap

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
            self.logger.info(line.rstrip())

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
            self.logger.info(line.rstrip())

            match = pattern.match(line)
            if not match:
                continue
            if not line.startswith('downloading '):
                count = max(count, total/2)
            count += 1
            self.set_completion(2 + count * 97 / total)

        # wait for pacstrap to exit
        self._pacstrap = None
        retcode = pacstrap.wait()
        if retcode:
            raise CalledProcessError(retcode, cmd)

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

    def _cancel(self):
        if self._pacstrap:
            self._pacstrap.terminate()

    def _process(self):
        self.set_completion(1)
        self._root = mkdtemp()
        self.logger.debug(_("creating temp dir at %s") % self._root)

        try:
            self._do_mount_partitions()
            self._do_pacstrap()
            self._do_fstab()
            self._done()
        finally:
            self._do_umount_partitions()
            os.rmdir(self._root)
            self._root = None

        # complete installation
        #    1/ root password
        #    2/ setup locale
        #    3/ setup timezone
        #    4/ regenerer initramfs (archlinux)
        #    5/ bootloader :(
