# -*- coding: utf-8 -*-
#

import logging
import device
from utils import MiB, GiB


DISK_MINSIZE = 1 * MiB

logger = logging.getLogger(__name__)


class DiskError(Exception):
    """Base class for exceptions in the disk module"""

    def __init__(self, bdev=None, message=None):
        if not message:
            message = _("invalid for installation usage")
        if bdev:
            message = "{0}: {1}".format(bdev.devpath, message)
        Exception.__init__(self, message)
        self.bdev = bdev


class DiskRaidError(DiskError):
    """Base class for exceptions specific to RAID error"""
    pass


class DiskTooSmallError(DiskError):

    def __init__(self, bdev):
        message = _("disk is too small (< %d") % DISK_MINSIZE
        DiskError.__init__(self, bdev, message)


class DiskHasDataError(DiskError):
    pass


class DiskReadOnlyError(DiskError):

    def __init__(self, bdev):
        message = _("read only")
        DiskError.__init__(self, bdev, message)


class DiskBusyError(DiskError):

    def __init__(self, bdev, message=None):
        if not message:
            message = _("currently busy")
        DiskError.__init__(self, bdev, message)


class DiskRaidBusyError(DiskBusyError):

    def __init__(self, bdev, md):
        self.md = md
        message = _("disk is part of running RAID array %s") % md.devpath
        DiskBusyError.__init__(self, bdev, message)


def get_candidates():
    """Returns a list of device that could be suitable for an
    installation. The disk must be validated by check_candidate()
    before being used.
    """
    candidates = []

    for disk in device.root_block_devices():
        # Disk of that type can't be a good candidate.
        if type(disk) in (device.CdromDevice, device.FloppyDevice):
            continue
        candidates.append(disk)

    return candidates


def check_candidate(bdev):
    """Check that a single device, previously returned by
    get_candidates(), is suitable for an installation.
    """
    if bdev.is_readonly:
        raise DiskReadOnlyError(bdev)

    if bdev.size < DISK_MINSIZE:
        raise DiskTooSmallError(bdev)

    if bdev.mountpoints:
        raise DiskBusyError(bdev, _("currently mounted"))

    for pdev in bdev.get_partitions():
        if pdev.mountpoints:
            raise DiskBusyError(bdev, _("has at least one mounted partition"))

    # Check that the disk or its siblings are not part of a running
    # RAID array.
    for md in device.leaf_block_devices():
        if type(md) == device.MetadiskDevice:
            if bdev in md.get_root_parents():
                raise DiskRaidBusyError(bdev, md)


def check_candidates(bdevs, RAID=True):
    """Check that each device of the given list is suitable for an
    installation and if 'RAID' is true also check that those device
    can be used to create a RAID array.
    """
    for bdev in bdevs:
        check_candidate(bdev)

    if len(bdevs) < 2 or not RAID:
        return

    # Check that those disks can be used to create a RAID array.

    # should be part of the same bus.
    bus = bdevs[0].bus
    for d in bdevs[1:]:
        if d.bus != bus:
            raise DiskRaidError("disks can be combined into a RAID array")

    # don't mix SSD and HDD
    is_rotational = bdevs[0].is_rotational
    for d in bdevs[1:]:
        if d.is_rotational != is_rotational:
            raise DiskRaidError("can't mix SSD with rotational disk")

    # same size
    maxsize = 0
    for d in bdevs:
        if d.size > maxsize:
            maxsize = d.size

    for d in bdevs:
        if (maxsize - d.size) * 100 > maxsize:
            raise DiskRaidError("largest drive exceeds size by more than 1%")


def select_candidates(bdevs):
    """Given a list of disks, select the best candidates for a installation.
    Multiple disks can be returned meaning the proposed setup will use RAID.
    """
    buses = {}

    # sorts device by bus
    for d in bdevs:
        bus = d.bus
        if not bus:
            bus = 'misc'
        if not buses.get(bus):
            buses[bus] = []
        buses[bus].append(d)

    # Give priority to SATA disks. Disks with unknown buses are
    # treated at last.
    ata = buses.pop("ata", [])
    misc = buses.pop("misc", [])
    others = list(buses.values())

    for bdevs in [ata] + others + [misc]:
        candidates = []
        for bdev in bdevs:
            try:
                check_candidate(bdev)
            except DiskError as e:
                logger.debug("skipping %s: %s", bdev.devpath, e)
                continue
            else:
                candidates.append(bdev)

        if not candidates:
            continue
        if len(candidates) == 1:
            # easy case only one disk can be used for an installation.
            return candidates

        # try to build a RAID array
        try:
            check_candidates(candidates)
        except DiskRaidError:
            #
            # several disks are good candidates but can't be combined into
            # a RAID array, let the user choose the good one.
            #
            logger.error("skipping %s: multiple choices possible" %
                         [d.devpath for d in candidates])
            return []
        return candidates

    # no good disk has been found
    return []
