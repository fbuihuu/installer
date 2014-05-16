# -*- coding: utf-8 -*-
#

import os
import logging

from installer import steps, l10n
from installer.steps.language import LanguageStep
from installer.steps.license import LicenseStep
from installer.steps.partitioning import PartitioningStep
from installer.steps.installation import InstallStep
from installer.steps.password import PasswordStep
from installer.steps.exit import ExitStep


logger = logging.getLogger(__name__)


class UI(object):

    _steps = []
    _keys = {}
    _hotkeys = {}

    def __init__(self, lang):
        self._current_step = None
        self._language = None
        self.language = lang

        # This requires working translation.
        self._steps.append(LanguageStep(self))
        self._steps.append(LicenseStep(self))
        self._steps.append(PartitioningStep(self))
        self._steps.append(InstallStep(self))
        self._steps.append(PasswordStep(self))
        self._steps.append(ExitStep(self))

        steps.finished_signal.connect(self._on_step_finished)
        steps.completion_signal.connect(self._on_step_completion)

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, lang):
        self._language = lang
        l10n.set_locale(lang)
        l10n.set_translation(lang)
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
        for step in self._steps[self._steps.index(self._current_step):]:
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