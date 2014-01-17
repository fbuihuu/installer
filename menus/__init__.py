# -*- coding: utf-8 -*-
#

from sets import Set
import logging


class MenuLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '%s: %s' % (self.extra['title'], msg), kwargs


class BaseMenu(object):

    _STATE_DISABLED = -2
    _STATE_FAILED = -1
    _STATE_INIT   = 0
    _STATE_DONE   = 1

    requires = []
    provides = []

    def __init__(self, ui, callback):
        self.ui = ui
        self.installer = ui.installer
        self._callback = callback
        self._logger = MenuLogAdapter(ui.logger, {'title': self.name})
        self.requires = Set(self.requires)
        self.provides = Set(self.provides)

        if len(self.requires) == 0:
            self._state = self._STATE_INIT
        else:
            self._state = self._STATE_DISABLED

    @property
    def name(self):
        raise NotImplementedError()

    @property
    def logger(self):
        return self._logger

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state
        if self._callback:
            self._callback(self)

    def redraw(self):
        pass

    def enable(self):
        if self.state == self._STATE_DISABLED:
            self.state = self._STATE_INIT

    def undo(self):
        if self.state == self._STATE_DONE or self.state == self._STATE_FAILED:
            self.state = self._STATE_INIT

    def disable(self):
        if len(self.requires) == 0:
            return
        if self.state != self._STATE_DISABLED:
            self.state = self._STATE_DISABLED

    def is_enabled(self):
        return self.state != self._STATE_DISABLED

    def is_done(self):
        return self.state == self._STATE_DONE

    def is_failed(self):
        return self.state == self._STATE_FAILED

    def process(self):
        raise NotImplementedError()
