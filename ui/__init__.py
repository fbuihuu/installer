# -*- coding: utf-8 -*-
#

import logging


class AbstractUI(object):

    _menus = []
    _current_menu = None
    _hotkeys = {}

    def __init__(self):
        self._logger = logging.getLogger(self.__module__)

    @property
    def logger(self):
        return self._logger

    def run(self):
        raise NotImplementedError()

    def quit(self):
        raise NotImplementedError()

    def redraw(self):
        raise NotImplementedError()

    def register_hotkey(self, hotkey, cb):
        self._hotkeys[hotkey] = cb

    def switch_to_menu(self, menu):
        raise NotImplementedError()


class AbstractMenu(object):

    def __init__(self, title):
        self._title = _(title)

    @property
    def name(self):
        return self._title

    def ui_content(self):
        raise NotImplementedError()
