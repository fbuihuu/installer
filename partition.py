# -*- coding: utf-8 -*-
#

import os
from operator import itemgetter
from tempfile import mkdtemp

import system
import device


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

    @property
    def minsize(self):
        return self._minsize

    def _is_valid_fs(self, fs):
        invalid_fs = ("swap", "linux_raid_member")
        if not fs or fs in invalid_fs:
            return False
        return True

    def is_valid_dev(self, dev):
        return self._is_valid_fs(dev.filesystem)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, dev):
        if dev and not self.is_valid_dev(dev):
            raise Exception()
        self._device = dev


class BootPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/boot")
        self._is_optional = not system.is_efi()
        self._minsize = 1*1024*1024*1024

    def _is_valid_fs(self, fs):
        if system.is_efi():
            return fs == "vfat"
        return Partition._is_valid_fs(self, fs)


partitions = [
    Partition("/", is_optional=False, minsize=200000000),
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
        if not part.is_valid_dev(dev):
            continue
        # skip any devices with mounted filesystem.
        if dev.mountpoints:
            continue
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
