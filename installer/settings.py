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
        return "unknown section '%s'" % self.section


class AttributeSettingsError(SettingsError, AttributeError):
    """Exception thrown when a section doesn't define a setting."""

    def __init__(self, section, attr):
        self.section = section
        self.attr    = attr

    def __str__(self):
        return "missing attribute '%s' in section '%s'" % (self.attr, self. section)


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


class I18n(Section):
    country  = ''
    timezone = ''
    keymap   = ''
    locale   = ''

    def __init__(self):
        Section.__init__(self)
        lang, enc = locale.getdefaultlocale()

        found = None
        for ccode, zones in l10n.country_zones.items():
            for zi in zones:
                if lang == zi.locale:
                    found = (ccode, zi)
                    break
                if not found and zi.locale.startswith(lang.split('_')[0]):
                    found = (ccode, zi)
            if lang == zi.locale:
                break
        if not found:
            found = ('US', l10n.country_zones['US'][0])

        I18n.country  = found[0]
        I18n.timezone = found[1].timezone
        I18n.keymap   = found[1].keymap
        I18n.locale   = found[1].locale


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


class Packages(Section):
    _extras = []

    @property
    def extras(self):
        return self._extras

    @extras.setter
    def extras(self, pkgfiles):
        #
        # Relative path is relative to the directory
        # containing the config file.
        #
        for f in pkgfiles:
            f = os.path.join(os.path.dirname(settings.Options.config), f)
            if not os.path.exists(f):
                raise SettingsError("Can't find package list file %s" % f)
            self._extras.append(f)


class Steps(Section):
    language = True
    license  = True
    partitioning = True
    installation = True
    localization = True
    password = True
    end = True


class Urpmi(Section):
    options  = ''
    use_host_config = True


class _Settings(object):

    def __init__(self):
        self._sections = {
            'I18n'       : I18n(),
            'Kernel'     : Kernel(),
            'License'    : License(),
            'Options'    : Options(),
            'Packages'   : Packages(),
            'Steps'      : Steps(),
            'Urpmi'      : Urpmi(),
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


settings = _Settings()
