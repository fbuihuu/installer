# -*- coding: utf-8 -*-
#

import os
from installer.system import is_efi


try:
    from configparser import ConfigParser # py3k
except ImportError:
    from ConfigParser import ConfigParser


class SettingsError(Exception):
    """Base class for exceptions for the settings module."""


class Section(object):
    _default = None

    def __init__(self, name=None):
        self._name = name

    @property
    def name(self):
        if self._name:
            return self._name
        return self.__class__.__name__

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
        """Return 'self._default' for unset section entries"""
        try:
            return object.__getattr__(self, attr)
        except AttributeError:
            return self._default


class I18n(Section):
    country  = 'France'
    timezone = 'Europe/Paris'
    keymap   = 'fr'
    locale   = 'fr_FR'


class Kernel(Section):
    cmdline  = 'rw quiet'


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
            f = os.path.join(os.path.dirname(configuration_file), f)
            if not os.path.exists(f):
                raise SettingsError("Can't find package list file %s" % f)
            self._extras.append(f)


class Steps(Section):
    _default = True


class Urpmi(Section):
    options  = ''


class _Settings(object):

    def __init__(self):
        self._sections = {
            'I18n'       : I18n(),
            'Kernel'     : Kernel(),
            'Options'    : Options(),
            'Packages'   : Packages(),
            'Steps'      : Steps(),
            'Urpmi'      : Urpmi(),
        }

    @property
    def sections(self):
        return [s for s in self._sections.values() if s.entries]

    def __getattr__(self, attr):
        if attr not in self._sections:
            self._sections[attr] = Section(name=attr)
        return self._sections[attr]

    def get(self, section, attribute):
        return getattr(getattr(self, section), attribute)

    def set(self, section, attribute, value):
        return setattr(getattr(self, section), attribute, value)

    def remove(self, section, attribute):
        delattr(getattr(self, section), attribute)
        if not getattr(self, section).entries:
            del self._sections[section]


configuration_file = None

def load_config_file(config_file):
    global configuration_file

    configuration_file = os.path.realpath(config_file)
    config = ConfigParser()
    config.read(configuration_file)

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
