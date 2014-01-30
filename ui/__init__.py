# -*- coding: utf-8 -*-
#

import os
import locale
import gettext
import logging
from collections import deque
import steps


class UILogHandler(logging.Handler):

    def __init__(self, ui):
        logging.Handler.__init__(self)
        self.ui = ui

    def emit(self, record):
        lvl = record.levelno
        msg = self.format(record)

        self.ui.logs.appendleft((lvl, msg))
        if lvl > logging.DEBUG:
            self.ui.notify(lvl, msg.split('\n')[0])


class UI(object):

    _steps = []
    _keys = {}
    _hotkeys = {}
    _installer = None

    def __init__(self, installer, lang):
        self.installer = installer
        self._current_step = None
        self.logs = deque()

        self._logger = logging.getLogger(self.__module__)
        handler = UILogHandler(self)
        formatter = logging.Formatter('[%(asctime)s] %(message)s','%H:%M:%S')
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

        self.language = lang
        self._load_steps()
        steps.finished_signal.connect(self.on_step_finished)
        steps.completion_signal.connect(self.on_step_completion)

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

    def _quit(self):
        for m in self._steps:
            m.reset()
        self.logger.info("exiting...")

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

    def _switch_to_step(self, step=None):
        if not step:
            step = self._current_step
        self._current_step = step

    def _switch_to_first_step(self):
        self._switch_to_step(self._steps[0])

    def _switch_to_next_step(self):
        for step in self._steps:
            if step.is_enabled() and not step.is_done():
                self._switch_to_step(step)
                return

    def on_view_event(self, view):
        for step in self._steps:
            if self._step_views[step] == view:
                step.process()

    def on_step_completion(self, step, percent):
        """Use to set the level of completion for a step.
        It can be called by any contexts.
        """
        return

    def on_step_finished(self, step):
        """Notify that a step is terminated.
        It can be called by any contexts,
        """
        return
