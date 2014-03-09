import os
import select
import logging
from subprocess import PIPE, Popen, call, check_call, check_output, CalledProcessError

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


# figure out systemd version
_output = check_output("systemctl --version", shell=True).split()
systemd_version = int(_output[1])

#
# This fonction can be prefered over the subprocess module helpers
# because:
#
#  - For long running processes with few outputs, waiting for the
#    process to finish before processing its output can not be
#    convenient specially when monitoring the process.
#
#  - It automatically logs all sub process outputs (including stderr)
#    without the need to spawn any extra threads.
#
def monitor(cmd, logger=None, stdout_handler=None, stderr_handler=None):
    fd_map = {}
    data = None

    logger.debug("running: %s" % cmd)

    if [logger, stdout_handler, stderr_handler].count(None) == 3:
        return call(cmd, shell=True, stdout=DEVNULL, stderr=DEVNULL)

    p = Popen(cmd, shell=True, stdout=PIPE, stderr=PIPE)

    if not stdout_handler:
        stdout_handler = lambda p,l,d: d
    if not stderr_handler:
        stderr_handler = lambda p,l,d: d

    fd_map[p.stdout.fileno()] = (p.stdout, stdout_handler, logging.DEBUG)
    fd_map[p.stderr.fileno()] = (p.stderr, stderr_handler, logging.WARNING)

    poller = select.poll()
    poller.register(p.stdout, select.POLLIN | select.POLLPRI)
    poller.register(p.stderr, select.POLLIN | select.POLLPRI)

    while p.poll() is None:

        try:
            ready = poller.poll()
        except select.error as e:
            if e.args[0] == errno.EINTR:
                continue
            raise

        for fd, event in ready:
            (fileobj, handler, level) = fd_map[fd]
            #
            # Note: don't use an iterate over file object construct since
            # it uses a hidden read-ahead buffer which won't play well
            # with long running process with limited outputs such as
            # pacstrap.  See:
            # http://stackoverflow.com/questions/1183643/unbuffered-read-from-process-using-subprocess-in-python
            #
            while True:
                line = fileobj.readline()
                line = line.decode()
                if not line:
                    break
                logger.log(level, line.rstrip())
                data = handler(p, line, data)

    retcode = p.wait()
    poller.unregister(p.stdout)
    poller.unregister(p.stderr)

    if retcode:
        raise CalledProcessError(retcode, cmd)

#
# Same as above but execute the command in a chrooted/container
# environment.
#
def monitor_chroot(rootfs, cmd, bind_mounts=[],
                   with_nspawn=True, **kwargs):
    mounts = []

    # Support of bind mounts has been added in v198
    if (bind_mounts and systemd_version < 198):
        with_nspawn=False

    if with_nspawn:
        chroot  = "systemd-nspawn -D %s " % rootfs
        for m in bind_mounts:
            chroot += "--bind %s " % m
    else:
        chroot = "chroot %s " % rootfs

        # Manually bind mount default and requested directories.o
        for src in ['/dev', '/proc', '/sys'] + bind_mounts:
            check_call('mount -o bind %s %s' % (src, rootfs + src), shell=True)
            mounts.append(rootfs + src)

        # Manually mount usual tmpfs directories.
        for dst in ['/tmp', '/run']:
            dst = rootfs + dst
            if not os.path.exists(dst):
                os.mkdir(dst)
            check_call('mount -t tmpfs none %s' % dst, shell=True)
            mounts.append(dst)

    try:
        monitor(chroot + cmd, **kwargs)
    finally:
        for m in reversed(mounts):
            check_call('umount %s' % m, shell=True, stdout=DEVNULL)
