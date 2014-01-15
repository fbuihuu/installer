# -*- coding: utf-8 -*-
#

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
        if not fs or fs == "swap":
            return False
        return True

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, dev):
        if dev and not self._is_valid_fs(dev.filesystem):
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

optional_partitions = []
mandatory_partitions = []

for part in partitions:
    if part.is_optional:
        optional_partitions.append(part)
    else:
        mandatory_partitions.append(part)


def find_partition(name):
    for part in partitions:
        if part.name == name:
            return part


def get_candidates(part):
    candidates = []
    in_use_devices = [p.device for p in partitions if p != part and p.device]
    for dev in device.partition_devices:
        if dev in in_use_devices:
            continue
        if not part._is_valid_fs(dev.filesystem):
            continue
        # FIXME: test if the dev is currently mounted, ignore it in
        # that case.
        candidates.append(dev)
    return candidates
