# -*- coding: utf-8 -*-
#

from subprocess import check_output, check_call, CalledProcessError
import gudev
import utils
import os


block_devices = []


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


class MountedDeviceError(DeviceError):

    def __init__(self, dev, *args):
        message = "is currently mounted, no harm will be done"
        DeviceError.__init__(self, dev, message)


class BlockDevice(object):

    def __init__(self, gudev):
        self._gudev = gudev
        self._mntpoint = None

    def __eq__(self, other):
        return other and os.path.samefile(other.syspath, self.syspath)

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def syspath(self):
        return self._gudev.get_sysfs_path()

    @property
    def devpath(self):
        return self._gudev.get_device_file()

    @property
    def devtype(self):
        return self._gudev.get_devtype()

    @property
    def model(self):
        return self._gudev.get_property("ID_MODEL")

    @property
    def bus(self):
        return self._gudev.get_property("ID_BUS")

    @property
    def size(self):
        with open(self.syspath + "/size", 'r') as f:
            size = f.read()
        return int(size) * 512

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_TABLE_TYPE")

    @property
    def filesystem(self):
        return self._gudev.get_property("ID_FS_TYPE")

    @property
    def fsuuid(self):
        return self._gudev.get_property("ID_FS_UUID")

    @property
    def fslabel(self):
        return self._gudev.get_property("ID_FS_LABEL")

    @property
    def partuuid(self):
        partuuid = self._gudev.get_property("ID_PART_ENTRY_UUID")
        assert(not partuuid)
        return partuuid

    @property
    def partlabel(self):
        partlabel = self._gudev.get_property("ID_PART_ENTRY_NAME")
        assert(not partlabel)
        return partlabel

    def validate(self):
        if self.devtype == 'disk' and self.scheme and self.filesystem:
            raise SignatureDeviceError(self)
        if self.mountpoints:
            raise MountedDeviceError(self)

    @property
    def mountpoints(self):
        if self.filesystem:
            try:
                cmd = "findmnt -n -o TARGET --source " + self.devpath
                return check_output(cmd, shell=True).split()
            except CalledProcessError:
                pass
        return []

    def mount(self, mountpoint):
        if self._mntpoint:
            raise Exception()
        cmd = "mount %s %s" % (self.devpath, mountpoint)
        check_call(cmd, shell=True)
        self._mntpoint = mountpoint

    def umount(self):
        if self._mntpoint:
            check_call("umount %s" % self._mntpoint, shell=True)
            mntpnt = self._mntpoint
            self._mntpoint = None
            return mntpnt

    def get_parents(self):
        """Gives the list of direct parent(s)"""
        return []

    def get_root_parents(self):
        """Give the list of the very first parent(s)"""
        if not self.get_parents():
            return [self]

        roots = []
        for parent in self.get_parents():
            roots.extend(parent.get_root_parents())
        return roots

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Bus"),        self.bus),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       utils.pretty_size(self.size)),
                 (_("Scheme"),     self.scheme)]
        width = max([len(line[0]) for line in lines])

        return "\n".join(["%s : %s" % (("{0:%d}" % width).format(f), v)
                         for f, v in lines])


class PartitionDevice(BlockDevice):

    def __init__(self, gudev):
        super(PartitionDevice, self).__init__(gudev)

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_ENTRY_SCHEME")

    @property
    def partuuid(self):
        return self._gudev.get_property("ID_PART_ENTRY_UUID")

    @property
    def partlabel(self):
        return self._gudev.get_property("ID_PART_ENTRY_NAME")

    def get_parents(self):
        parent = os.path.join(self.syspath, "..")
        for dev in block_devices:
            if os.path.samefile(dev.syspath, parent):
                return [dev]
        # Can't be reached.
        raise DeviceError(self, "partition %s has no direct parent !")


__uevent_handlers = []

def listen_uevent(cb):
    __uevent_handlers.append(cb)

def __notify_uevent_handlers(action, bdev):
    for cb in __uevent_handlers:
        cb(action, bdev)

def __on_add_uevent(gudev):
    if gudev.get_devtype() == "partition":
        bdev = PartitionDevice(gudev)
    else:
        bdev = BlockDevice(gudev)
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

__client = gudev.Client(["block"])
__client.connect("uevent", __on_uevent)
for gudev in __client.query_by_subsystem("block"):
    __on_add_uevent(gudev)
