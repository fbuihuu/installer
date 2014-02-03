# -*- coding: utf-8 -*-
#

import os
import re
from operator import itemgetter
from subprocess import *
from tempfile import mkdtemp
from steps import Step
from partition import mount_rootfs, unmount_rootfs, mounted_partitions
from system import distribution


class FStabEntry(object):

    def __init__(self, part):
        self.target = part.name
        self.fstype = part.device.filesystem
        self.dump   = 0
        self.passno = 1 if self.target == "/" else 2

        devpath = part.device.devpath
        options = check_output("findmnt -cvuno OPTIONS " + devpath , shell=True)
        self.options = options.split()[0]

        if part.device.partuuid:
            self.source = "PARTUUID=" + part.device.partuuid
        elif part.device.partlabel:
            self.source = "PARTLABEL=" + part.device.partlabel
        elif part.device.uuid:
            self.source = "UUID=" + part.device.fsuuid
        elif part.device.label:
            self.source = "LABEL=" + part.device.fslabel
        else:
            self.source = part.device.devpath

    def format(self):
        return "%-20s\t%-10s %-10s %-10s\t%d %d" % (self.source, self.target,
                                                    self.fstype, self.options,
                                                    self.dump, self.passno)


class _InstallStep(Step):

    requires = ["license"]
    provides = ["rootfs"]

    def __init__(self, ui):
        Step.__init__(self, ui)
        self._root = None
        self._fstab = {}

    @property
    def name(self):
        return _("Installation")

    def _do_rootfs(self):
        raise NotImplementedError()

    def _do_fstab(self):
        self.logger.info("generating fstab")
        for part in mounted_partitions:
            self._fstab[part.name] = FStabEntry(part)

        with open(os.path.join(self._root, 'etc/fstab'), 'w') as f:
            for entry in self._fstab.values():
                print >>f, entry.format(), '\n'

    def _cancel(self):
        raise NotImplementedError()

    def _process(self):
        self.set_completion(1)
        self._root = mount_rootfs()

        try:
            self._do_rootfs()
            self._do_fstab()
            self._done()
        finally:
            unmount_rootfs()
            self._root = None


class ArchInstallStep(_InstallStep):

    def __init__(self, ui):
        _InstallStep.__init__(self, ui)
        self._pacstrap = None

    def _cancel(self):
        if self._pacstrap:
            self._pacstrap.terminate()

    def _do_rootfs(self):
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


def InstallStep(ui):
    if distribution.distributor == "Mandriva":
        return MandrivaInstallStep(ui)

    elif distribution.distributor == "Arch":
        return ArchInstallStep(ui)

    raise NotImplementedError()

