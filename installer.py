#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import sys
import logging
import gettext
from rootfs import RootFS
from ui.urwid import UrwidUI


def parse_cmdline():
    """Parses the relevant cmdline arguments
    """
    parser = OptionParser()
    parser.add_option("--dry",
                      action='store_true',
                      dest="dry",
                      default=False,
                      help="Just write defaults, nothing else")
    parser.add_option("--debug",
                      action='store_true',
                      dest="debug",
                      default=False,
                      help="Run in debug mode (suitable for pdb)")

    return parser.parse_args()


rootfs = RootFS()
#rootfs.synchronize(None)

installer = None

class Installer(object):

    __version = "0.0"

    _location = None
    _timezone = None
    _kbd_layout = None
    _locale = None

    def __init__(self, ui="urwid"):

        reload(sys)
        sys.setdefaultencoding('utf-8')
        # For convenience, the _() function is installed by gettext.install()
        # in Python’s builtins namespace, so it is easily accessible in all
        # modules of our application.
        gettext.install('installer', '/usr/share/locale', unicode=True)

        self.logger = logging.getLogger(self.__module__)
        self.ui = UrwidUI(self)

        self.ui.register_hotkey("esc", self.quit)

    def run(self):
        self.logger.info("Starting installer")
        self.ui.header = "Installer %s for XXX" % self.__version
        self.ui.run()

    def quit(self):
        self.logger.info("Quitting installer")
        # FIXME
        rootfs.umount()
        self.ui.quit()

    @property
    def kbd_layout(self):
        return self._kbd_layout

    @kbd_layout.setter
    def kbd_layout(self, layout):
        # if system.keyboard.get_layout() != layout:
        # FIXME: self.ui.info(_("switching current keyboard layout to %s") % layout)
        # FIXME: system.keyboard.set_layout(layout)
        self._kbd_layout = layout

    @property
    def location(self):
        return self._location

    @location.setter
    def location(self, place):
        self._locale     = country_dict[place][3]
        self._timezone   = country_dict[place][2]
        self._kbd_layout = country_dict[place][1]
        self._location   = place


if __name__ == "__main__":
    installer = Installer()
    installer.run()
    rootfs = None

    # import os, pdb
    # os.system('reset')
    # print 'Entering debug mode'
    # pdb.set_trace()
