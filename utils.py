# -*- coding: utf-8 -*-
#

from __future__ import print_function
import sys


KB = 1000
MB = 1000 * KB
GB = 1000 * MB
TB = 1000 * GB

KiB = 1024
MiB = 1024 * KiB
GiB = 1024 * MiB
TiB = 1024 * GiB


def die(*args):
    print(*args, end='\n', file=sys.stderr)
    exit(1)


def pretty_size(size, KiB=True):
    UNITS = {
        1000: ['bytes',  'KB',  'MB',  'GB',  'TB',  'PB'],
        1024: ['bytes', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
    }

    multiple = 1024.0 if KiB else 1000.0

    for unit in UNITS[multiple]:
        if size < multiple and size > -multiple:
            return "%3.1f %s" % (size, unit)
        size /= multiple
    return "%3.1f %s" % (size, unit)


class Signal(object):

    def __init__(self):
        self._callbacks = []

    def connect(self, cb):
        self._callbacks.append(cb)

    def emit(self, *args, **kargs):
        for cb in self._callbacks:
            cb(*args, **kargs)
