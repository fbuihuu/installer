# -*- coding: utf-8 -*-
#

import os
import re
from operator import itemgetter
from subprocess import *
from tempfile import mkdtemp
from steps import Step
from partition import mount_rootfs, unmount_rootfs, mounted_partitions
from system import distribution, is_efi
import systemd


try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


class FStabEntry(object):

    def __init__(self, part):
        self.partition = part
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
        elif part.device.fsuuid:
            self.source = "UUID=" + part.device.fsuuid
        elif part.device.fslabel:
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

    def _do_bootloader(self):
        #
        # Several cases to handle:
        #
        #   1/ EFI (GTP)   =>  gummiboot + EFI System Partiton
        #   2/ BIOS + GPT  =>  syslinux  + BIOS Boot Partition
        #   3/ BIOS + MBR  =>  syslinux  + /boot partition      [3]
        #
        # We prefer to use GPT over MBR for several reasons:
        #
        #   - support of disks larger than 2TB
        #   - use of PARTUUID which is stable across partition reformat
        #
        # syslinux cannot access files from partitions other than its
        # own (unlike GRUB). This feature (called multi-fs) is
        # therefore unavailable.
        #
        # [3] syslinux supports the FAT, ext2, ext3, ext4, and Btrfs file
        # systems.
        #
        if is_efi():
            self._do_bootloader_on_efi()
        else:
            rootdev = self._fstab['/'].partition.device
            if rootdev.scheme == 'dos':
                self._do_bootloader_on_mbr()
            elif rootdev.scheme == 'gpt':
                raise NotImplementedError()
            else:
                raise NotImplementedError()

    def _xchroot(self, *args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        systemd.xchroot(self._root, *args, **kwargs)

    def _cancel(self):
        raise NotImplementedError()

    def _process(self):
        self.set_completion(1)
        self._root = mount_rootfs()

        try:
            self._do_rootfs()
            self._do_fstab()
            self._do_bootloader()
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
            self._pacstrap = None

    def _do_rootfs(self):
        self.logger.info("Initializing rootfs with pacstrap...")

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
            self.logger.debug(line.rstrip())

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
            self.logger.debug(line.rstrip())

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

    def _do_bootloader_on_efi(self):
        self.logger.info("installing gummiboot as bootloader on EFI system")

        cmd = "pacstrap %s efibootmgr gummiboot" % self._root
        check_call(cmd, shell=True, stdout=DEVNULL, stderr=STDOUT)

        # ESP = /boot
        #
        # The following copies the gummiboot binary to your EFI System
        # Partition and create a boot entry in the EFI Boot Manager.
        #
        self._xchroot("gummiboot --path=/boot install",
                      bind_mounts=['/dev', '/sys/firmware/efi/efivars'])

        GUMMY_ARCH_ENTRY_CONF = """
title       Arch Linux
linux       /vmlinuz-linux
initrd      /initramfs-linux.img
options     root=%s rw
"""

        LOADER_CONF = """
timeout     3
default     archlinux
"""
        with open(self._root + '/boot/loader/entries/archlinux.conf', 'w') as f:
            f.write(GUMMY_ARCH_ENTRY_CONF % self._fstab["/"].source)

        with open(self._root + '/boot/loader/loader.conf', 'w') as f:
            f.write(LOADER_CONF)

    def _do_bootloader_on_mbr(self):
        raise NotImplementedError()


class MandrivaInstallStep(_InstallStep):

    def __init__(self, ui):
        _InstallStep.__init__(self, ui)
        self._urpmi = None
        self._urpmi_default_opts  = "--no-verify --auto --no-suggests --excludedocs "
        self._urpmi_default_opts += "--downloader=curl --curl-options='-s' "

    def _cancel(self):
        if self._urpmi:
            self._urpmi.terminate()
            self._upmi = None

    def _urpmi_popen(self, cmd):
        opts = self._urpmi_default_opts + cmd
        return Popen('urpmi ' + opts, shell=True, stdout=PIPE, stderr=STDOUT)

    def _urpmi_call(self, cmd):
        opts = self._urpmi_default_opts + ' ' + cmd
        check_call('urpmi ' + opts, shell=True)

    def _do_rootfs(self):
        self.logger.info("Initializing rootfs with urpmi...")

        packages = "basesystem urpmi dracut kernel-server"
        self._urpmi = self._urpmi_popen("--root %s %s" % (self._root, packages))
        urpmi = self._urpmi

        pattern = re.compile(r'\s+([0-9]+)/([0-9]+): ')
        while urpmi.poll() is None:
            line = urpmi.stdout.readline()
            line = line.rstrip()
            if not line:
                continue
            self.logger.debug(line)

            match = pattern.match(line)
            if not match:
                continue
            count, total = map(int, match.group(1, 2))
            self.set_completion(2 + count * 97 / total)

        retcode = urpmi.wait()
        self._urpmi = None
        if retcode:
            raise CalledProcessError(retcode, cmd)

    def _do_bootloader_on_efi(self):
        raise NotImplementedError()

    def _do_bootloader_on_mbr(self):
        self._xchroot("grub2-mkconfig -o /boot/grub2/grub.cfg",
                      bind_mounts=['/dev'])

        # Install grub on the disk(s) containing /
        rootdev = self._fstab['/'].partition.device
        for parent in rootdev.get_root_parents():
            self.logger.info("grub2-install %s" % parent.devpath)
            self._xchroot("grub2-install %s" % parent.devpath,
                          bind_mounts=['/dev'])


def InstallStep(ui):
    if distribution.distributor == "Mandriva":
        return MandrivaInstallStep(ui)

    elif distribution.distributor == "Arch":
        return ArchInstallStep(ui)

    raise NotImplementedError()

