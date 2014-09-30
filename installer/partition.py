# -*- coding: utf-8 -*-
#

import os
import shutil
import logging
from operator import attrgetter
from tempfile import mkdtemp

from .settings import settings
from .system import distribution, get_arch
from .utils import pretty_size, MiB, GiB
from .process import check_output
from . import device
from . import disk


logger = logging.getLogger(__name__)


class PartitionError(Exception):
    """Base class for exceptions in the partition module"""


class BootPartitionError(PartitionError):

    def __init__(self, message):
        PartitionError.__init__(self, "/boot: " + message)


class PartitionSetupError(Exception):
    """Base class for exceptions in the partition module"""


class PartitionSetup(object):
    """This class describes partition's configuration. It will be used
    during its creation on a device.
    """

    def __init__(self):
        self.size = 0 # size that will be used to create partition
        self.fs_hint_size = 0
        self.fs = None
        self._raid_level    = None
        self._raid_metadata = None

    def estimate_size(self, pretty=False):
        """Returns an estimation of the partition size once the target
        filesystem will be installed.
        """
        # FIXME: give a better approximation for RAID[56]
        size = max(self.size, self.fs_hint_size)
        if pretty:
            return pretty_size(size)
        return size

    @property
    def raid_level(self):
        if self._raid_level:
            return (self._raid_level, self._raid_metadata)

    def set_raid_level(self, level, metadata=None):
        self._raid_level = level
        if metadata:
            self._raid_metadata = metadata

#
# Note: we follow the "The Discoverable Partitions Specification":
#
# http://www.freedesktop.org/wiki/Specifications/DiscoverablePartitionsSpec/
#
# MBR type code (_typecode) is not currently used since we support
# only GPT scheme which uses guids for partition types. We'll remove
# typecode if no MBR scheme support is not needed.
#
class Partition(object):

    def __init__(self, name, label, is_optional=True, minsize=0):
        self._name = name
        self._label = label
        self._typecode = "8300" # Linux filesystem
        self._typeuuid = "0fc63daf-8483-4772-8e79-3d69d8477de4"
        self._is_optional = is_optional
        self._minsize = minsize
        self._device = None
        self._mnt_target  = None
        self._mnt_options = []
        self.setup = None

    @property
    def name(self):
        return self._name

    @property
    def label(self):
        """Returns the partition label according to its real name"""
        return distribution.distributor + '-' + self._label

    def typecode(self, uuid=True):
        if uuid:
            return self._typeuuid
        return self._typecode

    @property
    def minsize(self):
        return self._minsize

    @property
    def _invalid_fs(self):
        return ("swap", "linux_raid_member")

    def is_optional(self):
        return self._is_optional

    @property
    def is_swap(self):
        return False

    def _validate_fs(self, fs):
        """Check the passed fs matches this partition requirements"""
        if not fs:
            raise PartitionError("device is not formatted")
        if fs in self._invalid_fs:
            raise PartitionError("%s is an invalid filesystem" % fs)

    def _validate_dev(self, dev):
        """Check the passed device matches partition requirements"""
        if dev.size < self._minsize:
            minsize = pretty_size(self._minsize, KiB=False)
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
            settings.set("Partitions", self.name, dev.devpath)

        elif settings.get("Partitions", self.name):
            settings.remove("Partitions", self.name)

        self._device = dev

    def mount(self, target, options=[]):
        self.device.mount(target, options)
        self._mnt_options = options
        self._mnt_target  = target

    def umount(self):
        self.device.umount()
        self._mnt_options = []
        self._mnt_target  = None

    @property
    def mount_options(self):
        if not self._mnt_options:
            devpath = self.device.devpath
            opts = check_output(["findmnt", "-cvuno", "OPTIONS", devpath])
            opts = opts.split()[0].decode()
            opts = opts.split(',')

            # Before kernels 3.8, codepage option in fat filesystems
            # was stored by the kernel with the 'cp' prefix making the
            # display in /proc/mounts invalid. Fix it, so we can reuse
            # the options later. This has been fixed by commmit:
            # c6c20372bbb2f70d2757eed0a8d6860884bae11f
            opts = [opt.replace("codepage=cp", "codepage=") for opt in opts]

            self._mnt_options = opts
        return self._mnt_options


class SwapPartition(Partition):

    counter = 0

    def __init__(self):
        SwapPartition.counter += 1
        name  = 'swap%d' % SwapPartition.counter
        label = 'Swap%d' % SwapPartition.counter
        Partition.__init__(self, name, label)
        self._typecode = "8200"
        self._typeuuid = "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f"

    @property
    def is_swap(self):
        return True

    def _validate_fs(self, fs):
        if fs != 'swap':
            raise PartitionError(_("not swap formatted"))


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
        Partition.__init__(self, "/", "Root", minsize=256*MiB)
        self._is_optional = False

    def typecode(self, uuid=True):
        if not uuid:
            return self._typecode
        arch = get_arch()
        if arch == "x86_64":
            return "4f68bce3-e8cd-4db1-96e7-fbcaf984b709"
        if arch == "x86_32":
            return "44479540-f297-41b2-9af7-d131d5f0458a"
        raise PartitionError("not yet supported architecture %s" % arch)

    def _validate_fs(self, fs):
        Partition._validate_fs(self, fs)
        if fs in ('msdos', 'fat', 'vfat', 'ntfs'):
            raise PartitionError(_("come on, %s for your root partition !") % fs)

    def _validate_dev(self, dev):
        Partition._validate_dev(self, dev)

    @Partition.device.setter
    def device(self, dev):
        Partition.device.fset(self, dev)

        is_optional = True
        if dev:
            if dev.filesystem not in ('ext2', 'ext3', 'ext4', 'btrfs'):
                #
                # for any other fancy FS not supported by syslinux, we
                # request a separate /boot.
                #
                is_optional = False

            elif dev.devtype != 'partition':
                #
                # If / is using a whole disk, we request a separate
                # /boot since the firmware needs a partition table.
                #
                # if / is a MD device, we should check that the disk
                # container is partitioned and MD is using RAID1
                # metadata 0.9 or 1.0 but for simplicity's sake we
                # ignore that rare case.
                #
                is_optional = False
        boot._is_optional = is_optional


class BootPartition(Partition):

    def __init__(self):
        #
        # EFI specification does not require a min size for ESP
        # although 512MiB and higher tend to avoid some corner cases.
        #
        Partition.__init__(self, "/boot", "Boot", minsize=32*MiB)
        self._typecode = "8300"
        self._typeuuid = "c12a7328-f81f-11d2-ba4b-00a0c93ec93b"

    def is_optional(self):
        if "uefi" in settings.Options.firmware:
            return False
        return self._is_optional

    def _validate_fs(self, fs):
        # ESP partition on UEFI systems should use a FAT32 fs.
        if "uefi" in settings.Options.firmware and fs != "vfat":
            raise BootPartitionError(_("must use vfat on UEFI systems"))
        Partition._validate_fs(self, fs)

    def _validate_dev(self, dev):
        for p in disk.get_candidates(dev):
            # disk(s) containing /boot must have a partition table.
            if not p.scheme:
                raise BootPartitionError(_("must be on a disk with a table partition"))
            if "uefi" in settings.Options.firmware and p.scheme != 'gpt':
                raise PartitionError("GPT is required on UEFI systems")

        if type(dev) is device.MetadiskDevice:
            #
            # For now the only supported case: dev is a disk is when
            # it's a RAID1 MD device using 0.9 or 1.0 metadata.
            #
            if dev.level != 'raid1':
                raise BootPartitionError(_("only software RAID1 is allowed"))
            if dev.metadata not in ('0.90', '1.0'):
                raise BootPartitionError(_("doesn't use metadata 0.9 or 1.0"))

        Partition._validate_dev(self, dev)


class HomePartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/home", "Home", minsize=100*MiB)
        self._typecode = "8302"
        self._typeuuid = "933ac7e1-2eb4-4f13-b844-0e14e2aef915"


class VarPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/var", "Var", minsize=100*MiB)


# currently not used
class SrvPartition(Partition):

    def __init__(self):
        Partition.__init__(self, "/srv", "Server-Data", minsize=100*MiB)
        self._typeuuid = "3b8f8425-20e0-4f3b-907f-1a25a76f98e8"


root = RootPartition()
boot = BootPartition()
home = HomePartition()
var  = VarPartition()
swap = SwapPartition()

#
# Sort partitions in order to mount/umount them in order and make it
# readonly for simplicity.
#
partitions = sorted([root, home, var, boot, swap], key=attrgetter('name'))
partitions = tuple(partitions)


_rootfs_mntpnt = None

def mount_rootfs():
    global _rootfs_mntpnt
    assert(not _rootfs_mntpnt)

    for part in partitions:
        if part.device and not part.is_swap:
            if part.name == '/':
                _rootfs_mntpnt = mkdtemp()
                mntpnt = _rootfs_mntpnt
            else:
                mntpnt = _rootfs_mntpnt + part.name
                if not os.path.exists(mntpnt):
                    os.mkdir(mntpnt)
            part.mount(mntpnt)

    return _rootfs_mntpnt

def unmount_rootfs():
    global _rootfs_mntpnt

    if _rootfs_mntpnt:
        try:
            for part in reversed(partitions):
                if part.device and not part.is_swap:
                    part.umount()
            shutil.rmtree(_rootfs_mntpnt)
        except:
            # Workaround: for some unknown reasons, umounting the
            # rootfs fails sometimes. For now only reports this but
            # don't fail since it's not critical.
            logger.error("failed to cleanup rootfs mountpoint %s", _rootfs_mntpnt)
        finally:
            _rootfs_mntpnt = None

def find_partition(name):
    if name == '/root':
        name = '/'
    for part in partitions:
        if part.name == name:
            return part

def get_candidates(part, all=False):
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
                if bdev in get_candidates(part):
                    try:
                        part.device = bdev
                    except PartitionError:
                        logger.warn("incompatible changes in device %s for %s",
                                    bdev.devpath, part.name)

device.listen_uevent(__uevent_callback)
