# -*- coding: utf-8 -*-
#

import os
import logging
from subprocess import check_output, check_call, CalledProcessError
from gi.repository import GUdev
import utils
from process import monitor


logger = logging.getLogger(__name__)


block_devices = []


def leaf_block_devices():
    """Returns the list of partition devices or any block devices
    without partitions.
    """
    leaves = block_devices.copy()
    for dev in block_devices:
        for parent in dev.get_parents():
            if parent in leaves:
                leaves.remove(parent)
    return leaves

def root_block_devices():
    """Returns the list of root block devices"""
    roots = []
    for dev in block_devices:
        if dev.devtype != 'disk':
            continue
        if dev.get_parents():
            continue
        if dev in roots:
            continue
        roots.append(dev)
    return roots

def _syspath_to_bdev(syspath):
    for dev in block_devices:
        if os.path.samefile(dev.syspath, syspath):
            return dev

def _format_description(lines):
    width = max([len(line[0]) for line in lines])
    return "\n".join(["{f:<{w}} : {v}".format(f=f, v=v, w=width)
                      for f, v in lines])


class DeviceError(Exception):
    """Base class for exceptions for the device module."""

    def __init__(self, dev, *args):
        self.dev = dev
        Exception.__init__(self, *args)

    def __str__(self):
        return self.dev.devpath + ": " + Exception.__str__(self)


class SignatureDeviceError(DeviceError):

    def __init__(self, dev, *args):
        message = "disk has multiple signatures making it hazardous to use"
        DeviceError.__init__(self, dev, message)


class BlockDevice(object):

    def __init__(self, gudev):
        self._gudev = gudev
        self._mntpoint = None

    def __eq__(self, other):
        return other and other.syspath == self.syspath

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def syspath(self):
        return os.path.abspath(self._gudev.get_sysfs_path())

    @property
    def devpath(self):
        return self._gudev.get_device_file()

    @property
    def devtype(self):
        return self._gudev.get_devtype()

    @property
    def major(self):
        return int(self._gudev.get_property("MAJOR"))

    @property
    def minor(self):
        return int(self._gudev.get_property("MINOR"))

    @property
    def model(self):
        return self._gudev.get_property("ID_MODEL")

    @property
    def bus(self):
        return self._gudev.get_property("ID_BUS")

    @property
    def size(self):
        return self._gudev.get_sysfs_attr_as_int('size') * 512

    @property
    def is_readonly(self):
        return self._gudev.get_sysfs_attr_as_boolean('ro')

    @property
    def filesystem(self):
        return self._gudev.get_property("ID_FS_TYPE")

    @property
    def fsuuid(self):
        return self._gudev.get_property("ID_FS_UUID")

    @property
    def fslabel(self):
        return self._gudev.get_property("ID_FS_LABEL")

    def validate(self):
        if self.devtype == 'disk' and self.scheme and self.filesystem:
            raise SignatureDeviceError(self)

    @property
    def mountpoints(self):
        if self.filesystem:
            try:
                args = ["findmnt", "-n", "-o", "TARGET", "--source", self.devpath]
                return check_output(args).decode().split()
            except CalledProcessError:
                pass
        return []

    def mount(self, mountpoint):
        if self._mntpoint:
            raise Exception()
        monitor(["mount", self.devpath, mountpoint], logger=logger)
        self._mntpoint = mountpoint

    def umount(self):
        if self._mntpoint:
            monitor(["umount", self._mntpoint], logger)
            mntpnt = self._mntpoint
            self._mntpoint = None
            return mntpnt

    def get_root_parents(self):
        """Give the list of the very first parent(s)"""
        if not self.get_parents():
            return [self]

        roots = []
        for parent in self.get_parents():
            roots.extend(parent.get_root_parents())
        return roots

    def iterparents(self):
        """Helper to recursively yield all device parents"""
        yield self
        for p in self.get_parents():
            for gp in p.iterparents():
                yield gp

    def is_compound(self):
        """Indicate if the device is built unpon other devices"""
        parents = self.get_parents()
        if len(parents) > 1:
            return True
        if not parents:
            return False
        return parents[0].is_compound()

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Bus"),        self.bus),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       utils.pretty_size(self.size)),
                 (_("Scheme"),     self.scheme)]
        return _format_description(lines)


class DiskDevice(BlockDevice):

    def __init__(self, gudev):
        super(DiskDevice, self).__init__(gudev)

    @property
    def is_removable(self):
        return self._gudev.get_sysfs_attr_as_boolean('removable')

    @property
    def is_rotational(self):
        return self._gudev.get_sysfs_attr_as_boolean('queue/rotational')

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_TABLE_TYPE")

    @property
    def partuuid(self):
        assert(not self._gudev.get_property("ID_PART_ENTRY_UUID"))

    @property
    def partlabel(self):
        assert(not self._gudev.get_property("ID_PART_ENTRY_NAME"))

    def get_parents(self):
        """Gives the list of direct parent(s)"""
        return []

    def get_partitions(self):
        parts = []
        for dev in block_devices:
            if dev.devtype != 'partition':
                continue
            if dev.syspath.startswith(self.syspath):
                parts.append(dev)
        parts.sort(key=lambda part: part.syspath)
        return parts


class RamDevice(DiskDevice):

    @property
    def bus(self):
        return "ram"

    @property
    def model(self):
        return "RAM disk #%d" % self.minor


class LoopDevice(DiskDevice):

    @property
    def bus(self):
        return "loop"

    @property
    def model(self):
        return "Loopback device #%d" % (self.minor/16 + 1)

    @property
    def backing_file(self):
        try:
            return gudev.get_sysfs_attr_as_strv('loop/backing_file')[0]
        except IndexError:
            return None

    def __str__(self):
        lines = [(_("Model"),          self.model),
                 (_("Backing File"),   self.backing_file),
                 (_("Filesystem"),     self.filesystem),
                 (_("Size"),           utils.pretty_size(self.size)),
                 (_("Scheme"),         self.scheme)]
        return _format_description(lines)


class FloppyDevice(DiskDevice):

    @property
    def model(self):
        return "floppy disk"


class CdromDevice(DiskDevice):

    @property
    def model(self):
        if super(CdromDevice, self).model:
            return super(CdromDevice, self).model
        return "SCSI CDROM"


class MetadiskDevice(DiskDevice):

    @property
    def model(self):
        return "MD %s" % self.level

    @property
    def level(self):
        return self._gudev.get_property("MD_LEVEL")

    @property
    def metadata_version(self):
        return self._gudev.get_property("MD_METADATA")

    def get_parents(self):
        parents = []
        #
        # Accessing sysfs path directly is not a good idea because the
        # device might have already been removed but the python udev
        # lib is still not aware. But I don't see any other way: the
        # exported info given by 'mdadm --detail --export' are not
        # usable.
        #
        md_dir = os.path.join(self.syspath, 'md')
        try:
            for f in os.listdir(md_dir):
                if f.startswith('dev-'):
                    parent = _syspath_to_bdev(os.path.join(md_dir, f, 'block'))
                    if parent:
                        parents.append(parent)
        except FileNotFoundError:
            parent = []
        else:
            assert(parents)
        return parents

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Metadata"),   self.metadata_version),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       utils.pretty_size(self.size)),
                 (_("Scheme"),     self.scheme)]
        return _format_description(lines)


class PartitionDevice(BlockDevice):

    def __init__(self, gudev):
        super(PartitionDevice, self).__init__(gudev)

    @property
    def is_removable(self):
        return False

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_ENTRY_SCHEME")

    @property
    def partuuid(self):
        #
        # partuuid is normally GPT only, but newer versions of libblkid
        # (util-linux >= 2.24) introduced partuuid for MBR to:
        # http://git.kernel.org/cgit/utils/util-linux/util-linux.git/commit/?id=d67cc2889a0527b26
        #
        # This will allow to use root=PARTUUID for MBR too but since
        # this feature is relatively new, distros haven't still
        # updated their udev rules to create the symlinks in
        # /dev/disk/by-partuuid.
        #
        # Therefore, we force partuuid to be null for any scheme by
        # GPT.
        #
        if self.scheme == 'gpt':
            return self._gudev.get_property("ID_PART_ENTRY_UUID")

    @property
    def partlabel(self):
        # same comments as in partuuid().
        if self.scheme == 'gpt':
            return self._gudev.get_property("ID_PART_ENTRY_NAME")

    @property
    def partnum(self):
        return int(self._gudev.get_property("ID_PART_ENTRY_NUMBER"))

    def get_parents(self):
        pdev = _syspath_to_bdev(os.path.join(self.syspath, ".."))
        if not pdev:
            raise DeviceError(self, "partition has no direct parent !")
        return [pdev]


__uevent_handlers = []

def listen_uevent(cb):
    __uevent_handlers.append(cb)

def __notify_uevent_handlers(action, bdev):
    for cb in __uevent_handlers:
        #
        # pygobject cannot propagate exceptions from a callback back
        # to the main thread. For now, only log them athough it will
        # lead to a fatal error.
        #
        try:
            cb(action, bdev)
        except:
            logger.exception("uevent callback got an unexpected exception")

def __on_add_uevent(gudev):
    bdev = None

    major = gudev.get_property_as_int("MAJOR")
    if gudev.get_devtype() == "partition":
        bdev = PartitionDevice(gudev)
    elif major == 1:
        bdev = RamDevice(gudev)
    elif major == 2:
        bdev = FloppyDevice(gudev)
    elif major == 7:
        bdev = LoopDevice(gudev)
        if not bdev.backing_file:
            bdev = None
    elif major == 9:
        bdev = MetadiskDevice(gudev)
    elif major == 11:
        bdev = CdromDevice(gudev)
    elif gudev.get_property_as_boolean("ID_CDROM_DVD"):
        bdev = CdromDevice(gudev)
    elif gudev.get_property_as_boolean("ID_CDROM"):
        bdev = CdromDevice(gudev)
    elif gudev.get_devtype() == "disk":
        bdev = DiskDevice(gudev)

    if bdev:
        block_devices.append(bdev)
        __notify_uevent_handlers("add", bdev)

def __on_remove_uevent(gudev):
    for bdev in block_devices:
        if bdev.syspath == gudev.get_sysfs_path():
            block_devices.remove(bdev)
            __notify_uevent_handlers("remove", bdev)

def __on_change_uevent(gudev):
    for bdev in block_devices:
        if bdev.syspath == gudev.get_sysfs_path():
            bdev._gudev = gudev
            __notify_uevent_handlers("change", bdev)

def __on_uevent(client, action, gudev):
    if action == "add":
        __on_add_uevent(gudev)
    if action == "remove":
        __on_remove_uevent(gudev)
    if action == "change":
        __on_change_uevent(gudev)

__client = GUdev.Client(subsystems=["block"])
__client.connect("uevent", __on_uevent)
for gudev in __client.query_by_subsystem("block"):
    __on_add_uevent(gudev)
