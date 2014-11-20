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

    def __init__(self, city, timezone, country, keymap, locale):
        self.city     = city
        self.timezone = timezone
        self.country  = country # country code
        self.keymap   = keymap
        self.locale   = locale


class BrazilZone(Zone):
    def __init__(self, city, timezone):
        super(BrazilZone, self).__init__(city, timezone, 'BR', 'br-abnt2', 'pt_BR')


class UsaZone(Zone):
    def __init__(self, city, timezone):
        super(UsaZone, self).__init__(city, timezone, 'US', 'us', 'en_US')


country_zones = None
country_names = None
language = None

#
#
#
def set_translation(lang):
    global country_zones, country_names, language

    if not lang:
        lang = 'en_US'

    # Try changing the prog current locale but that's really not a big
    # deal if that fails.
    try:
        # On Python 2.7, locale can't be unicode: basically it should
        # had been allowed but it's too late, see link below for
        # details: http://bugs.python.org/issue3067)
        if sys.version_info[0] < 3:
            lang = lang.encode('ascii')

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

    trans = gettext.translation('installer', languages=[lang],
                                localedir=localedir, fallback=True)
    #
    # If no translation was found then use the default language which
    # is en_US.
    #
    if type(trans) == gettext.NullTranslations:
        if lang != 'en_US':
            logger.warn("No translation found for '%s' language", lang)
            lang = 'en_US'

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

# Install _() with the default language used by the installer.
set_translation(None)

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

