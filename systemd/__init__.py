# -*- coding: utf-8 -*-
#
import os
from subprocess import *

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


# figure out systemd version
_output = check_output("systemctl --version", shell=True).split()
systemd_version = int(_output[1])


def xchroot(rootfs, command, bind_mounts=[], logger=None, force_chroot=False):
    mounts = []
    use_chroot = False

    # Support of bind mounts has been added in v198
    if systemd_version < 198 or force_chroot:
        use_chroot = True

    if not use_chroot:
        cmd  = "systemd-nspawn -D %s " % rootfs
        for m in bind_mounts:
            cmd += "--bind %s " % m
    else:
        for dst in ['/tmp', '/run', '/dev', '/dev/shm']:
            dst = rootfs + dst
            if not os.path.exists(dst):
                os.mkdir(dst)
            cmd = 'mount -t tmpfs none %s' % dst
            check_call(cmd, shell=True)
            mounts.append(dst)

        for src in ['/proc', '/sys'] + bind_mounts:
            cmd = 'mount -o bind %s %s' % (src, rootfs + src)
            check_call(cmd, shell=True)
            mounts.append(rootfs + src)

        cmd = "chroot %s " % rootfs

    p = Popen(cmd + "sh -c '%s'" % command, shell=True, stdout=PIPE, stderr=STDOUT)
    while p.poll() is None:
        line = p.stdout.readline()
        line = line.rstrip()
        if not line:
            continue
        if logger:
            logger.info(line)

    retcode = p.wait()
    for m in reversed(mounts):
        check_call('umount %s' % m, shell=True, stdout=DEVNULL)

    if retcode:
        raise CalledProcessError(retcode, command)
