# -*- coding: utf-8 -*-
#

import os
from operator import itemgetter
from tempfile import mkdtemp

import system
import device
import utils


class PartitionError(Exception):
    """Base class for exceptions in the partition module"""


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
    def is_optional(self):
        return self._is_optional

    @is_optional.setter
    def is_optional(self, optional):
        self._is_optional = optional

    @property
    def minsize(self):
        return self._minsize

    @property
    def _invalid_fs(self):
        return ("swap", "linux_raid_member")

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
# on BIOS + GPT: (a partition with type BIOS Boot Partition (BBP) must be used to store bootloader)
# -------------
#    same restriction as "BIOS + MBR"
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
#    1/ We don't have to stick with only one
#    (crapish/over-bloated) bootloader (call it GRUB).
#
#    2/ root partition can use any fancy things that the
#    kernel/initramfs combo can support (bcache is an example).
#
#    3/ probably easier for secure boot integration
#
# For the simplest case (1 disk containig a '/' partition with a
# standard FS), we make '/boot' partition optinal. All others cases
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

        # for any other fancy FS, we request a separate /boot.
        boot = find_partition("/boot")
        boot.is_optional = fs in ('ext2', 'ext3', 'ext4', 'btrfs')

    def _validate_dev(self, dev):
        Partition._validate_dev(self, dev)
        # For any fancy devices (RAID, etc...), we request a separate
        # /boot.
        boot = find_partition("/boot")
        if dev.devtype != 'partition' or (dev.get_parents() and dev.get_parents()[0].get_parents()):
            boot.is_optional = False
        else:
            boot.is_optional = True


class BootPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/boot")
        if system.is_efi():
            self._is_optional = False
            self._minsize = 1024 * 1024 * 1024
        else:
            self._minsize = 50 * 1000 * 1000

    def _validate_fs(self, fs):
        if system.is_efi() and fs != "vfat":
            raise PartitionError("/boot must use vfat FS on UEFI systems")
        Partition._validate_fs(self, fs)

    def _validate_dev(self, dev):
        # Since we make sure that the device used for /boot is a
        # partition, the parent disk has a valid partition table.
        if dev.devtype != 'partition' or (dev.get_parents() and dev.get_parents()[0].get_parents()):
            raise device.DeviceError(dev, "must be a (raw) disk partition")

        if system.is_efi():
            if dev.scheme != 'gpt':
                raise device.DeviceError(dev, "GPT is needed on UEFI systems")

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

def get_candidates(part):
    candidates = []
    in_use_devices = [p.device for p in partitions if p != part and p.device]
    for dev in device.block_devices:
        if dev in in_use_devices:
            continue
        #
        # Work on partitions first.
        #
        if dev.devtype == 'disk' and dev.scheme:
            continue
        #if not part.is_valid_dev(dev):
        #    continue
        #if not part.is_valid_fs(dev.filesystem):
        #    continue
        ## skip any devices with mounted filesystem.
        #if dev.mountpoints:
        #    continue
        candidates.append(dev)
    return candidates

def __uevent_callback(action, bdev):
    if action == "remove":
        for part in partitions:
            if part.device == bdev:
                part.device = None
    #
    # On 'change' event, a device that was previously assigned to a
    # partition may become invalid. If the fs changes for example.
    #
    if action == "change":
        for part in partitions:
            if part.device == bdev:
                part.device = None
                if bdev in get_candidates(part):
                    part.device = bdev

device.listen_uevent(__uevent_callback)
