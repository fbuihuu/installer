# -*- coding: utf-8 -*-
#

from __future__ import print_function
import os
import re
import glob
from subprocess import check_output, check_call
from steps import Step
from partition import mount_rootfs, unmount_rootfs, mounted_partitions
from system import distribution, is_efi
from settings import settings
from process import monitor, monitor_chroot


class FStabEntry(object):

    def __init__(self, part):
        self.partition = part
        self.target = part.name
        self.fstype = part.device.filesystem
        self.dump   = 0
        self.passno = 1 if self.target == "/" else 2

        devpath = part.device.devpath
        options = check_output(["findmnt", "-cvuno", "OPTIONS", devpath])
        self.options = options.split()[0].decode()

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
        self.__extra_packages = None

    @property
    def name(self):
        return _("Installation")

    @property
    def _kernel_cmdline(self):
        cmdline = settings.Kernel.cmdline
        if "root=" in cmdline:
            return cmdline
        return "root=" + self._fstab["/"].source + " " + cmdline

    @property
    def _extra_packages(self):
        if self.__extra_packages is None:
            self.__extra_packages = []
            if settings.Packages.list:
                self.logger.info("importing extra packages file")
                try:
                    with open(settings.Packages.list, 'r') as f:
                        for line in f:
                            line = line.partition('#')[0]
                            line = line.strip()
                            if line:
                                self.__extra_packages.append(line)
                except IOError:
                    self.logger.error("Failed to read extra packages file %s" %
                                      settings.Package.list)
        return self.__extra_packages

    def _do_rootfs(self):
        raise NotImplementedError()

    def _do_fstab(self):
        self.logger.info("generating fstab")
        for part in mounted_partitions:
            self._fstab[part.name] = FStabEntry(part)

        with open(os.path.join(self._root, 'etc/fstab'), 'w') as f:
            for entry in self._fstab.values():
                print(entry.format(), file=f)

    def _do_bootloader(self):
        #
        # Several cases to handle:
        #
        #   1/ UEFI (GTP)   =>  gummiboot + EFI System Partiton
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
        if 'uefi' in settings.Options.firmware:
            self._do_bootloader_on_efi()

        if 'bios' in settings.Options.firmware:
            if '/boot' in self._fstab:
                bootable = self._fstab['/boot'].partition.device
            else:
                bootable = self._fstab['/'].partition.device
            #
            # Find out which partition scheme is used by this
            # device. The device can be a RAID disk based on disk
            # partitions. In that case the RAID device does not have
            # a partition scheme but its parents have.
            #
            for dev in bootable.iterparents():
                scheme = dev.scheme
                if scheme:
                    break

            if scheme == 'dos':
                self._do_bootloader_on_mbr(bootable)
                return
            if scheme == 'gpt':
                self._do_bootloader_on_gpt(bootable)
                return

            self._failed("bootable device has unsupported partition scheme '%s'",
                         scheme)

    def _do_initramfs(self):
        raise NotImplementedError()

    def _do_bootloader_on_efi(self):
        raise NotImplementedError()

    def _do_bootloader_on_mbr(self, bootable):
        raise NotImplementedError()

    def _do_bootloader_on_gpt(self, bootable):
        raise NotImplementedError()

    def _do_extra_packages(self):
        raise NotImplementedError()

    def _do_i18n(self):
        # Don't rely on localectl(1), it may be missing on old
        # systems.

        locale = settings.I18n.locale
        keymap = settings.I18n.keymap
        tzone  = settings.I18n.timezone

        self.logger.debug("using locale '%s'", locale)
        with open(self._root + '/etc/locale.conf', 'w') as f:
            f.write("LANG=%s\n" % locale)

        self.logger.debug("using keymap '%s'", keymap)
        with open(self._root + '/etc/vconsole.conf', 'w') as f:
            f.write("KEYMAP=%s\n" % keymap)

        # Old versions of systemd-nspawn bind mount localtime
        self.logger.debug("selecting timezone '%s'", tzone)
        self._chroot('ln -sf /usr/share/zoneinfo/%s /etc/localtime' % tzone,
                     with_nspawn=False)

    def _monitor(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor(args, **kwargs)

    def _chroot(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor_chroot(self._root, args, **kwargs)

    def _cancel(self):
        raise NotImplementedError()

    def _process(self):
        self.set_completion(1)
        self._root = mount_rootfs()

        try:
            self._do_rootfs()
            self._do_i18n()
            self._do_fstab()
            self._do_bootloader()
            self._do_extra_packages()
            self._do_initramfs()
            self._done()
        except Exception as e:
            try:
                # At that point umounting rootfs will probably fail, but
                # let's try to do the cleanup anyways.
                unmount_rootfs()
            except:
                self.logger.error("failed to umount %s", self._root)
            raise e
        else:
            unmount_rootfs()
            self._root = None

    #
    # Some generic helpers
    #
    def _do_bootloader_on_bios_with_syslinux(self, bootable, gpt=True):
        self.logger.info("installing syslinux on a GPT disk layout")

        # This should work even on RAID1 device, since in that case
        # the vbr will be mirrored too.
        self._chroot('cp /usr/lib/syslinux/bios/*.c32 /boot/syslinux/')
        self._chroot('extlinux --install /boot/syslinux')

        bootcode = "gptmbr.bin" if gpt else "mbr.bin"
        bootcode = os.path.join("/usr/lib/syslinux/bios", bootcode)

        for parent in bootable.get_root_parents():
            # install mbr
            cmd = "dd bs=440 conv=notrunc count=1 if={0} of={1} 2>/dev/null"
            self._chroot(cmd.format(bootcode, parent.devpath))

            if gpt:
                # make sure the attribute legacy BIOS bootable (bit 2) is
                # set for the /boot partition for GPT.
                self._chroot("sgdisk %s --attributes=%d:set:2" %
                             (parent.devpath, bootable.partnum))
            else:
                # on MBR, we need to mark the boot partition active.
                self._chroot("sfdisk --activate=%d %s" %
                             (bootable.partnum, parent.devpath))

        # Setup kernel command line in syslinux.cfg or where appropriate.
        ls = glob.glob(self._root + '/boot/syslinux/entries/*')
        config = ls[0] if ls else self._root + '/boot/syslinux/syslinux.cfg'
        re = 's/([[:space:]]*APPEND[[:space:]]+).*/\\1%s/I' % self._kernel_cmdline
        check_call(["sed", "-ri", re, config])

    def _do_bootloader_on_bios_with_grub(self, grub="grub"):
        cmd = "{0}-mkconfig -o /boot/{0}/grub.cfg".format(grub)
        self._chroot(cmd)

        # Install grub on the bootable disk(s)
        for parent in bootable.get_root_parents():
            cmd = "{0}-install --target=i386-pc {1}".format(grub, parent.devpath)
            self._chroot(cmd)

    def _do_bootloader_on_efi_with_gummiboot(self):
        self.logger.info("installing gummiboot as bootloader on EFI system")

        # ESP = /boot
        #
        # The following copies the gummiboot binary to your EFI System
        # Partition and create a boot entry in the EFI Boot Manager
        # without '--no-variables'.
        #
        # The only case we want to update the EFI Boot Manager entries
        # is when we're doing an installation for *this* UEFI host.
        #
        if is_efi() and settings.Options.hostonly:
            self._chroot("gummiboot --path=/boot install",
                         bind_mounts=['/sys/firmware/efi/efivars'])
        else:
            self._chroot("gummiboot --path=/boot --no-variables install")

        # setup the kernel command line
        config = glob.glob(self._root + '/boot/loader/entries/*.conf')[0]
        config = config[len(self._root):]
        self._chroot("sed -i /^options/d %s" % config)
        self._chroot("echo 'options     %s' >>%s" % (self._kernel_cmdline, config))


class ArchInstallStep(_InstallStep):

    def __init__(self, ui):
        _InstallStep.__init__(self, ui)
        self._pacstrap = None

    def _cancel(self):
        if self._pacstrap:
            self._pacstrap.terminate()
            self._pacstrap = None

    def _do_pacstrap(self, pkgs, **kwargs):
        self._monitor(['pacstrap', self._root] + pkgs, **kwargs)
        self._pacstrap = None

    def _do_rootfs(self):
        self.logger.info("Initializing rootfs with pacstrap...")

        def stdout_handler(p, line, data):
            self._pacstrap = p
            if data is None:
                data = (0, 0, re.compile(r'Packages \(([0-9]+)\)'))
            count, total, pattern = data

            match = pattern.search(line)
            if not match:
                pass
            elif total == 0:
                total = int(match.group(1)) * 2
                pattern = re.compile(r'downloading |(re)?installing ')
                self.set_completion(2)
            else:
                if not line.startswith('downloading '):
                    count = max(count, total/2)
                count += 1
                self.set_completion(2 + count * 97 / total)

            return (count, total, pattern)

        pkgs = ["base", "mdadm"]
        self._do_pacstrap(pkgs, stdout_handler=stdout_handler)

    def _do_i18n(self):
        # Uncomment all related locales
        locale = settings.I18n.locale
        self._chroot("sed -i 's/^#\(%s.*\)/\\1/' /etc/locale.gen" % locale)
        self._chroot("locale-gen")
        _InstallStep._do_i18n(self)

    def _do_bootloader_on_efi(self):
        self._do_pacstrap(['gummiboot'])
        self._chroot('mkdir -p /boot/loader/entries')

        initrd = "initramfs-linux"
        if not settings.Options.hostonly:
            initrd += "-fallback"
        initrd += ".img"

        loader_conf_file = '/boot/loader/loader.conf'
        loader_conf = """timeout     3
default     archlinux
"""
        arch_conf_file = '/boot/loader/entries/archlinux.conf'
        arch_conf = """title       Arch Linux
linux       /vmlinuz-linux
initrd      /{initrd}
"""

        with open(self._root + loader_conf_file, 'w') as f:
            f.write(loader_conf)

        with open(self._root + arch_conf_file, 'w') as f:
            f.write(arch_conf.format(initrd=initrd))

        self._do_bootloader_on_efi_with_gummiboot()

    def _do_bootloader_on_mbr(self, bootable):
        self._do_pacstrap(['syslinux', 'util-linux'])
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=False)

    def _do_bootloader_on_gpt(self, bootable):
        self._do_pacstrap(['syslinux', 'gptfdisk'])
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=True)

    def _do_extra_packages(self):
        if self._extra_packages:
            self._pacstrap(self._extra_packages)

    def _do_initramfs(self):
        self._chroot("mkinitcpio -p linux")


class MandrivaInstallStep(_InstallStep):

    def __init__(self, ui):
        _InstallStep.__init__(self, ui)
        self._urpmi = None
        self._uname_r = None
        self._urpmi_installed = False

    def _cancel(self):
        if self._urpmi:
            self._urpmi.terminate()
            self._urpmi = None

    def _do_urpmi(self, args, completion):
        urpmi_opts = settings.Urpmi.options.split() + \
                     ["--auto", "--downloader=curl", "--curl-options='-s'"]

        completion_origin = self._completion
        pattern = re.compile(r'\s+([0-9]+)/([0-9]+): ')
        def stdout_handler(p, line, data):
            self._urpmi = p
            match = pattern.match(line)
            if match:
                count, total = map(int, match.group(1, 2))
                delta = completion - completion_origin
                self.set_completion(completion_origin + delta * count / total)

        if self._urpmi_installed:
            cmd = " ".join(["urpmi"] + urpmi_opts + args)
            self._chroot(cmd, stdout_handler=stdout_handler)
        else:
            cmd = ['urpmi', '--root', self._root] + urpmi_opts + args
            self._monitor(cmd, stdout_handler=stdout_handler)
        self._urpmi = None
        self.set_completion(completion)

        # Switch to urpmi from rootfs, so all packages installed later
        # will use a proper environment inside the chroot.
        if 'urpmi' in args:
            if not os.path.exists(os.path.join(self._root, 'etc/urpmi/urpmi.cfg')):
                self._monitor(["cp", "/etc/urpmi/urpmi.cfg",
                               os.path.join(self._root, 'etc/urpmi')])
                self._chroot("urpmi.update -a -q")
                self._urpmi_installed = True

        # If the kernel has been installed, it's time to setup
        # self._uname_r.
        if not self._uname_r:
            ls = glob.glob(os.path.join(self._root, 'boot', 'vmlinuz-*'))
            if ls:
                vmlinuz = os.path.basename(ls[0])[8:]
                if vmlinuz.endswith('.img'):
                    vmlinuz = vmlinuz[:-4]
                self._uname_r = vmlinuz

    def _do_rootfs(self):
        self.logger.info("Initializing rootfs with urpmi...")

        # Note that the kernel needs to be installed after the
        # bootloader so all bootloader configuration files will be
        # updated accordingly.
        packages = ["basesystem-minimal", "urpmi", "mdadm"]
        self._do_urpmi(packages, 60)

    def _do_i18n(self):
        locale = settings.I18n.locale
        self._do_urpmi(['locales-%s' % locale.split('_')[0]], 65)
        _InstallStep._do_i18n(self)

    def _do_bootloader_on_efi(self):
        self._do_urpmi(['gummiboot'], 70)
        self._do_urpmi(['kernel'], 80)
        self._do_bootloader_on_efi_with_gummiboot()

    def _do_bootloader_on_gpt(self, bootable):
        self._do_urpmi(['syslinux', 'extlinux', 'gdisk'], 70)
        self._do_urpmi(['kernel'], 80)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=True)

    def _do_bootloader_on_mbr(self, bootable):
        self._do_urpmi(['syslinux', 'extlinux', 'util-linux'], 70)
        self._do_urpmi(['kernel'], 80)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=False)

    def _do_extra_packages(self):
        if self._extra_packages:
            self._do_urpmi(self._extra_packages, 90)
        else:
            self.set_completion(90)

    def _do_initramfs(self):
        #
        # Even if the initramfs has been built during kernel
        # installation, we regenerate it now so it includes all tools
        # needed to mount the rootfs since the rootfs is completely
        # initialized.
        #
        opt = '--hostonly' if settings.Options.hostonly else '--no-hostonly'
        cmd = "dracut {0} --force /boot/initrd-{1}.img {1}"
        self._chroot(cmd.format(opt, self._uname_r))
        self.set_completion(98)


def InstallStep(ui):
    if distribution.distributor == 'Mandriva':
        return MandrivaInstallStep(ui)

    elif distribution.distributor == 'Arch':
        return ArchInstallStep(ui)

    raise NotImplementedError()

