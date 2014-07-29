# -*- coding: utf-8 -*-
#

from __future__ import print_function
import os
import glob
from subprocess import check_output, check_call

from installer import disk
from installer import l10n
from installer import distro
from installer.partition import partitions
from installer.system import distribution, is_efi
from installer.settings import settings, SettingsError
from . import Step, StepError


class FStabEntry(object):

    def __init__(self, part):
        self.partition = part
        self.target = part.name
        self.fstype = part.device.filesystem
        self.dump   = 0
        self.passno = 1 if self.target == "/" else 2

        if self.fstype not in ('swap'):
            # part is currently mounted, reuse the current options.
            self.options = ','.join(part.mount_options)
        else:
            self.options = "defaults"
            self.passno  = 0
        #
        # Make sure the corresponding devlink exists in /dev/disk/
        # before using ID=xxx notation. Indeed for certain type of
        # devices such as MD, 'by-partuuid' devlinks are not created
        # even if the MD device has PARTUUID prop defined. See
        # /lib/udev/rules.d/60-persistent-storage.rules
        #
        for ident in ("partuuid", "partlabel", "uuid", "label", "id"):
            devlinks = part.device.devlinks(ident)
            if devlinks:
                devlink = devlinks[0]
                break
        else:
            # This shouldn't happen.
            raise StepError("no devlink found for %s !" % part.device.devpath)

        if ident == "partuuid":
            self.source = "PARTUUID=" + part.device.partuuid
        elif ident == "partlabel":
            self.source = "PARTLABEL=" + part.device.partlabel
        elif ident == "uuid":
            self.source = "UUID=" + part.device.fsuuid
        elif ident == "label":
            self.source = "LABEL=" + part.device.fslabel
        else:
            if not settings.Options.hostonly:
                # We're probabling generating a generic image that
                # should be transparently used on any devices.
                raise StepError(_("Failed to generate fstab for a portable image."))
            #
            # For some reasons ID=xxx notation isn't supported by
            # systemd, libmount, blkid...
            #
            self.source = devlink

    def format(self):
        return "%-20s\t%-10s %-10s %-10s\t%d %d" % (self.source, self.target,
                                                    self.fstype, self.options,
                                                    self.dump, self.passno)


class _InstallStep(Step):

    requires = ["license"]
    provides = ["rootfs"]
    mandatory = True

    def __init__(self):
        Step.__init__(self)
        self._fstab = {}
        self._extra_packages = ['mdadm'] # FIXME: should test if it's a RAID setup

    @property
    def name(self):
        return _("Installation")

    @property
    def _kernel_cmdline(self):
        cmdline = settings.Kernel.cmdline
        if "root=" in cmdline:
            return cmdline
        return "root=" + self._fstab["/"].source + " " + cmdline

    def _do_read_package_list(self):
        lst = []
        for pkgfile in settings.Packages.extras:
            self.logger.info("reading package list")
            try:
                with open(pkgfile, 'r') as f:
                    for line in f:
                        line = line.partition('#')[0]
                        line = line.strip()
                        if line:
                            lst.append(line)
            except IOError:
                self.logger.error("Failed to read package list %s" %
                                  settings.Package.list)
        return lst

    def _do_rootfs(self):
        raise NotImplementedError()

    def _do_i18n(self):
        l10n.init_timezones(distro.paths['timezones'], self._root)
        l10n.init_keymaps(distro.paths['keymaps'], self._root)

    def _do_fstab(self):
        self.logger.info("generating fstab")
        for part in partitions:
            if part.device:
                self._fstab[part.name] = FStabEntry(part)

        with open(os.path.join(self._root, 'etc/fstab'), 'w') as f:
            for entry in self._fstab.values():
                print(entry.format(), file=f)

        # hallelujah: distros seem to agree on package names
        # containing fsck tools.
        pkgs = set()
        for entry in [ e for e in self._fstab.values() if e.passno > 0]:
            if entry.fstype in ('fat', 'vfat', 'msdos'):
                pkgs.add('dosfstools')
            elif entry.fstype.startswith('ext'):
                pkgs.add('e2fsprogs')
            elif entry.fstype in ('xfs'):
                pkgs.add('xfsprogs')
            elif entry.fstype in ('jfs'):
                pkgs.add('jfsutils')
            elif entry.fstype in ('btrfs'):
                pkgs.add('btrfs-progs')
            else:
                raise StepError(_("don't know how to check fs coherency"))
        self._extra_packages.extend(pkgs)

    def _do_bootloader(self):
        #
        # We support the following cases:
        #
        #   1/ UEFI (GTP)  =>  gummiboot + EFI System Partiton
        #   2/ BIOS + GPT  =>  syslinux  + BIOS Boot Partition
        #   3/ BIOS + MBR  =>  syslinux  + /boot partition      [3]
        #
        # We prefer to use GPT over MBR for several reasons:
        #
        #   - support of disks larger than 2TB
        #   - use of PARTUUID which is stable across partition reformat
        #   - MBR is basically outdated
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
            # a partition scheme but its root parents have.
            #
            scheme = disk.get_candidates(bootable)[0].scheme

            if scheme == 'dos':
                self._do_bootloader_on_mbr(bootable)
            elif scheme == 'gpt':
                self._do_bootloader_on_gpt(bootable)
            else:
                raise StepError("bootable device has unsupported "
                                "partition scheme '%s'" % scheme)

        self._do_bootloader_finish()

        # Fix the kernel command line in syslinux config file.
        append = "    APPEND      %s" % self._kernel_cmdline
        for cfg in glob.glob(self._root + distro.paths['syslinux.cfg']):
            self._monitor(["sed", "-i", "/[[:space:]]*APPEND[[:space:]]+/d", cfg])
            self._monitor(["sed", "-i", "$a%s" % append, cfg])

        # Fix the kernel command line in gummiboot config file.
        options = "options     %s" % self._kernel_cmdline
        for cfg in glob.glob(self._root + '/boot/loader/entries/*.conf'):
            self._monitor(["sed", "-i", "/^options/d", cfg])
            self._monitor(["sed", "-i", "$a%s" % options, cfg])

    def _do_initramfs(self):
        raise NotImplementedError()

    def _do_bootloader_on_efi(self):
        raise NotImplementedError()

    def _do_bootloader_on_mbr(self, bootable):
        raise NotImplementedError()

    def _do_bootloader_on_gpt(self, bootable):
        raise NotImplementedError()

    def _do_bootloader_finish(self):
        raise NotImplementedError()

    def _do_extra_packages(self):
        raise NotImplementedError()

    def _cancel(self):
        raise NotImplementedError()

    def _process(self):
        self.set_completion(1)

        pkgs = self._do_read_package_list()
        self._do_rootfs(pkgs)
        self._do_i18n()
        self._do_fstab()
        self._do_bootloader()
        self._do_extra_packages()
        self._do_initramfs()
        self._done()

    #
    # Some generic helpers
    #
    def _do_bootloader_on_bios_with_syslinux(self, bootable, gpt=True):
        self.logger.info("installing syslinux on a GPT disk layout")

        #
        # This should work even on RAID1 device, since in that case
        # the vbr will be mirrored too.
        #
        self._chroot(['sh', '-c', 'cp /usr/lib/syslinux/bios/*.c32 /boot/syslinux/'])
        self._chroot(['extlinux', '--install', '/boot/syslinux'])

        bootcode = "gptmbr.bin" if gpt else "mbr.bin"
        bootcode = os.path.join("/usr/lib/syslinux/bios", bootcode)

        if bootable.devtype != 'partition':
            # /boot is a RAID array: its parents are partitions, it
            # was checked previously.
            partnums = [p.partnum for p in bootable.get_parents()]
        else:
            partnums = [bootable.partnum]

        for i, parent in enumerate(disk.get_candidates(bootable)):
            # install mbr
            self.logger.debug("installing bootcode in %s MBR", parent.devpath)
            cmd  = "dd bs=440 conv=notrunc count=1 if={0} of={1} 2>/dev/null"
            self._chroot(['sh', '-c', cmd.format(bootcode, parent.devpath)])

            if gpt:
                #
                # make sure the attribute legacy BIOS bootable (bit 2)
                # is set for the /boot partition for GPT. It's
                # required by syslinux on BIOS system.
                #
                self._chroot(['sgdisk', parent.devpath,
                              '--attributes=%d:set:2' % partnums[i]])
            else:
                # on MBR, we need to mark the boot partition active.
                self._chroot(['sfdisk' '--activate=%d' % partnums[i],
                              parent.devpath])

    def _do_bootloader_on_bios_with_grub(self, bootable, grub="grub"):
        self._chroot([grub + '-mkconfig', '-o', '/boot/' + grub + '/grub.cfg'])

        # Install grub on the bootable disk(s)
        for parent in bootable.get_root_parents():
            self._chroot([grub + '-install', '--target=i386-pc', parent.devpath])

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
            self._chroot(['gummiboot', '--path=/boot', 'install'],
                         bind_mounts=['/sys/firmware/efi/efivars'])
        else:
            self._chroot(['gummiboot', '--path=/boot', '--no-variables',
                          'install'])


class ArchInstallStep(_InstallStep):

    def __init__(self):
        _InstallStep.__init__(self)
        self._pacstrap = self._chroot_install

    def _do_rootfs(self, pkgs):
        self.logger.info("Initializing rootfs with pacstrap...")
        self._pacstrap(["base"] + pkgs, 60)

    def _do_bootloader_on_efi(self):
        self._pacstrap(['gummiboot'], 80)
        self._chroot(['mkdir', '-p', '/boot/loader/entries'])

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
        self._pacstrap(['syslinux', 'util-linux'], 80)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=False)

    def _do_bootloader_on_gpt(self, bootable):
        self._pacstrap(['syslinux', 'gptfdisk'], 80)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=True)

    def _do_bootloader_finish(self):
        pass

    def _do_extra_packages(self):
        self._pacstrap(self._extra_packages, 90)

    def _do_initramfs(self):
        hooks = ["base", "udev"]

        if settings.Options.hostonly:
            # This hook is used to get rid of kernel modules uneeded to
            # boot the current system.
            hooks += ["autodetect"]

        hooks += ["modconf", "block"]

        root = self._fstab['/'].partition.device
        if root.is_compound():
            # see https://wiki.archlinux.org/index.php/mkinitcpio#Using_RAID
            hooks += ["mdadm_udev"]

        hooks += ["filesystems", "keyboard", "fsck"]

        # modify /etc/mkinitcpio.conf
        re = "s/^HOOKS=.*/HOOKS='{0}'/".format(" ".join(hooks))
        self._monitor(["sed", "-i", re, self._root+'/etc/mkinitcpio.conf'])
        self._chroot(['mkinitcpio', '-p', 'linux'])
        self.set_completion(99)


class MandrivaInstallStep(_InstallStep):

    def __init__(self):
        _InstallStep.__init__(self)
        self._urpmi = self._chroot_install # alias

    def _do_rootfs(self, pkgs):
        self.logger.info("Initializing rootfs with urpmi...")
        self._urpmi(['basesystem-minimal'] + pkgs, 60)

    def _do_bootloader_on_efi(self):
        self._urpmi(['gummiboot'], 70)
        self._do_bootloader_on_efi_with_gummiboot()

    def _do_bootloader_on_gpt(self, bootable):
        self._urpmi(['syslinux', 'extlinux', 'gdisk'], 70)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=True)

    def _do_bootloader_on_mbr(self, bootable):
        self._urpmi(['syslinux', 'extlinux', 'util-linux'], 70)
        self._do_bootloader_on_bios_with_syslinux(bootable, gpt=False)

    def _do_bootloader_finish(self):
        #
        # The kernel needs to be installed after the bootloader so all
        # bootloader configuration files will be updated accordingly.
        #
        # Note: we can't use extra_package, here because we have to
        # generate all config files right now so _do_bootloader can
        # customize them.
        #
        self._urpmi(['kernel'], 80)

    def _do_extra_packages(self):
        self._urpmi(self._extra_packages, 90)

    def _do_initramfs(self):
        #
        # Retrieve the kernel version we previously installed.
        #
        ls = glob.glob(os.path.join(self._root, 'boot', 'vmlinuz-*'))
        vmlinuz = os.path.basename(ls[0])[8:]
        if vmlinuz.endswith('.img'):
            vmlinuz = vmlinuz[:-4]
        uname_r = vmlinuz

        #
        # Even if the initramfs has been built during kernel
        # installation, we regenerate it now so it includes all tools
        # needed to mount the rootfs since the rootfs is completely
        # initialized.
        #
        hostonly  = '--hostonly' if settings.Options.hostonly else '--no-hostonly'
        self._chroot(['dracut', hostonly, '--force',
                      '/boot/initrd-' + uname_r + '.img', uname_r])
        self.set_completion(98)


def InstallStep():
    if distribution.distributor == 'Mandriva':
        return MandrivaInstallStep()

    elif distribution.distributor == 'Arch':
        return ArchInstallStep()

    raise NotImplementedError()
