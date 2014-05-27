# -*- coding: utf-8 -*-
#

from time import sleep
import logging

from installer import device, partition, disk
from installer.system import distribution, get_meminfo
from installer.process import monitor
from installer.settings import settings
from installer.utils import MiB, GiB
from . import Step


DEFAULT_FILESYSTEM = "ext4"
ROOT_DEFAULT_SIZE = 16 * GiB
ROOT_MIN_SIZE = 300 * MiB
HOME_MIN_SIZE = 20 * GiB
VAR_MIN_SIZE  = 20 * GiB
SWAP_MIN_SIZE = 100 * MiB


logger = logging.getLogger(__name__)


# Based on: https://access.redhat.com/site/documentation/en-US/Red_Hat_Enterprise_Linux/6/html/Installation_Guide/s2-diskpartrecommend-x86.html
def calculate_swap_size(memsize, hibernation=False):
    if memsize <= 2*GiB:
        factor = 2 if not hibernation else 3
        size   = factor * memsize
    elif memsize <= 8*GiB:
        factor = 1 if not hibernation else 2
        size   = memsize
    elif memsize < 64*GiB:
        factor = 0.5 if not hibernation else 1.5
        size   = factor * memsize
    else:
        size = 4*GiB

    return size


class DiskSetup(object):

    def __init__(self, disks, preset='small'):
        self._scheme = None
        self._disks  = disks
        self.preset = preset

        swap_is_mandatory = False # FIXME: should be given by the preset

        for with_swap in (True, False):
            try:
                self._create_partition_setup(with_swap)
                break
            except partition.PartitionSetupError:
                if with_swap and not swap_is_mandatory:
                    logger.warn(_("small disk(s), trying with no swap"))
                    continue
                raise

        if self.RAID:
            for p in self._partitions:
                if p == partition.boot:
                    p.setup.set_raid_level('raid1', '1.0')
                else:
                    if len(disks) == 2:
                        level = 'raid1'
                    elif len(disks) == 3:
                        # level 5 nécessite impérativement un minimum de trois disques durs
                        # at least 2 raid-devices needed for level 4 or 5
                        level = 'raid5'
                    elif len(disks) > 3:
                        # at least 4 raid-devices needed for level 6
                        # no more than 256 raid-devices supported for level 6
                        level = 'raid6'
                    p.setup.set_raid_level(level)

    def _create_partition_setup(self, with_swap):
        self._partitions = []

        total = self.disks[0].size
        for d in self.disks[1:]:
            total = min(total, d.size)
        free = total

        for part in partition.partitions:
            part.setup = partition.PartitionSetup()

        free = self._create_boot_partition(free)
        if with_swap:
            free = self._create_swap_partition(free, total)
        free = self._create_root_partition(free)
        free = self._create_data_partition(free)

    def _create_boot_partition(self, free):
        if self.RAID or "uefi" in settings.Options.firmware:
            if free < 1 * GiB:
                size = 34 * MiB
            elif free < 16 * GiB:
                size = 64 * MiB
            elif free < 32 * GiB:
                size = 128 * MiB
            elif free < 128 * GiB:
                size = 256 * MiB
            else:
                size = 512 * MiB

            if "uefi" in settings.Options.firmware:
                partition.boot.setup.fs = 'vfat'
            else:
                partition.boot.setup.fs = DEFAULT_FILESYSTEM

            partition.boot.setup.size = size
            self._partitions.append(partition.boot)
            free -= size
        return free

    def _create_swap_partition(self, free, total):
        if settings.Options.hostonly:
            meminfo = get_meminfo()
            memsize = meminfo['MemTotal']
        else:
            memsize = 2*GiB

        size = min(calculate_swap_size(memsize), total * 10/100)
        size = max(size, partition.swap.minsize)
        if free < size:
            raise partition.PartitionSetupError() # FIXME

        partition.swap.setup.fs   = "swap"
        partition.swap.setup.size = size
        self._partitions.append(partition.swap)
        return free - size

    def _create_root_partition(self, free):
        if free < partition.root.minsize:
            raise partition.PartitionSetupError() # FIXME

        if self.preset == 'small':
            partition.root.setup.fs_hint_size = free # remaining of the free space
            free = 0
        elif free >= ROOT_DEFAULT_SIZE:
            partition.root.setup.size = ROOT_DEFAULT_SIZE
            free -= ROOT_DEFAULT_SIZE
        else:
            raise partition.PartitionSetupError() # FIXME

        partition.root.setup.fs = DEFAULT_FILESYSTEM
        self._partitions.append(partition.root)
        return free

    def _create_data_partition(self, free):
        if self.preset in ('mail', 'web'):
            if self.preset == 'mail':
                part = partition.home
            elif self.preset == 'web':
                part = partition.var

            if free < part.minsize:
                raise partition.PartitionSetupError() # FIXME

            part.setup.fs = DEFAULT_FILESYSTEM
            part.setup.fs_hint_size = free # remaining of the free space
            self._partitions.append(part)
            free = 0
        return free

    @property
    def RAID(self):
        return len(self.disks) > 1

    @property
    def disks(self):
        return self._disks

    @property
    def partitions(self):
        return self._partitions


class PartitioningStep(Step):

    requires = ["license"]
    provides = ["partitioning"]

    def __init__(self):
        Step.__init__(self)
        global logger
        logger = self.logger
        self._setup = None
        self._devices = []

    @property
    def name(self):
        return _("Partitioning")

    def _cancel(self):
        raise NotImplementedError()

    def _monitor(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor(args, **kwargs)

    def _do_clean_disks(self):
        """wipefs all disks and their direct siblings"""
        self.logger.debug("cleaning disk(s)")
        for d in self._setup.disks:
            #
            # wipefs doens't clean signatures recursively, meaning
            # signatures stored on partitions are still
            # present. Therefore if we recreate an exact partition
            # layout than the previous one, all already present
            # signatures will be reused and udev will automatically
            # create the device (RAID signature is an example).
            #
            for p in d.get_partitions():
                self._monitor(['wipefs', '-a', p.devpath])
            self._monitor(['wipefs', '-a', d.devpath])

    def _do_partitioning_with_sgdisk(self, setup):
        self.logger.debug("partitioning disk(s) with sgdisk")
        cmd = ['sgdisk']

        # For small disks (<256Mo) use 64 sectors
        # alignment to avoid wasting too much space.
        if setup.disks[0].size < 256 * MiB:
            cmd += ['-a', '64']
        else:
            cmd += ['-a', '2048']

        # start by clearing out all partition data again.
        for d in setup.disks:
            self._monitor(cmd + ['-o', d.devpath])
        self.set_completion(20)

        for p in setup.partitions:
            #
            # - A partnum value of 0 causes the program to use the
            #   first available partition number.
            #
            # - A start value of 0 specifies the default value, which
            #   is the start of the largest available.
            #
            args  = ['--new=0:0:+%dK' % (p.setup.size / 1024)]
            args += ['--change-name=0:%s' % p.label]
            args += ['--typecode=0:%s' % p.typecode(uuid=True)]
            for d in setup.disks:
                self._monitor(cmd + args + [d.devpath])
        self.set_completion(50)

        #
        # Now that the partitions have been created, the associated
        # devices should be known by udev. Make sure we registered
        # these new devices.
        #
        self._monitor(["udevadm", "settle"])
        for d in setup.disks:
            while len(d.get_partitions()) < len(setup.partitions):
                sleep(0.5)
        self.set_completion(55)

        #
        # RAID case is handled later.
        #
        if not setup.RAID:
            self._devices = setup.disks[0].get_partitions()

    def _do_partitioning(self):
        self._do_partitioning_with_sgdisk(self._setup)

        #
        # A disk could have had a 'hidden' partition layout (the user
        # riped it out manually with wipefs). In that case we didn't
        # remove the signatures from its previous partitions.
        #
        # If we partition the disk with the same previous layout then
        # all partitions will reuse the old signatures. If one of them
        # indicates that the partition was part of a raid array then
        # udev will automatically restart the RAID array with this
        # partition.
        #
        while True:
            try:
                disk.check_candidates(self._setup.disks, RAID=False)
                break
            except disk.DiskRaidBusyError as e:
                    self._monitor(["mdadm", "--stop", e.md.devpath])
                    # wait the md device is gone
                    while e.md in device.leaf_block_devices():
                        sleep(0.1)

    def _do_soft_raid(self):
        if not self._setup.RAID:
            return

        disks = self._setup.disks
        md_devnames = []

        for i, p in enumerate(self._setup.partitions):
            md = p.label
            md_devnames.append(md)

            args = ['--force', '--run']
            level, metadata = p.setup.raid_level
            if metadata:
                args += ['--metadata=%s' % metadata]
            args += ['--level=%s' % level]
            args += ['--raid-devices=%d' % len(disks)]

            # component devices:
            args += [ d.get_partitions()[i].devpath for d in disks]

            self._monitor(['mdadm', '--create', md] + args)
            self._monitor(["udevadm", "settle", "-E", "/dev/md/" + md])

        # Retrieve the MD devices we have just created.
        for md in md_devnames:
            bdev = None
            while not bdev:
                for bdev in device.leaf_block_devices():
                    if type(bdev) == device.MetadiskDevice:
                        if bdev.md_devname == md:
                            break
                else:
                    sleep(0.5) # executed if no break
                    bdev = None
            self._devices.append(bdev)

    def _do_mkfs(self):
        for bdev, part in zip(self._devices, self._setup.partitions):
            fs = part.setup.fs
            if not fs:
                continue
            if fs == 'swap':
                self._monitor(['mkswap', bdev.devpath])
            else:
                opts = []
                if fs == 'vfat':
                    # Needed when the partition is actually a MD device.
                    opts = ['-I']
                if fs.startswith('ext'):
                    opts = ['-q']
                self._monitor(['mkfs', '-t', fs] + opts + [bdev.devpath])
            # make sure GUdev catch up
            while not bdev.filesystem:
                sleep(0.1)

    def _process(self):
        self._do_clean_disks()
        self.set_completion(10)
        self._do_partitioning()
        self.set_completion(60)
        self._do_soft_raid()
        self.set_completion(70)
        self._do_mkfs()

        for bdev, part in zip(self._devices, self._setup.partitions):
            part.device = bdev

    def initialize(self, disks, preset):
        self._setup = DiskSetup(disks, preset)
        return self._setup
