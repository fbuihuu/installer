# -*- coding: utf-8 -*-
#

from subprocess import check_output, check_call, CalledProcessError
import gudev
import utils


class BlockDevice(object):

    def __init__(self, gudev):
        self._gudev = gudev

    def __eq__(self, other):
        return other and other._syspath == self._syspath

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def _syspath(self):
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


class PartitionDevice(BlockDevice):

    def __init__(self, gudev):
        super(PartitionDevice, self).__init__(gudev)
        self._mntpoint = None

    @property
    def filesystem(self):
        return self._gudev.get_property("ID_FS_TYPE")

    @property
    def size(self):
        with open(self._syspath + "/size", 'r') as f:
            size = f.read()
        return int(size) * 512

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_ENTRY_SCHEME")

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
            self._mntpoint = None

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Bus"),        self.bus),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       utils.pretty_size(self.size)),
                 (_("Scheme"),     self.scheme)]
        width = max([len(line[0]) for line in lines])

        return "\n".join(["%s : %s" % (("{0:%d}" % width).format(f), v)
                         for f, v in lines])


block_devices = []
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
        if bdev._syspath == gudev.get_sysfs_path():
            block_devices.remove(bdev)
            __notify_uevent_handlers("remove", bdev)

def __on_uevent(client, action, gudev):
    if action == "add":
        __on_add_uevent(gudev)
    if action == "remove":
        __on_remove_uevent(gudev)

__client = gudev.Client(["block"])
__client.connect("uevent", __on_uevent)
for gudev in __client.query_by_subsystem("block"):
    __on_add_uevent(gudev)
