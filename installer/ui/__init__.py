# -*- coding: utf-8 -*-
#

import os
import sys
import locale
import gettext
import logging

from installer import steps


logger = logging.getLogger(__name__)


class UI(object):

    _steps = []
    _keys = {}
    _hotkeys = {}
    _installer = None

    def __init__(self, lang):
        self._current_step = None
        self.language = lang
        self._load_steps()
        steps.finished_signal.connect(self._on_step_finished)
        steps.completion_signal.connect(self._on_step_completion)

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, lang):
        self._language = lang
        locale.setlocale(locale.LC_ALL, lang)

        trans = gettext.translation('installer', languages=[lang], localedir='po')
        #
        # In Python 2, ensure that the _() that gets installed into
        # built-ins always returns unicodes.  This matches the default
        # behavior under Python 3, although that keyword argument is
        # not present in the Python 3 API.
        #
        # http://www.wefearchange.org/2012/06/the-right-way-to-internationalize-your.html
        #
        kwargs = {}
        if sys.version_info[0] < 3:
            kwargs['unicode'] = True
        trans.install(**kwargs)

        self.redraw()

    def run(self):
        raise NotImplementedError()

    def _quit(self):
        for m in self._steps:
            m.reset()
        logger.info(_("exiting..."))

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

    def _select_step(self, step=None):
        if not step:
            step = self._current_step
        self._current_step = step

    def _select_first_step(self):
        self._select_step(self._steps[0])

    def _select_next_step(self):
        for step in self._steps:
            if step.is_enabled() and not step.is_done():
                self._select_step(step)
                return

    def _on_step_completion(self, step, percent):
        """Use to set the level of completion for a step.
        It can be called by any contexts.
        """
        return

    def _on_step_finished(self, step):
        """Notify that a step is terminated.
        It can be called by any contexts,
        """
        return
