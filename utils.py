# -*- coding: utf-8 -*-
#

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