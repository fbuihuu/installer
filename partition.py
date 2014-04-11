# -*- coding: utf-8 -*-
#

import os
import logging
from operator import itemgetter
from tempfile import mkdtemp

from settings import settings
import system
import device
import utils


logger = logging.getLogger(__name__)


class PartitionError(Exception):
    """Base class for exceptions in the partition module"""


class BootPartitionError(PartitionError):

    def __init__(self):
        message = _("only disk partition or RAID1 with 0.9 or 1.0 metadata devices are allowed")
        PartitionError.__init__(self, message)


class Partition(object):

    def __init__(self, name, is_optional=True, minsize=0):
        self._name = name
        self._is_optional = is_optional
        self._minsize = minsize
        self._device = None

    @property
    def name(self):
        return self._name

    @property
    def minsize(self):
        return self._minsize

    @property
    def _invalid_fs(self):
        return ("swap", "linux_raid_member")

    def is_optional(self):
        return self._is_optional

    def _validate_fs(self, fs):
        """Check the passed fs matches this partition requirements"""
        if not fs:
            raise PartitionError("device is not formatted")
        if fs in self._invalid_fs:
            raise PartitionError("%s is an invalid filesystem" % fs)

    def _validate_dev(self, dev):
        """Check the passed device matches partition requirements"""
        if dev.size < self._minsize:
            minsize = utils.pretty_size(self._minsize, KiB=False)
            raise PartitionError("you need at least %s" % minsize)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, dev):
        if dev:
            dev.validate()  # track any device inconsistencies.
            self._validate_dev(dev)
            self._validate_fs(dev.filesystem)
        self._device = dev


# /boot partition can be:
#
# on EFI:
# -------
#    1/ a disk partition using GTP
#    2/ a MD RAID1 device with metadata (1.0 or 0.9) => underlying device must be 1/
#    3/ a fakeraid partition device => underlying device must be 1/
#    4/ a partition inside a fakeraid device => same as 1/
#
# on BIOS + GPT:
# -------------
#    same restriction as "BIOS + MBR" but if grub is used, a partition with type
#    BIOS Boot Partition (BBP) must be used to store bootloader).
#
# on BIOS + MBR:
# -------------
#    1/ a partition inside a disk using MBR
#    2/ if grub any RAID/LVM devices
#    3/ if not grub MD RAID1 device (1.0 or 0.9)
#
# Conclusion:
# ----------
# On EFI, ESP (hence /boot) mut be kept simple: vfat, RAID1
# (0.9, 1) at most.
#
# On BIOS, if / needs to use a complex layout (RAID > 1, LVM,
# advanced FS) we need a separate /boot with a much simpler
# layout so the bootloader can access to the kernel file.
#
# A common denominator is to always have a separate /boot and
# keep it simple (ext[234], or btrfs).
# Pros:
#
#    1/ We don't have to stick with only one (bloated) bootloader
#       (call it GRUB).
#
#    2/ root partition can use any fancy things that the
#       kernel/initramfs combo can support (bcache is an example).
#
#    3/ might be easier for secure boot integration, but it's just
#       a guess.
#
# For the simplest case (1 disk containig a '/' partition with a
# standard FS), we make '/boot' partition optional. All others cases
# will have a separate '/boot'.
#
class RootPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/")
        self._is_optional = False
        self._minsize = 200 * 1000 * 1000

    def _validate_fs(self, fs):
        Partition._validate_fs(self, fs)

        if fs in ('msdos', 'fat', 'vfat', 'ntfs'):
            raise PartitionError("come on, %s for your root partition !" % fs)

    def _validate_dev(self, dev):
        Partition._validate_dev(self, dev)

    @Partition.device.setter
    def device(self, dev):
        Partition.device.fset(self, dev)

        is_optional = True
        if dev:
            # for any other fancy FS, we request a separate /boot.
            if dev.filesystem not in ('ext2', 'ext3', 'ext4', 'btrfs'):
                is_optional = False

            # For any fancy devices (RAID, etc...), we request a separate
            # /boot.
            elif dev.devtype != 'partition' or dev.is_compound():
                is_optional = False

        boot = find_partition("/boot")
        boot._is_optional = is_optional


class BootPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/boot")
        if "uefi" in settings.Options.firmware:
            # EFI specification does not require a min size for ESP
            # but 512MiB and higher tend to avoid some corner cases.
            self._minsize = 512 * 1024 * 1024
        else:
            self._minsize = 50 * 1000 * 1000

    def is_optional(self):
        if "uefi" in settings.Options.firmware:
            return False
        return self._is_optional

    def _validate_fs(self, fs):
        # ESP partition on UEFI systems should use a FAT32 fs.
        if "uefi" in settings.Options.firmware and fs != "vfat":
            raise PartitionError("/boot must use vfat FS on UEFI systems")
        Partition._validate_fs(self, fs)

    def _validate_dev(self, dev):
        if dev.devtype != 'partition':
            #
            # For now the only supported case: dev is a disk is when
            # it's a RAID1 MD device using 0.9 or 1.0 metadata.
            #
            if type(dev) is not device.MetadiskDevice:
                raise BootPartitionError()

            if dev.level != 'raid1':
                raise BootPartitionError()

            if dev.metadata_version not in ('0.90', '1.0'):
                raise BootPartitionError()
        else:
            #
            # Ok looks a simple case, check that dev is a 'raw' disk
            # partition.
            #
            if dev.is_compound():
                raise BootPartitionError()

        if "uefi" in settings.Options.firmware:
            if dev.scheme != 'gpt':
                raise PartitionError("GPT is required on UEFI systems")

        Partition._validate_dev(self, dev)


partitions = [
    RootPartition(),
    Partition("/home"),
    Partition("/var"),
    BootPartition(),
]


_rootfs_mntpnt = None
mounted_partitions = []

def mount_rootfs():
    global _rootfs_mntpnt, mounted_partitions

    if _rootfs_mntpnt:
        return _rootfs_mntpnt
    _rootfs_mntpnt = mkdtemp()

    lst = [ (p.name, p) for p in partitions if p.device ]
    lst.sort(key=itemgetter(0))

    for name, part in lst:
        mntpnt = _rootfs_mntpnt + name
        if name != "/" and not os.path.exists(mntpnt):
            os.mkdir(mntpnt)
        part.device.mount(mntpnt)
        mounted_partitions.append(part)

    return _rootfs_mntpnt

def unmount_rootfs():
    global _rootfs_mntpnt, mounted_partitions

    if _rootfs_mntpnt:
        for part in reversed(mounted_partitions):
            mntpnt = part.device.umount()
            mounted_partitions.remove(part)
        os.rmdir(_rootfs_mntpnt)
        _rootfs_mntpnt = None

def find_partition(name):
    for part in partitions:
        if part.name == name:
            return part

def get_installable_devices(part, all=False):
    candidates = []

    #
    # Build the list of devices currently selected by partitions and
    # exclude them.
    #
    busy_devices = [p.device for p in partitions if p != part and p.device]

    #
    # Consider leaf devices only: it can be either a disk or a
    # partition. We consider both because soft RAID on partitions are
    # seen as a single disk.
    #
    for dev in device.leaf_block_devices():
        # skip already in use devices
        if dev in busy_devices:
            continue

        # Following devices can't be a good candidate.
        if type(dev) is device.CdromDevice:
            continue

        # Those ones might be used (for testing purposes) but shouldn't
        # during a real installation.
        if not all and type(dev) in (device.RamDevice,
                                     device.LoopDevice,
                                     device.FloppyDevice):
            continue

        candidates.append(dev)

    return candidates

def __uevent_callback(action, bdev):
    if action == "remove":
        for part in partitions:
            if part.device == bdev:
                part.device = None
                logger.warn("device %s used by partition %s has disappeared",
                            bdev.devpath, part.name)
    #
    # On 'change' event, a device that was previously assigned to a
    # partition may become invalid. If the fs changes for example.
    #
    if action == "change":
        for part in partitions:
            if part.device == bdev:
                part.device = None
                if bdev in get_installable_devices(part):
                    part.device = bdev
                else:
                    logger.warn("incompatible changes in device %s for %s",
                                bdev.devpath, part.name)

device.listen_uevent(__uevent_callback)
