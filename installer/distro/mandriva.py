import os
import re

from installer.settings import settings
from installer.process import monitor, monitor_chroot


paths = {
    'syslinux.cfg'      : '/boot/syslinux/entries/*',
    'timezones'         : '/usr/share/zoneinfo/posix',
    'keymaps'           : '/usr/lib/kbd/keymaps',
}


_first_install_call = True
def _init_urpmi(root, logger=lambda *args: None):
    # Import urpmi.cfg from host since it's the one used to init the rootfs.
    monitor(["cp", '/etc/urpmi/urpmi.cfg', os.path.join(root, 'etc/urpmi/')])

    # Import pub keys in the rootfs
    monitor(['urpmi.update', '--urpmi-root', root, '-a', '--force-key', '-q'])


def install(pkgs, root=None, completion_start=0, completion_end=0,
          set_completion=lambda *args: None, logger=None):

    urpmi_opts  = settings.Urpmi.options.split()
    urpmi_opts += ["--auto", "--downloader=curl", "--curl-options='-s'"]

    def stdout_handler(p, line, data):
        pattern = re.compile(r'\s+([0-9]+)/([0-9]+): ')
        match   = pattern.match(line)
        if match:
            count, total = map(int, match.group(1, 2))
            delta = completion_end - completion_start
            set_completion(completion_start + delta * count / total)

    if pkgs:
        if not root:
            cmd = ['urpmi'] + urpmi_opts + pkgs
            monitor(cmd, logger=logger, stdout_hander=stdout_hander)

        else:
            if os.path.exists(os.path.join(root, 'usr/sbin/urpmi')):
                global _first_install_call
                if _first_install_call:
                    _init_urpmi(root, logger)
                    _first_install_call = False

            cmd = ['urpmi', '--root', root] + urpmi_opts + pkgs
            monitor(cmd, logger=logger, stdout_handler=stdout_handler)

    # Make sure to set completion level specially in the case where the
    # packages are already installed.
    set_completion(completion_end)

