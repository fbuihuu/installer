# -*- coding: utf-8 -*-
#

from sets import Set
import logging
from threading import current_thread, Thread, RLock


_all_menus = []
_current_provides = Set([])
_rlock = RLock()

def _recalculate_menu_dependencies(menu):
    global _all_menus, _current_provides, _rlock

    with _rlock:
        if menu.is_done():
            _current_provides |= menu.provides
        else:
            _current_provides -= menu.provides

        for m in _all_menus:
            if m is menu:
                continue
            if not menu.provides.issubset(m.requires):
                continue
            if m.requires.issubset(_current_provides):
                if m.is_enabled():
                    # 'menu' was already in done state but has been
                    # revalidated. In that case menu that depends on
                    # it should be revalidated as well.
                    m.reset()
                else:
                    m.enable()
            else:
                m.disable()


class MenuLogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return '%s: %s' % (self.extra['title'], msg), kwargs


class BaseMenu(object):

    requires = []
    provides = []

    _STATE_DISABLED    = -1
    _STATE_INIT        = 0
    _STATE_IN_PROGRESS = 1
    _STATE_DONE        = 2
    _STATE_FAILED      = 3
    _STATE_CANCELLED   = 4

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

        _all_menus.append(self)

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
        _recalculate_menu_dependencies(self)

    def __cancel(self):
        #
        # This can be called by the UI thread, when a menu is
        # restarted (through the process() method) and all it's
        # running deps are disabled (hence cancelled).
        #
        # But a menu is never cancelled by its worker thread.
        #
        assert(current_thread() != self._thread)

        if self.__is_in_progress():
            self._state = self._STATE_CANCELLED
            self._cancel()
            self._thread.join()
            self.logger.info("aborted.")
            self.set_completion(0)
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

    def process(self):
        assert(not self.__is_in_progress())
        self._thread = Thread(target=self.__process)
        self._state = self._STATE_IN_PROGRESS
        self._thread.start()

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

    def _done(self, msg=None):
        """Used by menu thread to indicate it has finished successfully"""
        if not msg:
            msg = _("done.")
        self.logger.info(msg)
        self.set_completion(100)
        self._state = self._STATE_DONE
        self._ui.redraw()

    def _failed(self, msg=None):
        """Used by menu thread to indicate it has failed"""
        if not msg:
            msg = _("failed.")
        self.logger.error(msg)
        self.set_completion(0)
        self._state = self._STATE_FAILED
        self._ui.redraw()

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
