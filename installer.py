#!/usr/bin/python
# -*- coding: utf-8 -*-
#

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


import sys
import logging
import gettext
from ui.urwid import UrwidUI


def load_all_menus():
    pass


class Installer(object):

    __version = "0.0"

    def __init__(self, ui="urwid"):

        reload(sys)
        sys.setdefaultencoding('utf-8')
        # For convenience, the _() function is installed by gettext.install()
        # in Python’s builtins namespace, so it is easily accessible in all
        # modules of our application.
        gettext.install('installer', '/usr/share/locale', unicode=True)

        self.logger = logging.getLogger(self.__module__)
        self.ui = UrwidUI()

        self.ui.register_hotkey("esc", self.quit)

    def run(self):
        self.logger.info("Starting installer")
        self.ui.header = "Installer %s for XXX" % self.__version
        self.ui.run()

    def quit(self):
        self.logger.info("Quitting installer")
        self.ui.quit()


if __name__ == "__main__":
    installer = Installer()
    installer.run()

    #import system
    #kbd = system.Keyboard()
    #print kbd.list_layouts()
