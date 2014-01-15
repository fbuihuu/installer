#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import os
import platform
import systemd.localed


def reboot():
    process.call(["reboot"])

def poweroff():
    process.call(["poweroff"])

def is_efi():
    return os.path.exists("/sys/firmware/efi")


class Distribution(object):

    _linux_distribution = platform.linux_distribution()

    @staticmethod
    def name():
        return distribution._linux_distribution[0]

    @staticmethod
    def version():
        return distribution._linux_distribution[1]

    @staticmethod
    def id():
        return distribution._linux_distribution[2]


class Keyboard(object):
    """Configure keyboard layout of the virtual console"""

    __keymap_dirs = ('/usr/lib/kbd/keymaps', '/usr/share/kbd/keymaps')
    __keymap_dir = None

    def __init__(self):
        for d in self.__keymap_dirs:
            if os.path.exists(d):
                self.__keymap_dir = d
                break
        self.__systemd_localed = systemd.localed.LocaledWrapper()

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
