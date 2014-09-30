import os
import signal
import select
import logging
from subprocess import PIPE, Popen, call, check_call, check_output, CalledProcessError

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


# figure out systemd version
_output = check_output(["systemctl", "--version"]).split()
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
# 'args' is list of arguments to be passed to Popen(shell=False) (ie
# execvp())
#
_current = None
def get_current():
    return _current


def monitor_kill(sig=signal.SIGTERM, logger=None):
    if get_current():
        # current is the process group leader
        pid = get_current().pid
        if logger:
            logger.debug("killing spawned process group %d" % pid)
        os.killpg(pid, sig)


def _monitor(args, logger=None, stdout_handler=None, stderr_handler=None):
    global _current

    fd_map = {}
    data = None

    if logger:
        logger.debug("running: %s", " ".join(args))

    #
    # Make sure the command's output is always formatted the same
    # regardless the current locale setting.
    #
    env = os.environ.copy()
    env['LC_ALL'] = 'C'

    if [logger, stdout_handler, stderr_handler].count(None) == 3:
        check_call(args, env=env, stdout=DEVNULL, stderr=DEVNULL)
        return

    #
    # Make the new created process the group leader, so we can kill
    # it *and* all its sibling easily by sending signals to the whole
    # group. pacstrap for example needs that.
    #
    p = Popen(args, env=env, stdout=PIPE, stderr=PIPE, preexec_fn=os.setpgrp)
    _current = p

    if not stdout_handler:
        stdout_handler = lambda p,l,d: d
    if not stderr_handler:
        stderr_handler = lambda p,l,d: d

    fd_map[p.stdout.fileno()] = (p.stdout, stdout_handler, logging.DEBUG)
    fd_map[p.stderr.fileno()] = (p.stderr, stderr_handler, logging.WARNING)

    poller = select.poll()
    poller.register(p.stdout, select.POLLIN | select.POLLPRI | select.POLLHUP)
    poller.register(p.stderr, select.POLLIN | select.POLLPRI | select.POLLHUP)

    while fd_map:
        try:
            ready = poller.poll()
        except select.error as e:
            if e.args[0] == errno.EINTR:
                continue
            raise

        for fd, event in ready:

            if event & (select.POLLIN | select.POLLPRI):
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
                    if logger:
                        logger.log(level, line.rstrip())
                    data = handler(p, line, data)

            # Make sure to deal with fd hangup after emptying them.
            if event & select.POLLHUP:
                poller.unregister(fd)
                del fd_map[fd]

    retcode = p.wait()
    _current = None
    if retcode:
        raise CalledProcessError(retcode, " ".join(args))


def monitor(args, logger=None, stdout_handler=None, stderr_handler=None):
    global _current
    assert(not _current)

    try:
        _monitor(args, logger, stdout_handler, stderr_handler)
    finally:
        if _current:
            _current.terminate()
            _current = None

#
# Same as above but execute the command in a chrooted/container
# environment. The command is always excuted by the shell, hence the
# cmd parameter should be a string which specifies the command to execute
# through the shell.
#
def monitor_chroot(rootfs, args, bind_mounts=[],
                   chrooter='chroot', **kwargs):
    mounts = []

    # Support of bind mounts has been added in v198
    if chrooter == 'systemd-nspawn':
        if bind_mounts and systemd_version < 198:
            chrooter = 'chroot'

    if chrooter == 'systemd-nspawn':
        chroot  = ["systemd-nspawn", "-D", rootfs]
        for m in bind_mounts:
            chroot += ["--bind", m]

    elif chrooter == 'chroot':
        chroot = ["chroot", rootfs]

    elif chrooter is None:
        chroot = []

    else:
        raise NotImplementedError()

    if chrooter in ('chroot', None):

        # Manually bind mount default and requested directories.o
        for src in ['/dev', '/proc', '/sys'] + bind_mounts:
            dst = rootfs + src
            if not os.path.exists(dst):
                os.mkdir(dst)
            check_call(["mount", "-o", "bind", src, dst])
            mounts.append(dst)

        # Manually mount usual tmpfs directories.
        for dst in ['/tmp', '/run']:
            dst = rootfs + dst
            if not os.path.exists(dst):
                os.mkdir(dst)
            check_call(["mount", "-t", "tmpfs", "none", dst])
            mounts.append(dst)

        # Finally copy /etc/resolv.conf into the chroot but don't barf
        # if that fails.
        call(["cp", "/etc/resolv.conf", rootfs + "/etc/resolv.conf"],
             stderr=DEVNULL)

    try:
        monitor(chroot + args, **kwargs)
    finally:
        for m in reversed(mounts):
            check_call(["umount", "-l", m], stdout=DEVNULL)
