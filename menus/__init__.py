# -*- coding: utf-8 -*-
#

from sets import Set
import logging
from threading import current_thread, Thread


class MenuLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '%s: %s' % (self.extra['title'], msg), kwargs


class BaseMenu(object):

    __STATE_DISABLED    = -1
    __STATE_INIT        = 0
    __STATE_IN_PROGRESS = 1 # FIXME: maybe useless, try "thread.is_alive()"
    __STATE_DONE        = 2
    __STATE_FAILED      = 3
    __STATE_CANCELLED   = 4

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
            self._state = self.__STATE_INIT
        else:
            self._state = self.__STATE_DISABLED

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
    def state(self):
        return self._state

    @state.setter
    def state(self, state):
        self._state = state
        self._ui.on_menu_event(self)

    def __cancel(self):
        assert(current_thread() != self._thread)
        if self.__is_in_progress():
            self._state = self.__STATE_CANCELLED
            self._cancel()
            self._thread.join()
            self.set_completion(0)
            # Don't trigger an event for that, the caller will.
            self._state = self.__STATE_FAILED

    def __process(self):
        try:
            self._process()
        except:
            if self.__is_cancelled():
                self.logger.info("aborted.")
            else:
                self.logger.exception("failed, see logs for details.")
                self.set_completion(0)
                self.state = self.__STATE_FAILED

    def enable(self):
        if self.state == self.__STATE_DISABLED:
            self.state = self.__STATE_INIT

    def disable(self):
        if len(self.requires):
            if self.__is_in_progress():
                self.__cancel()
            if self.state != self.__STATE_DISABLED:
                self.state = self.__STATE_DISABLED

    def reset(self):
        if self.__is_in_progress():
            self.__cancel()
        if self.state == self.__STATE_DONE or self.state == self.__STATE_FAILED:
            self.state = self.__STATE_INIT

    def process(self):
        assert(not self.__is_in_progress())
        self._thread = Thread(target=self.__process)
        self._state = self.__STATE_IN_PROGRESS
        self._thread.start()

    def _done(self):
        """Used by menu thread to indicate it has finished successfully"""
        self.logger.info("done.")
        self.set_completion(100)
        self.state = self.__STATE_DONE

    def _failed(self):
        """Used by menu thread to indicate it has failed"""
        self.logger.error("failed.")
        self.set_completion(0)
        self.state = self.__STATE_FAILED

    def _process(self):
        """Implement the actual work executed asynchronously"""
        raise NotImplementedError()

    def _cancel(self):
        """Notify the thread it should terminate as soon as possible"""
        raise NotImplementedError()

    def _cancel(self):
        raise NotImplementedError()

    def is_enabled(self):
        return self.state != self.__STATE_DISABLED

    def is_done(self):
        return self.state == self.__STATE_DONE

    def is_failed(self):
        return self.state == self.__STATE_FAILED

    def __is_in_progress(self):
        return self.state == self.__STATE_IN_PROGRESS

    def __is_cancelled(self):
        return self.state == self.__STATE_CANCELLED

    def set_completion(self, percent):
        self._ui.set_completion(percent, self.view)
