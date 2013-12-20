#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import sys
import logging
import gettext
from ui.urwid import UrwidUI
from l10n import country_dict


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


logging.basicConfig(format='%(name)-12s%(levelname)-8s%(asctime)s  %(message)s',
                    datefmt='%H:%M:%S',
                    filename='/tmp/installer.log',
                    level=logging.DEBUG, filemode='w')
logger = logging.getLogger('installer')


class InstallerData(dict):

    def __init__(self):
        dict.__init__(self)

    def __getitem__(self, key):
        return dict.get(self, key, None)

    def __setitem__(self, key, value):

        if key == "localization/country":
            self["localization/locale"]   = country_dict[value][3]
            self["localization/timezone"] = country_dict[value][2]
            self["localization/keyboard"] = country_dict[value][1]

        elif key == "localization/locale":
            # change installer language
            lang, country = value.split("_")
            tr = gettext.translation('installer', localedir='po', languages=[lang], fallback=False)
            tr.install()
            pass

        elif key == "localization/keyboard":
            #if system.keyboard.get_layout() != value:
            #  self.logger.info(_("switching keyboard layout to %s") % value)
            #   system.keyboard.set_layout(value)
            pass

        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        if key in self:
            dict.__delitem__(self, key)


class Installer(object):

    __version = "0.0"

    def __init__(self, ui="urwid"):
        self.data = InstallerData()

        reload(sys)
        sys.setdefaultencoding('utf-8')
        # For convenience, the _() function is installed by gettext.install()
        # in Python’s builtins namespace, so it is easily accessible in all
        # modules of our application.
        gettext.install('installer', localedir='po', unicode=True)

        self.ui = UrwidUI(self)
        self.ui.register_hotkey("esc", self.quit)

    def run(self):
        logger.info("Starting installer")
        self.ui.run()

    def quit(self):
        logger.info("Quitting installer")
        # FIXME
        rootfs.umount()
        self.ui.quit()


if __name__ == "__main__":
    installer = Installer()
    installer.run()
    rootfs = None

    # import os, pdb
    # os.system('reset')
    # print 'Entering debug mode'
    # pdb.set_trace()
