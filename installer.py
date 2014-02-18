#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import os
import sys
import locale
import logging
import gettext
import argparse
from ui.urwid import UrwidUI
from settings import settings, load_config_file
from utils import die


VERSION='0.0'
CONFIG_FILE='/etc/installer/installer.conf'
LOG_FILE='/tmp/installer.log'


def parse_cmdline():
    """Parses the relevant cmdline arguments"""

    parser = argparse.ArgumentParser(description="An easy way to install your favorite distribution")
    parser.add_argument("-c", "--config",
                        metavar='file',
                        help="Specify a configuration file")
    parser.add_argument("--log",
                        dest="logfile",
                        metavar='file',
                        help="Specify the log file")
    parser.add_argument("--version",
                        action='version',
                        version=VERSION)

    return parser.parse_args()


def main():
    locale.resetlocale()
    lang, enc = locale.getlocale()

    reload(sys)
    sys.setdefaultencoding('utf-8')

    args = parse_cmdline()

    #
    # Config file must be valid if specified by the user. If not
    # specified, it doesn't matter anymore if it exists or not
    #
    if args.config:
        if not os.path.exists(args.config):
            die("Can't find config file")
        config_file = args.config
    else:
        config_file = CONFIG_FILE
    load_config_file(config_file)

    #
    # Setting up the default logging facility: it uses a log file. If
    # the user wants to disable this it can pass '--config=/dev/null'.
    #
    # Each frontend can add additional hanlders to meet its needs.
    #
    logfile = LOG_FILE

    if args.logfile:
        settings.options.logfile = args.logfile
    if settings.options.logfile:
        logfile = settings.options.logfile

    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(name)-12s  %(message)s',
                        datefmt='%H:%M:%S',
                        filename=logfile, filemode='w',
                        level=logging.DEBUG)

    #
    # check the extra package list now to catch any errors early.
    #
    if settings.Packages.list:
        # ok this means that a config file has been read.
        pkgfile = settings.Packages.list
        pkgfile = os.path.join(os.path.dirname(config_file), pkgfile)
        if not os.path.exists(pkgfile):
            die("Can't find package list file")
        settings.Packages.list = pkgfile

    #
    # Start the frontend interface.
    #
    ui = UrwidUI(None, lang)
    ui.run()


if __name__ == "__main__":
    main()
