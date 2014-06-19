#!/usr/bin/python
# -*- coding: utf-8 -*-
#
import os
import sys
import logging
import locale
import gettext

from . import get_topdir

#
# FileNotFoundError is not available on python 2.x
#
try:
    FileNotFoundError
except NameError:
    FileNotFoundError = IOError


logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Base class for exceptions for the l10n module."""


#
# a Zone is a country's area with a specific timezone (mainly).
#
class Zone(object):

    def __init__(self, city, timezone, country, keymap, locale):
        self.city     = city
        self.timezone = timezone
        self.keymap   = keymap
        self.locale   = locale
        self.country  = country # country code


class BrazilZone(Zone):
    def __init__(self, city, timezone):
        super(BrazilZone, self).__init__(city, timezone, 'BR', 'br-abnt2', 'pt_BR')


class UsaZone(Zone):
    def __init__(self, city, timezone):
        super(UsaZone, self).__init__(city, timezone, 'US', 'us', 'en_US')


country_zones = None
country_names = None

#
#
#
def set_translation(lang):
    global country_zones, country_names

    # Try changing the prog current locale but that's really not a big
    # deal if that fails.
    try:
        locale.setlocale(locale.LC_ALL, lang)
    except locale.Error:
        logger.debug("failed to set current locale to %s" % lang)

    #
    # However failing to find a translation for this lang is more
    # annoying since the user will notice.
    #
    localedir = None
    if get_topdir():
        localedir = os.path.join(get_topdir(), 'build/mo')
    try:
        trans = gettext.translation('installer', languages=[lang],
                                    localedir=localedir)
    except FileNotFoundError:
        assert(lang != 'en_US')
        logger.warn("No translation found for '%s' language", lang)
        raise TranslationError()

    #
    # In Python 2, ensure that the _() that gets installed
    # into built-ins always returns unicodes.  This matches
    # the default behavior under Python 3, although that
    # keyword argument is not present in the Python 3 API.
    #
    # http://www.wefearchange.org/2012/06/the-right-way-to-internationalize-your.html
    #
    kwargs = {}
    if sys.version_info[0] < 3:
        kwargs['unicode'] = True
    trans.install(**kwargs)

    # The first zone of the list of each country is the prefered one.
    country_zones = {
        'BR' : [
            BrazilZone(_('Curitiba'),  'America/Cuiaba'),
            BrazilZone(_('Sao Paulo'), 'America/Sao_Paulo'),
        ],
        'FR' : [
            Zone(_('Paris'), 'Europe/Paris', 'FR', 'fr', 'fr_FR')
        ],
        'US' : [
            UsaZone(_('New York'),    'America/New_York'),
            UsaZone(_('Los Angeles'), 'America/Los_Angeles'),
            UsaZone(_('Denver'),      'America/Denver'),
        ],
    }

    country_names = {
        'BR' : _('Brazil'),
        'FR' : _('France'),
        'US' : _('United States'),
    }

# Init module, with the current local. The current locale is probably
# not yet reseted by the installer: use the default locale.
set_translation(locale.getdefaultlocale()[0])

#
# Time zones
#
timezones = []
timezones_path = None

def init_timezones(path, prefix=None):
    global timezones_path
    timezones_path = path
    if prefix:
        path = os.path.join(prefix, path.lstrip('/'))
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            tz = os.path.relpath(os.path.join(dirpath, f), path)
            timezones.append(tz)
    timezones.sort()

#
# Keymaps
#
keymaps = []
keymaps_path = None

def init_keymaps(path, prefix=None):
    global keymaps_path
    keymaps_path = path
    if prefix:
        path = os.path.join(prefix, path.lstrip('/'))
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            if f.endswith('.map'):
                f = f[:-4]
            elif f.endswith('.map.gz'):
                f = f[:-7]
            else:
                continue
            keymaps.append(f)
    keymaps.sort()

