import os

VERSION = (0, 1)

def get_version():
    return '.'.join(str(x) for x in VERSION)

def get_topdir():
    pwd = os.path.dirname(os.path.abspath(__file__))
    topdir = os.path.dirname(pwd)
    for d in ('bin', 'installer', '.git', 'po'):
        if not os.path.exists(os.path.join(topdir, d)):
            return None
    return topdir
