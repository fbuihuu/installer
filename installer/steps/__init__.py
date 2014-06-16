# -*- coding: utf-8 -*-
#

import os
import logging
from threading import current_thread, Thread, RLock
from installer.utils import Signal
from installer.process import monitor, monitor_chroot
from installer.partition import mount_rootfs, unmount_rootfs
from installer.settings import settings, SettingsError


class StepError(Exception):
    """Base class for exceptions thrown by steps."""


_all_steps = []

def get_steps():
    return [ s for s in _all_steps if not s._skip]


_current_provides = set([])
_rlock = RLock()

def _recalculate_step_dependencies(step):
    global _all_steps, _current_provides, _rlock

    if step.provides:
        with _rlock:
            if step.is_done():
                _current_provides |= step.provides
            else:
                _current_provides -= step.provides

            for m in _all_steps:
                if m is step:
                    continue
                if not step.provides.intersection(m.requires):
                    continue
                if m.requires.issubset(_current_provides):
                    if m.is_enabled():
                        # 'step' was already in done state but has been
                        # revalidated. In that case step that depends on
                        # it should be revalidated as well.
                        m.reset()
                    else:
                        m.enable()
                else:
                    m.disable()


finished_signal = Signal()
completion_signal = Signal()


class Step(object):

    requires = []
    provides = []

    _STATE_DISABLED    = -1
    _STATE_INIT        = 0
    _STATE_IN_PROGRESS = 1
    _STATE_DONE        = 2
    _STATE_FAILED      = 3
    _STATE_CANCELLED   = 4

    def __init__(self):
        self._skip = False
        self._exit = False # system wide exit
        self._root = None
        self._exit_delay = 0
        self._thread = None
        self.requires = set(self.requires)
        self.provides = set(self.provides)
        self._completion = 0
        self.view_data = None # should be used by step's view only
        self.__state = self._STATE_DISABLED

    @property
    def name(self):
        raise NotImplementedError()

    @property
    def logger(self):
        return logging.getLogger(self.name)

    @property
    def _state(self):
        return self.__state

    @_state.setter
    def _state(self, state):
        self.__state = state
        _recalculate_step_dependencies(self)

    def __cancel(self):
        #
        # This can be called by the UI thread, when a step is
        # restarted (through the process() method) and all it's
        # running deps are disabled (hence cancelled).
        #
        # But a step is never cancelled by its worker thread.
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
        quit = False
        delay = 0
        self._root = mount_rootfs()

        try:
            self._process()
        except StepError as e:
            self._failed("%s" % e)
        except:
            if not self.__is_cancelled():
                self._failed(_("failed, see logs for details."), True)
        else:
            if self.__is_in_progress():
                self._done()

        try:
            self._root = unmount_rootfs()
        except:
            self.logger.error("failed to umount %s", self._root)

        finished_signal.emit(self, self._exit, self._exit_delay)

    def process(self):
        assert(not self.__is_in_progress())
        self._thread = Thread(target=self.__process)
        self._state = self._STATE_IN_PROGRESS
        self._thread.start()

    def enable(self):
        if self._skip:
            self._state = self._STATE_DONE
        elif self.is_disabled():
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
        """Used by step thread to indicate it has finished successfully"""
        if not msg:
            msg = _("done.")
        self.logger.info(msg)
        self.set_completion(100)
        self._state = self._STATE_DONE

    def _failed(self, msg=None, backtrace=False):
        """Used by step thread to indicate it has failed"""
        if not msg:
            msg = _("failed.")
        if backtrace:
            self.logger.exception(msg)
        else:
            self.logger.error(msg)
        self.set_completion(0)
        self._state = self._STATE_FAILED

    def _process(self):
        """Implement the actual work executed asynchronously"""
        raise NotImplementedError()

    def _cancel(self):
        """Notify the thread it should terminate as soon as possible"""
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
        if percent != self._completion:
            self._completion = percent
            completion_signal.emit(self, percent)

    def _monitor(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor(args, **kwargs)

    def _chroot(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor_chroot(self._root, args, **kwargs)

    def _chroot_cp(self, src, overwrite=True):
        """Copy a file from the host into the chroot using the same
        path. 'src' must be an absolute path.
        """
        assert(src[0] == "/")
        dst = os.path.join(self._root, '.' + src)
        if not os.path.exists(dst) or overwrite:
            self.logger.info("importing from host: %s", src)
            self._monitor(["cp", src, dst])

#
# Step instantiations requires working translation.
#
from .language import LanguageStep
from .license import LicenseStep
from .partitioning import PartitioningStep
from .installation import InstallStep
from .localization import LocalizationStep
from .password import PasswordStep
from .end import EndStep

def _initialize_one_step(step, no_skip):
    step._skip = not no_skip
    _all_steps.append(step)

def initialize():
    if not settings.Steps.installation:
        raise SettingsError(_("installation step can't be disabled !"))

    _initialize_one_step(LanguageStep(), settings.Steps.language)
    _initialize_one_step(LicenseStep(), settings.Steps.license)
    _initialize_one_step(PartitioningStep(), settings.Steps.partitioning)
    _initialize_one_step(InstallStep(), True)
    _initialize_one_step(LocalizationStep(), settings.Steps.localization)
    _initialize_one_step(PasswordStep(), settings.Steps.password)
    _initialize_one_step(EndStep(), settings.Steps.end)

    assert(get_steps())
    assert(not _all_steps[0].requires)
    _all_steps[0].enable()
