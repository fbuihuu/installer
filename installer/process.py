import os
import stat
import signal
import threading
import logging
import subprocess

try:
    from subprocess import DEVNULL # py3k
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


# aliases
CalledProcessError = subprocess.CalledProcessError
check_call = subprocess.check_call
call = subprocess.call

# figure out systemd version
_output = subprocess.check_output(["systemctl", "--version"]).split()
systemd_version = int(_output[1])


class _StreamWorker(threading.Thread):
    """Used to parse and log subprocess' stdout and stderr"""

    def __init__(self, handler):
        threading.Thread.__init__(self)
        self.daemon   = True
        self._stream  = None
        self._handler = handler
        self._data    = None
        self._logger  = None
        self._log_level = None

    def run(self):
        #
        # Note: don't use an iterate over file object construct since
        # it uses a hidden read-ahead buffer which won't play well
        # with long running process with limited outputs such as
        # pacstrap.  See:
        # http://stackoverflow.com/questions/1183643/unbuffered-read-from-process-using-subprocess-in-python
        #
        while True:
            line = self._stream.readline().decode()
            if not line:
                break
            if self._logger:
                self._logger.log(self._log_level, line.rstrip())
            if self._handler:
                self._data = self._handler(self._stream, line, self._data)

    def connect(self, stream):
        self._stream = stream
        self.start()

    def set_logger(self, logger, log_level):
        self._logger = logger
        self._log_level = log_level

#
# Redefine some subprocess' helpers to make sure they use 'LC_ALL=C'
# so we can parse/read safely their output.
#
def check_output(*args, **kwargs):
    env = os.environ.copy()
    env['LC_ALL'] = 'C'
    kwargs['env'] = env
    return subprocess.check_output(*args, **kwargs)

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

    if logger:
        logger.debug("running: %s", " ".join(args))

    #
    # Make sure the command's output is always formatted the same
    # regardless the current locale setting.
    #
    env = os.environ.copy()
    env['LC_ALL'] = 'C'

    if [logger, stdout_handler, stderr_handler].count(None) == 3:
        subprocess.check_call(args, env=env, stdout=DEVNULL, stderr=DEVNULL)
        return

    #
    # Prepare the process outputs parsers.
    #
    stdout_worker = _StreamWorker(stdout_handler)
    stderr_worker = _StreamWorker(stderr_handler)

    stdout_worker.set_logger(logger, logging.DEBUG)
    stderr_worker.set_logger(logger, logging.WARNING)

    #
    # Make the new created process the group leader, so we can kill
    # it *and* all its sibling easily by sending signals to the whole
    # group. pacstrap for example needs that.
    #
    p = subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE, preexec_fn=os.setpgrp)
    _current = p
    stdout_worker.connect(p.stdout)
    stderr_worker.connect(p.stderr)

    retcode = p.wait()
    stdout_worker.join()
    stderr_worker.join()
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

#
# Mount helpers: target dir is always in the chroot.
#
def _mount_bind(sources, rootfs, ro=False):
    try:
        for i, src in enumerate(sources):
            dst = rootfs + src
            if not os.path.exists(dst):
                os.makedirs(dst)
            check_call(['mount', '--bind', src, dst])
            if ro:
                check_call(['mount', '-o', 'remount,ro', dst])
    except:
        # This shouldn't fail.
        for src in reversed(sources[:i]):
            check_call(['umount', rootfs + src], stdout=DEVNULL)
        raise


def _mount_tmpfs(sources, rootfs, nodev=True):
    opts = 'strictatime,nosuid'
    if nodev:
        opts += ',nodev'

    try:
        for i, src in enumerate(sources):
            dst = rootfs + src
            if not os.path.exists(dst):
                os.makedirs(dst)
            check_call(['mount', '-t', 'tmpfs', '-o', opts, 'none', dst])
    except:
        # This shouldn't fail.
        for src in reversed(sources[:i]):
            check_call(['umount', rootfs + src], stdout=DEVNULL)
        raise


def _create_device_nodes(rootfs):
    devices = ('null', 'zero', 'random', 'urandom', 'tty')

    for dev in devices:
        node = os.path.join('/dev', dev)
        st   = os.stat(node)

        mode = st.st_mode
        assert(stat.S_ISCHR(mode) or stat.S_ISBLK(mode))

        dirname = os.path.dirname(node)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

        os.mknod(rootfs + node, st.st_mode, st.st_rdev)


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

        # Manually bind mount main pseudo fs.
        sources = ['/proc', '/sys']
        _mount_bind(sources, rootfs)
        mounts.extend(sources)

        # Manually mount usual tmpfs directories.
        sources = ['/tmp', '/run']
        _mount_tmpfs(sources, rootfs)
        mounts.extend(sources)

        # Create a minimal set of device nodes inside rootfs to
        # satisfy any reasonable package installations.
        if '/dev' not in bind_mounts:
            _mount_tmpfs(['/dev'], rootfs, nodev=False)
            mounts.append('/dev')
            _create_device_nodes(rootfs)

        # bind mount user's dirs if any at last so they have
        # precedence.
        _mount_bind(bind_mounts, rootfs)
        mounts.extend(bind_mounts)

        # Finally copy /etc/resolv.conf into the chroot but don't barf
        # if that fails.
        call(["cp", "/etc/resolv.conf", rootfs + "/etc/resolv.conf"],
             stderr=DEVNULL)

    try:
        monitor(chroot + args, **kwargs)
    finally:
        for m in reversed(mounts):
            check_call(["umount", "-l", rootfs + m], stdout=DEVNULL)
