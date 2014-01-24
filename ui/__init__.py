# -*- coding: utf-8 -*-
#

import os
import locale
import gettext
import logging
from sets import Set
from collections import deque


class UILogHandler(logging.Handler):

    def __init__(self, ui):
        logging.Handler.__init__(self)
        self.ui = ui

    def emit(self, record):
        lvl = record.levelno
        msg = self.format(record)

        self.ui.logs.appendleft((lvl, msg))
        if lvl > logging.DEBUG:
            self.ui.notify(lvl, msg)


class UI(object):

    _menus = []
    _keys = {}
    _hotkeys = {}
    _installer = None
    current_provides = Set([])

    def __init__(self, installer, lang):
        self.installer = installer
        self._current_menu = None
        self.logs = deque()

        self._logger = logging.getLogger(self.__module__)
        handler = UILogHandler(self)
        formatter = logging.Formatter('[%(asctime)s] %(message)s','%H:%M:%S')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

        self.language = lang
        self._load_menus()

    @property
    def logger(self):
        return self._logger

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, lang):
        self._language = lang
        locale.setlocale(locale.LC_ALL, lang)
        # For some reason, python implementation of gettext.install()
        # ignores the previous call to setlocale(). It only uses
        # environment variables.
        os.environ["LANGUAGE"] = lang
        gettext.install('installer', localedir='po', unicode=True)
        self.redraw()
        self.logger.debug(_("switch to english language"))

    def run(self):
        raise NotImplementedError()

    def quit(self, delay=0):
        raise NotImplementedError()

    def suspend(self):
        raise NotImplementedError()

    def redraw(self):
        raise NotImplementedError()

    def notify(self, lvl, msg):
        pass

    def register_hotkey(self, hotkey, cb):
        self._hotkeys[hotkey] = cb

    def register_key(self, key, cb):
        self._keys[key] = cb

    def handle_hotkey(self, key):
        if self._hotkeys.get(key) is not None:
            self._hotkeys[key]()
            return True
        return False

    def handle_key(self, key):
        if self._keys.get(key) is not None:
            self._keys[key]()
            return True
        return False

    def _switch_to_menu(self, menu=None):
        if not menu:
            menu = self._current_menu
        self._current_menu = menu
        self._current_menu.view.redraw()

    def _switch_to_first_menu(self):
        self._switch_to_menu(self._menus[0])

    def _switch_to_next_menu(self):
        for m in self._menus:
            if m.is_enabled() and not m.is_done():
                self._switch_to_menu(m)
                return

    def on_menu_event(self, menu):
        if menu.is_done():
            self.current_provides |= menu.provides
        else:
            self.current_provides -= menu.provides

        for m in self._menus:
            if m is menu:
                continue
            if not menu.provides.issubset(m.requires):
                continue
            if m.requires.issubset(self.current_provides):
                if m.is_enabled():
                    # 'menu' was already in done state but has been
                    # revalidated. In that case menu that depends on
                    # it should be revalidated as well.
                    m.reset()
                else:
                    m.enable()
            else:
                m.disable()

    def on_view_event(self, view):
        for menu in self._menus:
            if menu.view == view:
                menu.process()

    def set_completion(self, percent, view):
        raise NotImplementedError()
