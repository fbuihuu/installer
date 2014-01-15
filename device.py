# -*- coding: utf-8 -*-
#

from subprocess import check_output, CalledProcessError
import gudev
import utils


class BlockDevice(object):

    def __init__(self, gudev):
        self._gudev = gudev

    def __eq__(self, other):
        return self._syspath == other._syspath

    def __ne__(self, other):
        return self._syspath != other._syspath

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

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Bus"),        self.bus),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       utils.pretty_size(self.size)),
                 (_("Scheme"),     self.scheme)]
        width = max([len(line[0]) for line in lines])

        return "\n".join(["%s : %s" % (("{0:%d}" % width).format(f), v)
                         for f, v in lines])


def on_uevent(client, action, bdev):
    return
    if action == "add":
        block_devices.append(bdev)
    if action == "remove":
        block_devices.remove(bdev)

block_devices = []
_client = gudev.Client(["block"])
_client.connect("uevent", on_uevent)

for bdev in _client.query_by_subsystem("block"):
    if bdev.get_devtype() == "disk":
        dev = BlockDevice(bdev)
    if bdev.get_devtype() == "partition":
        dev = PartitionDevice(bdev)
    block_devices.append(dev)
