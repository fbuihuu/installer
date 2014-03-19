import os
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
def monitor(args, logger=None, stdout_handler=None, stderr_handler=None):
    fd_map = {}
    data = None

    logger.debug("running: %s", " ".join(args))

    if [logger, stdout_handler, stderr_handler].count(None) == 3:
        return call(cmd, stdout=DEVNULL, stderr=DEVNULL)

    p = Popen(args, stdout=PIPE, stderr=PIPE)

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
        raise CalledProcessError(retcode, " ".join(args))

#
# Same as above but execute the command in a chrooted/container
# environment. The command is always excuted by the shell, hence the
# cmd parameter should be a string which specifies the command to execute
# through the shell.
#
def monitor_chroot(rootfs, cmd, bind_mounts=[],
                   with_nspawn=True, **kwargs):
    mounts = []

    # Support of bind mounts has been added in v198
    if (bind_mounts and systemd_version < 198):
        with_nspawn=False

    if with_nspawn:
        chroot  = ["systemd-nspawn", "-D", rootfs]
        for m in bind_mounts:
            chroot += ["--bind", m]
    else:
        chroot = ["chroot", rootfs]

        # Manually bind mount default and requested directories.o
        for src in ['/dev', '/proc', '/sys'] + bind_mounts:
            check_call(["mount", "-o", "bind", src, rootfs+src])
            mounts.append(rootfs + src)

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
        monitor(chroot + ["sh", "-c", cmd], **kwargs)
    finally:
        for m in reversed(mounts):
            check_call(["umount", m], stdout=DEVNULL)
