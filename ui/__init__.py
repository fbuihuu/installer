# -*- coding: utf-8 -*-
#

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
            self.ui.notify(msg)


class UI(object):

    _menus = []
    _hotkeys = {}
    _installer = None
    current_provides = Set([])

    def __init__(self, installer):
        self.installer = installer
        self._current_menu = None
        self.logs = deque()

        self._logger = logging.getLogger(self.__module__)
        handler = UILogHandler(self)
        formatter = logging.Formatter('[%(asctime)s] %(message)s',' %H:%M:%S')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

        self._load_menus()

    @property
    def logger(self):
        return self._logger

    def run(self):
        raise NotImplementedError()

    def quit(self):
        raise NotImplementedError()

    def suspend(self):
        raise NotImplementedError()

    def redraw(self):
        raise NotImplementedError()

    def notify(self, msg):
        pass

    def register_hotkey(self, hotkey, cb):
        self._hotkeys[hotkey] = cb

    def handle_hotkey(self, key):
        if self._hotkeys.get(key) is not None:
            self._hotkeys[key]()
            return True
        return False

    def _switch_to_menu(self, menu):
        raise NotImplementedError()

    def switch_to_menu(self, menu=None):
        if not menu:
            menu = self._current_menu
        self._current_menu = menu
        self._switch_to_menu(menu)

    def switch_to_first_menu(self):
        self.switch_to_menu(self._menus[0])

    def switch_to_next_menu(self):
        for m in self._menus:
            if m.is_enabled() and not m.is_done():
                self.switch_to_menu(m)
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
                    m.undo()
                else:
                    m.enable()
            else:
                m.disable()
