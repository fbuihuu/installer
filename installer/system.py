#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import os
import re
from subprocess import check_output
from .systemd import localed


def reboot():
    process.call(["reboot"])

def poweroff():
    process.call(["poweroff"])

def is_efi():
    return os.path.exists("/sys/firmware/efi")


def _lsb_release(o):
    return check_output("lsb_release -s %s" % o, shell=True).decode().rstrip()

class Distribution(object):

    _distributor = _lsb_release('-i')
    _description = _lsb_release('-d')
    _release     = _lsb_release('-r')

    @property
    def distributor(self):
        return self._distributor

    @property
    def description(self):
        return self._description

    @property
    def release(self):
        return self._release

distribution = Distribution()


def get_meminfo():
    """Returns the content of /proc/meminfo through a dict"""
    meminfo = {}
    pattern = re.compile(r'^(\w+):\s*(\d+)\s*(\w+)?')

    for line in open('/proc/meminfo'):
        match = pattern.match(line)
        if match:
            key, value, unit = match.groups()
            value = int(value)
            if unit == 'kB':
                value *= 1024
            meminfo[key] = value
    return meminfo


def get_arch():
    arch = check_output(["uname", "-m"]).decode().rstrip()
    if arch in ("i686", "i586", "i486", "i386"):
        arch = "x86_32"
    return arch


class Keyboard(object):
    """Configure keyboard layout of the virtual console"""

    __keymap_dirs = ('/usr/lib/kbd/keymaps', '/usr/share/kbd/keymaps')
    __keymap_dir = None

    def __init__(self):
        for d in self.__keymap_dirs:
            if os.path.exists(d):
                self.__keymap_dir = d
                break
        self.__systemd_localed = localed.LocaledWrapper()

    def get_layout(self):
        return self.__systemd_localed.get_keyboard_info()["KEYTABLE"]

    def set_layout(self, name):
        self.__systemd_localed.set_keymap(name)

    def list_layouts(self):
        layouts = []
        for root, dirs, files in os.walk(self.__keymap_dir):
            for f in files:
                if f.endswith(".map") or f.endswith(".map.gz"):
                    layouts.append(f.split(".")[0])
        return layouts


class Language(object):
    pass


class TimeZone(object):

    __tz_list = []

    def __init__(self):
        pass

    def set(self):
        pass

    def get(self):
        pass

    def ls(self):
        pass
