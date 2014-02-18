#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import sys
import locale
import logging
import gettext
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


logging.basicConfig(format='%(name)-12s%(levelname)-8s%(asctime)s  %(message)s',
                    datefmt='%H:%M:%S',
                    filename='/tmp/installer.log',
                    level=logging.DEBUG, filemode='w')
logger = logging.getLogger()


class Installer(object):

    __version = "0.0"

    def __init__(self, ui="urwid"):

        locale.resetlocale()
        lang, enc = locale.getlocale()

        reload(sys)
        sys.setdefaultencoding('utf-8')

        self.ui = UrwidUI(self, lang)

    def run(self):
        logger.info("Starting installer")
        self.ui.run()

    def quit(self):
        logger.info("Quitting installer")
        self.ui.quit()


if __name__ == "__main__":
    installer = Installer()
    installer.run()

    # import os, pdb
    # os.system('reset')
    # print 'Entering debug mode'
    # pdb.set_trace()
