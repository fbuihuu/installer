# -*- coding: utf-8 -*-
#

from sets import Set
import logging
from threading import current_thread, Thread


class MenuLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '%s: %s' % (self.extra['title'], msg), kwargs


class BaseMenu(object):

    _STATE_DISABLED    = -1
    _STATE_INIT        = 0
    _STATE_IN_PROGRESS = 1
    _STATE_DONE        = 2
    _STATE_FAILED      = 3
    _STATE_CANCELLED   = 4

    requires = []
    provides = []

    def __init__(self, ui, view):
        self._ui = ui
        self._view  = view
        self._thread = None
        self._logger = MenuLogAdapter(ui.logger, {'title': self.name})
        self.requires = Set(self.requires)
        self.provides = Set(self.provides)

        if len(self.requires) == 0:
            self.__state = self._STATE_INIT
        else:
            self.__state = self._STATE_DISABLED

    @property
    def view(self):
        return self._view

    @property
    def name(self):
        raise NotImplementedError()

    @property
    def logger(self):
        return self._logger

    @property
    def _state(self):
        return self.__state

    @_state.setter
    def _state(self, state):
        self.__state = state
        self._ui.on_menu_event(self)

    def __cancel(self):
        assert(current_thread() != self._thread)
        if self.__is_in_progress():
            self._state = self._STATE_CANCELLED
            self._cancel()
            self._thread.join()
            self.set_completion(0)
            self.logger.info("aborted.")
            # Don't trigger an event for that, the caller will.
            self._state = self._STATE_FAILED

    def __process(self):
        try:
            self._process()
        except:
            if not self.__is_cancelled():
                self.logger.exception("failed, see logs for details.")
                self.set_completion(0)
                self._state = self._STATE_FAILED

    def enable(self):
        if self.is_disabled():
            self._state = self._STATE_INIT

    def disable(self):
        if len(self.requires):
            if self.is_enabled():
                if self.__is_in_progress():
                    self.__cancel()
                self._state = self._STATE_DISABLED

    def reset(self):
        if self.__is_in_progress():
            self.__cancel()
        if self.is_done() or self.is_failed():
            self._state = self._STATE_INIT

    def process(self):
        assert(not self.__is_in_progress())
        self._thread = Thread(target=self.__process)
        self._state = self._STATE_IN_PROGRESS
        self._thread.start()

    def _done(self):
        """Used by menu thread to indicate it has finished successfully"""
        self.logger.info("done.")
        self.set_completion(100)
        self._state = self._STATE_DONE

    def _failed(self):
        """Used by menu thread to indicate it has failed"""
        self.logger.error("failed.")
        self.set_completion(0)
        self._state = self._STATE_FAILED

    def _process(self):
        """Implement the actual work executed asynchronously"""
        raise NotImplementedError()

    def _cancel(self):
        """Notify the thread it should terminate as soon as possible"""
        raise NotImplementedError()

    def _cancel(self):
        raise NotImplementedError()

    def is_enabled(self):
        return self._state != self._STATE_DISABLED

    def is_disabled(self):
        return self._state == self._STATE_DISABLED

    def is_done(self):
        return self._state == self._STATE_DONE

    def is_failed(self):
        return self._state == self._STATE_FAILED

    def __is_in_progress(self):
        return self._state == self._STATE_IN_PROGRESS

    def __is_cancelled(self):
        return self._state == self._STATE_CANCELLED

    def set_completion(self, percent):
        self._ui.set_completion(percent, self.view)
