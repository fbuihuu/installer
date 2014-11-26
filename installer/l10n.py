# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import os
import sys
import logging
import locale
import gettext

from . import get_topdir


logger = logging.getLogger(__name__)


#
# a Zone is a country's area with a specific timezone (mainly).
#
class Zone(object):

    def __init__(self, city, timezone, ccode, keymap, locale):
        self.city     = city
        self.timezone = timezone
        self.ccode    = ccode # country code
        self.keymap   = keymap
        self.locale   = locale


class BrazilZone(Zone):
    def __init__(self, city, timezone):
        super(BrazilZone, self).__init__(city, timezone, 'BR', 'br-abnt2', 'pt_BR')

    @property
    def country(self):
        return _('Brazil')


class FranceZone(Zone):
    def __init__(self, city, timezone):
        super(FranceZone, self).__init__(city, timezone, 'FR', 'fr', 'fr_FR')

    @property
    def country(self):
        return _('France')


class UsaZone(Zone):
    def __init__(self, city, timezone):
        super(UsaZone, self).__init__(city, timezone, 'US', 'us', 'en_US')

    @property
    def country(self):
        return _('United State')


# The first zone of the list of each country is the prefered one.
def get_country_zones():
    return [
        # BR
        BrazilZone(_('Curitiba'),  'America/Cuiaba'),
        BrazilZone(_('Sao Paulo'), 'America/Sao_Paulo'),
        # FR
        FranceZone(_('Paris'),     'Europe/Paris'),
        # US
        UsaZone(_('New York'),    'America/New_York'),
        UsaZone(_('Los Angeles'), 'America/Los_Angeles'),
        UsaZone(_('Denver'),      'America/Denver'),
    ]


def _get_zone(locale):
    for z in get_country_zones():
        if z.locale.startswith(locale):
            return z


def get_language_zone():
    return _get_zone(language)


language = None

#
# This initializes the installer locale setting. It can be called
# either during initialization or later if the user decides to switch
# the language used by the installer.
#
def set_locale(value):
    try:
        if value == '':
            # Calling resetlocale() sets the locale to the first value
            # found in 'LC_ALL', 'LC_CTYPE', 'LANG', in that order
            # (this search path is used in GNU setlocale(3)).
            locale.resetlocale(locale.LC_ALL)
        else:
            # On Python 2.7, locale can't be unicode: basically it should
            # had been allowed but it's too late, see link below for
            # details: http://bugs.python.org/issue3067). On Python 3.x,
            # str() is a nop.
            locale.setlocale(locale.LC_ALL, str(value))

    except locale.Error:
        logger.debug("failed to set current locale to %s" % value)


def set_language(lang):
    global language

    #
    # Use the translation in the source topdir if the installer is run
    # from there.
    #
    localedir = None
    if get_topdir():
        localedir = os.path.join(get_topdir(), 'build/mo')

    # If lang is '', the lang used by gettext, to search the .mo, will
    # be given by the first value found in LANGUAGE, LC_ALL,
    # LC_MESSAGES, and LANG in that order. This order is the same as
    # GNU gettext(3).
    #
    langs = [lang] if lang else None

    #
    # This is used to find out which language will be used by gettext
    # specially when lang is ''. In that case the lang can't be retrieve
    # from the current locale since locale.getlocale() doesn't take
    # into account LANGUAGE env variable.
    #
    # In case of succes gettext.find() returns a path which has the
    # following form: <localedir>/<language>/LC_MESSAGES/<domain>.mo
    #
    mo = gettext.find('installer', languages=langs, localedir=localedir)
    if mo:
        lang = mo.split('/')[-3]
    elif lang:
        lang = 'en_US'
        logger.warn("No translation found for '%s' language", lang)
    else:
        lang = 'en_US'
        logger.warn("No translation found for current locale")

    #
    # If no translation was found then use the default language which
    # is en_US.
    #
    trans = gettext.translation('installer', languages=[lang],
                                localedir=localedir)

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

    language = lang


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

