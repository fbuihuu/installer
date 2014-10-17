import os
import re

from installer.process import monitor


paths = {
    'syslinux.cfg'      : '/boot/syslinux/syslinux.cfg',
    'timezones'         : '/usr/share/zoneinfo/posix',
    'keymaps'           : '/usr/share/kbd/keymaps',
}


def install(pkgs, root=None, completion_start=0, completion_end=0,
          set_completion=lambda *args: None, logger=None, options=[]):

    pacman_opts = ['--needed'] + options

    def stdout_handler(p, line, data):
        if data is None:
            data = (0, 0, re.compile(r'Packages \(([0-9]+)\)'))
        count, total, pattern = data

        match = pattern.search(line)
        if not match:
            pass
        elif total == 0:
            total = int(match.group(1)) * 2
            pattern = re.compile(r'downloading |(re)?installing ')
        else:
            if not line.startswith('downloading '):
                count = max(count, total/2)
            count += 1
            delta = completion_end - completion_start
            set_completion(completion_start + delta * count / total)

        return (count, total, pattern)

    if pkgs:
        if root:
            monitor(['pacstrap', root] + pacman_opts + pkgs, logger=logger,
                    stdout_handler=stdout_handler)
        else:
            monitor(['pacman'] + pkgs + pacman_opts, logger=logger,
                    stdout_handler=stdout_handler)

    # Make sure to set completion level specially when packages are
    # already installed (and --needed options is used).
    set_completion(completion_end)
