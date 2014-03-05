#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import os
from subprocess import check_output
from systemd import localed


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
