# -*- coding: utf-8 -*-
#


try:
    from configparser import ConfigParser # py3k
except ImportError:
    from ConfigParser import ConfigParser


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

class Steps(Section):
    _default = True


class _Settings(object):

    def __init__(self):
        self._sections = {
            'I18n'       : I18n(),
            'Kernel'     : Kernel(),
            'Steps'      : Steps(),
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
            del self._section[section]


def load_config_file(config_file):
    config = ConfigParser()
    config.read(config_file)

    for section in config.sections():
        for entry, value in config.items(section):
            settings.set(section, entry, value)


settings = _Settings()
