# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import os
import re
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
    try:
        with open(filename, 'r') as f:
            for line in f:
                line = line.partition('#')[0]
                line = line.strip()
                if line:
                    if not ':' in line:
                        line = '1:' + line
                    level, package = line.split(':', 1)
                    if int(level) >= settings.Options.level:
                        lst.append(package)
    except IOError:
        raise SettingsError(_('Failed to read package list: %s' % filename))
    return lst

#
#
#
class Section(object):

    def __init__(self, name=None):
        self.name = name if name else self.__class__.__name__

    def _is_enabled(self):
        return True

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

#
# This describes a section used to configure a specific step. Thus the
# section can be disabled if the step is skipped. This avoids to parse
# a section in an inconsistent state which is acceptable if the step is
# disabled.
#
class StepSection(Section):

    def _is_enabled(self):
        return settings.get('Steps', self.name)

#
# Step sections
#
class End(StepSection):
    _action = 'quit'

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, a):
        if not a in ('quit', 'reboot', 'shutdown'):
            raise SettingsError("Invalid value '%s' for End.action" % a)
        self._action = a


class Installation(StepSection):
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
        for f in pkgfiles:
            # absolute_path() doesn't do any sanity checkings on 'f'
            self._pkgfiles.append(absolute_path(f))


class License(StepSection):
    dir = ''


#
# The current language is used as a hint to find out the default l10n
# values. If the user provided some values then they will be used.
#
class Localization(StepSection):
    _timezone = ''
    _keymap   = ''
    _locale   = ''

    @property
    def timezone(self):
        return self._timezone or l10n.get_language_zone().timezone

    @property
    def keymap(self):
        return self._keymap or l10n.get_language_zone().keymap

    @property
    def locale(self):
        return self._locale or l10n.get_language_zone().locale

    @timezone.setter
    def timezone(self, tz):
        self._timezone = tz

    @keymap.setter
    def keymap(self, kmap):
        self._keymap = kmap

    @locale.setter
    def locale(self, locale):
        self._locale = locale


#
# Other sections.
#
class Kernel(Section):
    cmdline  = 'rw quiet'


class Options(Section):
    level    = 1
    profile  = 'default'
    logfile  = '/var/log/installer/installer.log'
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


class Steps(Section):
    Language     = True
    License      = True
    Disk         = True
    Installation = True
    Localization = True
    Password     = True
    End          = True


class Urpmi(Section):
    options  = ''


class Urwid(Section):
    colors = 16


class _Settings(object):

    def __init__(self):
        self._sections = {
            'End'              : End(),
            'Localization'     : Localization(),
            'Installation'     : Installation(),
            'Kernel'           : Kernel(),
            'License'          : License(),
            'Options'          : Options(),
            'Steps'            : Steps(),
            'Urpmi'            : Urpmi(),
            'Urwid'            : Urwid(),
        }

    @property
    def sections(self):
        return [s for s in self._sections.values() if s.entries and s._is_enabled()]

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
    config.optionxform = str # make it case-sensitive
    config.readfp(fp)

    for section in config.sections():
        for entry in config.options(section):

            default = settings.get(section, entry)
            if type(default) == int:
                value = config.getint(section, entry)
            elif type(default) == bool:
                value = config.getboolean(section, entry)
            elif type(default) == float:
                value = config.getfloat(section, entry)
            else:
                # Use unicode for string values on python2.7.
                value = '%s' % config.get(section, entry)
                if type(default) == list:
                    value = value.split()

            settings.set(section, entry, value)


def absolute_path(f):
    """Helper to convert a relative path into an absolute
    one. Relative paths are relative to the directory containing the
    config file. It doesn't do any sanity checkings on the file.
    """
    return os.path.join(os.path.dirname(settings.Options.config), f)


settings = _Settings()
