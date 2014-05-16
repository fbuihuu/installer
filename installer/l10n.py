#!/usr/bin/python
# -*- coding: utf-8 -*-
#
import os
import sys
import logging
import locale
import gettext

from . import get_topdir

logger = logging.getLogger(__name__)


# [1]: default time zone
# [2]: default keymap
# [3]: default locale (<language>_<country>)

country_dict = {
    'America':  [ 'America/New_York', 'us',        'en_US'],
    'Brasil':   [ 'Brazil/West',      'br-abnt2',  'pt_BR'],
    'Deutsch':  [ 'Europe/Berlin',    'de',        'de_DE'],
    'France':   [ 'Europe/Paris',     'fr',        'fr_FR'],
}


def set_locale(lang):
    try:
        locale.setlocale(locale.LC_ALL, lang)
    except locale.Error:
        logger.warn("failed to set current locale to %s", lang)


def set_translation(lang):
    localedir = None
    if get_topdir():
        localedir = os.path.join(get_topdir(), 'build/mo')

    trans = gettext.translation('installer', languages=[lang],
                                localedir=localedir, fallback=True)

    #
    # If no translation was found then use the default language which
    # is en_US.
    #
    if lang != "en_US" and type(trans) == gettext.NullTranslations:
        logger.warn("failed to find translation for %s", lang)

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
