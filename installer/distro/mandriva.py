import os
import re

from installer.settings import settings, SettingsError
from installer.process import monitor, monitor_chroot


paths = {
    'syslinux.cfg'      : '/boot/syslinux/entries/*',
    'timezones'         : '/usr/share/zoneinfo/posix',
    'keymaps'           : '/usr/lib/kbd/keymaps',
}

_urpmi_root_opt=None

# This assumes that the global options section is empty and is at the
# start of the file.
def _urpmi_config_set_options(options, urpmi_cfg):

    with open(urpmi_cfg, 'r') as f:
        contents = f.readlines()

    while contents[0].strip() == '':
        contents.pop(0)

    if contents[0] != '{\n':
        # FIXME: another type of exception should be raised.
        raise SettingsError("%s is malformated: missing opening '{'." % urpmi_cfg)

    while contents[1].strip() == '':
        contents.pop(1)

    if contents[1] != '}\n':
        # missing the closing brace or urpmi.cfg already has some
        # options, this shouldn't be the case since it has just been
        # created.
        raise SettingsError("some global options are already present in %s" % urpmi_cfg)

    # Insert the user's options
    lst = []
    for option in options + ['--']:
        if not option.startswith('--'):
            lst.append(option)
            continue
        if lst:
            if len(lst) > 1:
                lst[0] = lst[0] + ':'
            contents.insert(1, " ".join(lst) + '\n')
        lst = ['  ' + option[2:]]

    with open(urpmi_cfg, 'w') as f:
        f.writelines(contents)


def add_repository(repo, root, logger):
    #
    # We split the operation into 2 separate steps (addmedia + update)
    # in order to silent urpmi when it retrieve the repo metadata.
    #
    monitor(['urpmi.addmedia', '--raw', '--urpmi-root', root, '--distrib', repo],
            logger=logger)
    monitor(['urpmi.update', '-q', '--urpmi-root', root, '-a'],
            logger=logger)


def urpmi_init(repositories, root, logger=lambda *args: None):
    global _urpmi_root_opt

    if repositories:
        #
        # Distribution has been specified, setup the rootfs in order
        # to use it.
        #
        for repo in repositories:
            logger.info(_('Using repository: %s' % repo))
            add_repository(repo, root, logger)

        # Tell urpmi to pick its configuration up from the rootfs.
        _urpmi_root_opt='--urpmi-root'

    else:
        logger.info(_('Using urpmi configuration from host'))
        #
        # If no repository has been specified, we use the host urpmi
        # setup but don't import any passwords (stored in
        # /etc/urpmi/netrc) to avoid leaking secrets.
        #
        if not os.path.exists(os.path.join(root, 'etc/urpmi')):
            os.makedirs(os.path.join(root, 'etc/urpmi/'))
        monitor(["cp", '/etc/urpmi/urpmi.cfg', os.path.join(root, 'etc/urpmi/')],
                logger=logger)

        # Import pub keys in the rootfs.
        monitor(['urpmi.update', '--urpmi-root', root, '-a', '--force-key', '-q'],
                logger=logger)

        # Since medias might be protected by passwords, use host urpmi
        # setup to install package.
        _urpmi_root_opt='--root'

    #
    # Import the user's options as default urpmi options for the
    # target system.
    #
    if settings.Urpmi.options:
        logger.debug('Adding user options in urpmi.cfg')
        _urpmi_config_set_options(settings.Urpmi.options.split(),
                                  root + '/etc/urpmi/urpmi.cfg')


def install(pkgs, root=None, completion_start=0, completion_end=0,
          set_completion=lambda *args: None, logger=None, options=[]):

    urpmi_opts  = ["--auto", "--downloader=curl", "--curl-options='-s'"]
    urpmi_opts += ["--rsync-options='-q'"]
    urpmi_opts += options

    if settings.Urpmi.distrib_src:
        urpmi_opts += ['--use-distrib', settings.Urpmi.distrib_src]

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
            global _urpmi_root_opt
            cmd = ['urpmi', _urpmi_root_opt, root] + urpmi_opts + pkgs
            monitor_chroot(root, cmd, chrooter=None,
                           logger=logger,
                           stdout_handler=stdout_handler)

    # Make sure to set completion level specially in the case where the
    # packages are already installed.
    set_completion(completion_end)
