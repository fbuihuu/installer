from __future__ import print_function
import sys
import time
import logging
import threading
from gi.repository import GLib, GObject

from .. import UI
from .widgets import ProgressBar
from installer import steps
from installer.settings import settings
from installer.system import get_terminal_size


logger = logging.getLogger()


def parse_cmdline(parser):
    """Parses the relevant cmdline arguments specific to urwid frontend"""
    group = parser.add_argument_group('cmdline', 'command line frontend specific options')
    group.add_argument("--verbose",
                       dest="verbose",
                       action="store_true",
                       help="show logs during installation"),
    group.add_argument("--no-progress",
                       dest="progress",
                       action="store_false",
                       help="don't show progress during installation"),
    group.add_argument("disks",
                        metavar="disk",
                        nargs="*",
                        help="disk(s) to use for installation (cmdline frontend only)")


class ViewError(Exception):
    """Exception thrown by cmdline view"""


class StdoutFilter(logging.Filter):

    def filter(self, record):
        return record.levelno <= logging.INFO


class StderrFilter(StdoutFilter):

    def filter(self, record):
        return not StdoutFilter.filter(self, record)


class CommandLineUI(UI):

    def __init__(self, args):
        # For now, no need to accept the license with the cmdline frontend.
        settings.Steps.license = False
        UI.__init__(self)
        self._retcode = 0
        self._args = args
        self._isatty = sys.stdout.isatty()
        self._step_finished_event = threading.Event()
        self._loop = GLib.MainLoop()

        if not self._isatty:
            self._args.progress = False
        if self._args.verbose:
            self._args.progress = False

        if self._args.progress:
            self._progress_lock = threading.Lock()

    def redraw(self):
        pass

    def _init_logging(self):
        global logger

        if self._args.progress:
            # Only critical messages are sent to stderr (and the log file).
            f = logging.Formatter('%(message)s')
            h2 = logging.StreamHandler(sys.stderr)
            h2.setLevel(logging.ERROR)
            h2.addFilter(StderrFilter())
            h2.setFormatter(f)
            logger.addHandler(h2)
        else:
            f = logging.Formatter('[%(asctime)s] %(name)s: %(message)s','%H:%M:%S')
            # Weird... all of this only to send logs to stdout/stderr
            h1 = logging.StreamHandler(sys.stdout)
            h2 = logging.StreamHandler(sys.stderr)
            h1.setLevel(logging.DEBUG if self._args.verbose else logging.INFO)
            h2.setLevel(logging.WARNING)
            h1.addFilter(StdoutFilter())
            h2.addFilter(StderrFilter())
            h1.setFormatter(f)
            h2.setFormatter(f)
            logger.addHandler(h1)
            logger.addHandler(h2)

    def __run_steps(self):
        self._retcode = 1

        for step in steps.get_steps():
            assert(not step.is_disabled())

            if not step.view_data:
                step.view_data = StepView(None, step)
            view = step.view_data

            if self._args.progress:
                self._progress_bar = ProgressBar(step.name)
                timer = GLib.timeout_add_seconds(1, self._on_timeout, step)

            self._step_finished_event.clear()
            view.run(self._args)
            self._step_finished_event.wait()

            if not step.is_done():
                return

        self._retcode = 0

    def _run_steps(self):
        try:
            self.__run_steps()
        except ViewError as e:
            logger.critical("%s" % e)
        finally:
            self._loop.quit()

    def run(self):
        self._init_logging()

        # Since PyGObject 3.10.2, calling GObject.threads_init() is no
        # longer needed.
        GObject.threads_init()

        th = threading.Thread(target=self._run_steps)
        th.start()
        try:
            self._loop.run()
        except KeyboardInterrupt:
            logger.critical(_("Interrupt signal received, aborting..."))

        self.quit()
        th.join()
        return self._retcode

    def quit(self, delay=0):
        self._quit()
        time.sleep(delay)

    def _on_step_finished(self, step):
        self._step_finished_event.set()

    def _on_step_completion(self, step, percent):
        if self._args.progress:
            self._progress_lock.acquire()
            self._progress_bar.percent = percent
            self._progress_bar.show()
            self._progress_lock.release()

    def _on_timeout(self, step):
        assert(self._args.progress)
        if step.is_in_progress():
            self._progress_lock.acquire()
            self._progress_bar.time  = int(time.time())
            self._progress_bar.width = get_terminal_size().columns
            self._progress_bar.show()
            self._progress_lock.release()
            return True
        # stop and destroy the timer
        return False


class StepView(object):

    def __init__(self, ui, step):
        self._step = step

    def _run(self, args):
        self._step.process()

    def run(self, args):
        self._run(args)
