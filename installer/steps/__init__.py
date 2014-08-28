# -*- coding: utf-8 -*-
#

import os
import logging
from threading import current_thread, Thread, RLock
from installer import distro
from installer.utils import Signal, rsync
from installer.process import monitor, monitor_chroot, kill_current
from installer.partition import mount_rootfs, unmount_rootfs
from installer.settings import settings, SettingsError


_STATE_DISABLED    = -1
_STATE_INIT        = 0
_STATE_IN_PROGRESS = 1
_STATE_DONE        = 2
_STATE_FAILED      = 3
_STATE_CANCELLED   = 4


class StepError(Exception):
    """Base class for exceptions thrown by steps."""


_all_steps = []

def get_steps():
    return [ s for s in _all_steps if not s._skip]


_current_provides = set([])
_rlock = RLock()

def _recalculate_step_dependencies(step):
    global _all_steps, _current_provides, _rlock

    assert(not step.is_in_progress())
    if step.provides:
        with _rlock:
            if step.is_done():
                _current_provides |= step.provides
            else:
                _current_provides -= step.provides

            for s in _all_steps:
                if s is step:
                    continue
                if not step.provides.intersection(s.requires):
                    continue
                if s.requires.issubset(_current_provides):
                    if s.is_enabled():
                        # 'step' was already in done state but has been
                        # revalidated. In that case steps that depend on
                        # it should be revalidated as well.
                        if s.is_done() or s.is_failed():
                            s._state = _STATE_INIT
                        _recalculate_step_dependencies(s)
                    else:
                        s._state = _STATE_INIT
                        if s._skip:
                            _recalculate_step_dependencies(s)
                else:
                    assert(not s.is_in_progress())
                    s._state = _STATE_DISABLED
                    _recalculate_step_dependencies(s)


finished_signal = Signal()
completion_signal = Signal()


class Step(object):

    requires = []
    provides = []
    mandatory = False

    def __init__(self):
        self._skip = not settings.get('Steps', self.name.lower())
        self._root = None
        self._thread = None
        self.requires = set(self.requires)
        self.provides = set(self.provides)
        self._completion = 0
        self.view_data = None # should be used by step's view only
        self.__state = _STATE_DISABLED

        if self._skip and self.mandatory:
            raise SettingsError(_("step '%s' can't be disabled !" % self.name))

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
        if self._skip and self.is_enabled():
            self.__state = _STATE_DONE

    def __cancel(self):
        #
        # This can be called by the UI thread, when a step is
        # restarted (through the process() method) and all it's
        # running deps are disabled (hence cancelled).
        #
        # But a step is never cancelled by its worker thread.
        #
        assert(current_thread() != self._thread)

        self.logger.info("aborting...")
        self._state = _STATE_CANCELLED
        kill_current(logger=self.logger)
        self._thread.join()
        self.logger.info("aborted.")

    def __process(self, *args):
        self.logger.info("processing...")

        #
        # Mount rootfs only if the step needs it. Also mount it in the
        # case the step is going to initialize it.
        #
        if 'rootfs' in self.requires or 'rootfs' in self.provides:
            self._root = mount_rootfs()
            assert(self._root)

        try:
            self._process(*args)
        except (StepError, SettingsError) as e:
            self.logger.error(e)
        except:
            if not self.__is_cancelled():
                self.logger.exception(_('failed, see logs for details.'))
        else:
            if self.is_in_progress():
                self.set_completion(100)
                self._state = _STATE_DONE
                self.logger.info(_('done.'))

        if not self.is_done():
            self.set_completion(0)
            self._state = _STATE_FAILED

        if self._root:
            unmount_rootfs()
            self._root = None

        _recalculate_step_dependencies(self)
        finished_signal.emit(self)

    def process_async(self, *args):
        assert(not self.is_in_progress())
        self._thread = Thread(target=self.__process, args=args)
        self._thread.start()
        self._state = _STATE_IN_PROGRESS

    def process(self, *args):
        # The synchronous version is still using a thread because
        # cancel() is synchronous too: it needs to wait for __process()
        # to finish before returning.
        self.process_async(*args)
        self._thread.join()

    def cancel(self):
        if self.is_in_progress():
            self.__cancel()

    def _process(self):
        """Implement the actual work executed asynchronously"""
        raise NotImplementedError()

    def is_enabled(self):
        return self._state != _STATE_DISABLED

    def is_disabled(self):
        return self._state == _STATE_DISABLED

    def is_done(self):
        return self._state == _STATE_DONE

    def is_failed(self):
        return self._state == _STATE_FAILED

    def is_in_progress(self):
        return self._state == _STATE_IN_PROGRESS

    def __is_cancelled(self):
        return self._state == _STATE_CANCELLED

    def set_completion(self, percent):
        if percent != self._completion:
            self._completion = percent
            completion_signal.emit(self, percent)

    def _monitor(self, args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        monitor(args, **kwargs)

    def _rsync(self, *args, **kwargs):
        if "logger" not in kwargs:
            kwargs["logger"] = self.logger
        rsync(*args, set_completion=self.set_completion, **kwargs)

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

    def _chroot_install(self, pkgs, completion):
        distro.install(pkgs, self._root, self._completion, completion,
                       self.set_completion, self.logger)

#
# Step instantiations requires working translation.
#
from .language import LanguageStep
from .license import LicenseStep
from .partitioning import PartitioningStep
from .installation import InstallStep
from .download import DownloadStep
from .localization import LocalizationStep
from .password import PasswordStep
from .end import EndStep


def initialize():
    _all_steps.append(LanguageStep())
    _all_steps.append(LicenseStep())
    _all_steps.append(PartitioningStep())
    _all_steps.append(InstallStep())
    _all_steps.append(DownloadStep())
    _all_steps.append(LocalizationStep())
    _all_steps.append(PasswordStep())
    _all_steps.append(EndStep())

    assert(get_steps())
    assert(not _all_steps[0].requires)
    _all_steps[0]._state = _STATE_INIT
    _recalculate_step_dependencies(_all_steps[0])
