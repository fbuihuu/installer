from __future__ import print_function
import time

from installer.system import get_terminal_size

#
# <--------------------------------- COLS ----------------------------------->
# <--------- head --------><---------------- bar ----------------><-- tail -->
#
# language     :     00:00 [################################] 100%
# partitioning :     00:33 [################################] 100%
# installation :     01:33 [######################          ]  70% (300 warns)
#

class _Head(object):

    def __init__(self, title):
        self._title = title
        self._t0    = int(time.time())
        self.t1     = self._t0

    def stringify(self, length):
        elapsed = "%02d:%02d" % divmod(int(self.t1) - self._t0, 60)
        headlen_min = len("%-*s : %s " % (20, self._title, elapsed))
        if length < headlen_min:
            length = headlen_min
        return "%-*s : %*s " % (20, self._title, length - headlen_min, elapsed)


class _Bar(object):

    def __init__(self, bar_minlen=4, bar_char='#'):
        self._bar_char   = bar_char
        self._bar_minlen = bar_minlen + 2 # include bar edges '[]'
        self.percent = 0

    def _stringify_percent(self):
        return "%3d%%" % self.percent

    def _stringify_bar(self, length):
        length = length - len('[]')
        barlen = int(length * self.percent / 100)
        return '[' + '%-*s' % (length, '#' * barlen) + ']'

    def stringify(self, length):
        per = self._stringify_percent()
        if length < self._bar_minlen + 1 + len(per):
            return per
        return self._stringify_bar(length - len(' ' + per)) + ' ' + per


class _Tail(object):

    def __init__(self):
        self.warnings = 0

    def stringify(self):
        if self.warnings == 0:
            return "             "
        if self.warnings < 10:
            return " (%d warnings)" % self.warnings
        return " (%4d warns)" % self.warnings


class ProgressBar(object):

    def __init__(self, name):
        self._head = _Head(name)
        self._pbar = _Bar()
        self._tail = _Tail()
        self.width = get_terminal_size().columns

    @property
    def time(self):
        return self._head.t1

    @time.setter
    def time(self, t):
        self._head.t1 = t

    @property
    def percent(self):
        return self._pbar.percent

    @percent.setter
    def percent(self, percent):
        self._pbar.percent = percent

    @property
    def warnings(self):
        return self._tail.warnings

    @warnings.setter
    def warnings(self, count):
        self._tail.warnings = count

    def set_completion(self, percent):
        self._pbar.set_completion(percent)

    def show(self):
        head = self._head.stringify(int(self.width / 2))
        tail = self._tail.stringify()
        pbar = self._pbar.stringify(self.width - len(head) - len(tail))
        end = '\r' if self.percent < 100 else '\n'
        print("%s%s%s" % (head, pbar, tail), end=end)
