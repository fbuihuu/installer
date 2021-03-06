# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals
from __future__ import print_function

import sys
import re

from installer.process import monitor, check_output


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

#
# I can't find anything simpler to parse the overall progress of
# rsync. Note this supports at rsync v3.0 and v3.1.
#
def rsync(src, dst, completion_start=0, completion_end=0,
          set_completion=lambda *args: None, logger=None,
          rootfs=None, options=[]):

    if rootfs:
        src = rootfs + src
        dst = rootfs + dst

    #
    # This is used to get the total number of files created by rsync
    #
    out = check_output(['rsync', '-a', '--stats', '--dry-run', src, dst])
    out = out.decode()

    # whatever the local used, it seems that rsync uses comma as
    # thousand seperator.
    pattern = re.compile('Total file size: ([0-9,]+)')
    match = pattern.search(out)
    total = int(match.group(1).replace(',', ''))

    if total == 0:
        set_completion(completion_end)
        return

    def stdout_handler(p, line, data):
        bytes = 0 if data is None else data
        bytes += int(line)
        delta = completion_end - completion_start
        set_completion(completion_start + int(delta * bytes / total))
        return bytes
    #
    # Don't log rsync's output since it's not really interesting for
    # the user as we report the number of bytes actually transferred
    # for reporting progression. But log the command run.
    #
    cmd = ['rsync'] + options + ['-a', '--out-format=%b', src, dst]
    logger.debug('running: %s' % ' '.join(cmd))
    monitor(cmd, logger=None, stdout_handler=stdout_handler)


def sed(pattern, replacement, file):
    """Equivalent of 'sed -i s/<pattern>/<replacement>/ <file>'.
    Return True if a substitution happened otherwise False.
    Work for small files only.
    """
    contents = []
    pattern  = re.compile(pattern)
    count = 0

    with open(file, 'r') as f:
        for line in f:
            if pattern.search(line):
                count += 1
            contents.append(pattern.sub(replacement, line))

    if count > 0:
        with open(file, 'w') as f:
            f.writelines(contents)

    return count > 0
