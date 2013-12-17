# -*- coding: utf-8 -*-
#

from sets import Set
import logging


class AbstractUI(object):

    _menus = []
    _hotkeys = {}
    _installer = None
    current_provides = Set([])

    def __init__(self, installer):
        self._logger = logging.getLogger(self.__module__)
        self.installer = installer
        self._current_menu = None
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

    def register_hotkey(self, hotkey, cb):
        self._hotkeys[hotkey] = cb

    def _switch_to_menu(self, menu):
        raise NotImplementedError()

    def switch_to_menu(self, menu):
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
