# -*- coding: utf-8 -*-
#

import os
import locale

from installer.system import is_efi
from installer import l10n


try:
    from configparser import ConfigParser # py3k
except ImportError:
    from ConfigParser import ConfigParser


class SettingsError(Exception):
    """Base class for exceptions for the settings module."""


class SectionSettingsError(SettingsError, AttributeError):
    """Exception thrown when trying to access to an unset/undefined section."""

    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "missing section '%s'" % self.section


class AttributeSettingsError(SettingsError, AttributeError):
    """Exception thrown when a section doesn't define a setting."""

    def __init__(self, section, attr):
        self.section = section
        self.attr    = attr

    def __str__(self):
        return "missing option '%s' in section '%s'" % (self.attr, self. section)

#
# Helpers
#
def read_package_list(filename):
    """Read a package list given by a file"""
    lst = []
    with open(filename, 'r') as f:
        for line in f:
            line = line.partition('#')[0]
            line = line.strip()
            if line:
                lst.append(line)
    return lst

#
#
#
class Section(object):

    def __init__(self, name=None):
        self.name = name if name else self.__class__.__name__

    @property
    def entries(self):
        lst = []
        for attr in dir(self):
            if attr.startswith('_'):
                continue
            if attr in ('name', 'entries'):
                continue
            lst.append(attr)
        return lst

    def __getattr__(self, attr):
        raise AttributeSettingsError(self.name, attr)


class End(Section):
    _action = 'quit'

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, a):
        if not a in ('quit', 'reboot', 'shutdown'):
            raise SettingsError("Invalid value '%s' for End.action" % a)
        self._action = a


class I18n(Section):
    _country  = ''
    _timezone = ''
    _keymap   = ''
    _locale  = ''

    def __init__(self):
        Section.__init__(self)
        # used to keep track of the options overriden by the user explicitely.
        self._explicit_settings = set()

        # Try to find out the default settings for I18n based on the
        # default locale.
        default = locale.getdefaultlocale()[0]
        if default in (None, 'C'):
            default = 'en_US'
        self.locale = default

    @property
    def country(self):
        return self._country

    @property
    def timezone(self):
        return self._timezone

    @property
    def keymap(self):
        return self._keymap

    @property
    def locale(self):
        return self._locale

    @country.setter
    def country(self, country):
        self._explicit_settings.add('country')
        self._country = country

    @timezone.setter
    def timezone(self, tz):
        self._explicit_settings.add('timezone')
        self._timezone = tz

    @keymap.setter
    def keymap(self, kmap):
        self._explicit_settings.add('keymap')
        self._keymap = kmap

    @locale.setter
    def locale(self, locale):
        found = None
        for ccode, zones in l10n.country_zones.items():
            for zi in zones:
                if locale == zi.locale:
                    found = (ccode, zi)
                    break
                if found:
                    # Try to find an exact match only.
                    continue
                if zi.locale.split('_')[0] == locale.split('_')[0]:
                    found = (ccode, zi)
            if locale == zi.locale:
                break
        if not found:
            found = ('US', l10n.country_zones['US'][0])

        self._locale = found[1].locale
        # don't change values previously customized by the user.
        if not 'country' in self._explicit_settings:
            self._country = found[0]
        if not 'timezone' in self._explicit_settings:
            self._timezone = found[1].timezone
        if not 'keymap' in self._explicit_settings:
            self._keymap = found[1].keymap


class Kernel(Section):
    cmdline  = 'rw quiet'


class License(Section):
    dir = ''


class Options(Section):
    logfile  = '/tmp/installer.log'
    hostonly = True
    _firmware = []

    @property
    def firmware(self):
        if self._firmware:
            return self._firmware
        return ['uefi' if is_efi() else 'bios']

    @firmware.setter
    def firmware(self, fw):
        self._firmware = fw


class Installation(Section):
    repositories = []
    _pkgfiles = []

    @property
    def packages(self):
        # Read the files lately so the user can modify them without
        # restarting the installer.
        lst = []
        for f in self._pkgfiles:
            lst += read_package_list(f)
        return lst

    @packages.setter
    def packages(self, pkgfiles):
        #
        # Relative path is relative to the directory
        # containing the config file.
        #
        for f in pkgfiles:
            self._pkgfiles.append(check_file(f))


class LocalMedia(Section):
    _pkgfiles = []

    @property
    def packages(self):
        # Read the files lately so the user can modify them without
        # restarting the installer.
        lst = []
        for f in self._pkgfiles:
            lst += read_package_list(f)
        return lst

    @packages.setter
    def packages(self, pkgfiles):
        #
        # Relative path is relative to the directory
        # containing the config file.
        #
        for f in pkgfiles:
            self._pkgfiles.append(check_file(f))


class Steps(Section):
    language     = True
    license      = True
    partitioning = True
    installation = True
    local_media  = False
    localization = True
    password     = True
    end          = True


class Urpmi(Section):
    options  = ''


class Urwid(Section):
    colors = 16


class _Settings(object):

    def __init__(self):
        self._sections = {
            'End'              : End(),
            'I18n'             : I18n(),
            'Installation'     : Installation(),
            'Kernel'           : Kernel(),
            'License'          : License(),
            'LocalMedia'       : LocalMedia(),
            'Options'          : Options(),
            'Steps'            : Steps(),
            'Urpmi'            : Urpmi(),
            'Urwid'            : Urwid(),
        }

    @property
    def sections(self):
        return [s for s in self._sections.values() if s.entries]

    def __getattr__(self, section):
        try:
            return self._sections[section]
        except KeyError:
            raise SectionSettingsError(section)

    def get(self, section, attribute):
        """If the section or attribute is undefined returns None."""
        try:
            return getattr(getattr(self, section), attribute)
        except (SectionSettingsError, AttributeSettingsError) as e:
            return None

    def set(self, section, attribute, value):
        """If the section or attribute is undefined, create it."""
        if not section in self._sections:
            self._sections[section] = Section(section)
        return setattr(getattr(self, section), attribute, value)

    def remove(self, section, attribute):
        delattr(getattr(self, section), attribute)
        if not getattr(self, section).entries:
            del self._sections[section]


def load_config_file(fp):
    # Register the config file path in the global settings.
    settings.set('Options', 'config', os.path.abspath(fp.name))

    config = ConfigParser()
    config.readfp(fp)

    for section in config.sections():
        for entry in config.options(section):

            default = settings.get(section, entry)
            if type(default) == int:
                getter = config.getint
            elif type(default) == bool:
                getter = config.getboolean
            elif type(default) == float:
                getter = config.getfloat
            else:
                getter = config.get

            value = getter(section, entry)

            if type(default) == list:
                value = value.split(',')

            settings.set(section, entry, value)


def check_file(f):
    """Helper to do basic sanity checks on files specified in the
    config file.
    """
    f = os.path.join(os.path.dirname(settings.Options.config), f)
    if not os.path.exists(f):
        raise SettingsError("Can't find file %s" % f)
    return f


settings = _Settings()
