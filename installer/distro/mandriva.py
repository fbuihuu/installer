#
# We manually install urpmi.cfg from the host into the target system
# so all repositories available from the host will be from the target
# too except for remote repositories protected by a password.
#
# We choose, at least for now, to not propagate secrets into the
# target to avoid leaking passwords by mistake. Maybe we'll introduce
# a new option to do that. Note that secrets are stored in
# /etc/urpmi/netrc.
#
# Therefore repository protected by a password couldn't be used for
# installation.
#
# Since urpmi.cfg is installed into the target system, we can use
# --urpmi-root option when installing packages. The table below shows
# the different urpmi behaviours between '--root' and '--urpmi-root':
#
# |--------------+-----------+-------------+----------------|
# |              | urpmi.cfg | local media | --noclean      |
# |--------------+-----------+-------------+----------------|
# | --urpmi-root | target    | host        | rpms in target |
# | --root       | host      | host        | rpms in host   |
# |--------------+-----------+-------------+----------------|
#
# '--urpmi-root' allows one to create a local media easily since rpms
# will always be stored directly in the target system when '--noclean'
# is used.
#
# Unfortunately it won't work if a local media is also used by the
# host because for some reasons urpmi won't store packages in
# /var/cache/urpmi/rpms directory (target or host).
#
import os
import re

from installer.settings import settings, SettingsError
from installer.process import monitor, monitor_chroot, CalledProcessError


paths = {
    'syslinux.cfg'      : '/boot/syslinux/entries/*',
    'timezones'         : '/usr/share/zoneinfo/posix',
    'keymaps'           : '/usr/lib/kbd/keymaps',
}

#
# This can be used by steps to pass extra options to urpmi. Those
# options won't be part of the urpmi global options like the options
# specified by the users.
#
_urpmi_extra_options = []

def urpmi_add_extra_options(options):
    _urpmi_extra_options.extend(options)


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
    #
    # In case we're reusing the host config, some global options might
    # be present already. If so they're simply discarded and the
    # options given by the user are added instead.
    #
    while contents[1] != '}\n':
        contents.pop(1)

    # Insert the user's options
    lst = []
    for option in options + ['--']:
        if not option.startswith('--'):
            lst.append(option)          # value of current option
            continue
        if lst:
            if len(lst) > 1:
                lst[0] = lst[0] + ':'
            contents.insert(1, " ".join(lst) + '\n')
        lst = ['  ' + option[2:]]

    with open(urpmi_cfg, 'w') as f:
        f.writelines(contents)


def add_repository(repo, root, logger):
    cmd  = ['urpmi.addmedia', '--urpmi-root', root]
    cmd += ['--curl', '--curl-options=-s', '--rsync-options=-q']
    cmd += ['--distrib', repo]
    monitor(cmd, logger=logger)


def add_media(name, media, root, logger, options=[]):
    # Use monitor_chroot() here since the path of the media must be
    # resolved inside the rootfs.
    cmd  = ['urpmi.addmedia'] + options
    cmd += ['--curl', '--curl-options=-s', '--rsync-options=-q']
    cmd += [name, media]
    monitor_chroot(root, cmd, logger=logger)


def del_media(name, root, logger, ignore_error=False):
    try:
        monitor(['urpmi.removemedia', '--urpmi-root', root, name], logger=logger)
    except CalledProcessError:
        if not ignore_error:
            raise


def urpmi_init(repositories, root, logger=lambda *args: None):
    if repositories:
        #
        # A distribution has been specified, configure the rootfs in
        # order to use it. If the installation step has been restarted
        # the config file already exists.
        #
        monitor(['rm', '-f', root + '/etc/urpmi/urpmi.cfg'], logger=logger)

        for repo in repositories:
            logger.info(_('Using repository: %s' % repo))
            add_repository(repo, root, logger)
    else:
        #
        # If no repository has been specified, we use the host urpmi
        # setup but don't import any passwords to avoid leaking
        # secrets.
        #
        logger.info(_('Using urpmi configuration from host'))

        # The directory can exist already, when retrying an
        # installation.
        if not os.path.exists(os.path.join(root, 'etc/urpmi')):
            os.makedirs(os.path.join(root, 'etc/urpmi/'))

        monitor(["cp", '/etc/urpmi/urpmi.cfg', os.path.join(root, 'etc/urpmi/')],
                logger=logger)

        logger.info(_('Retrieving repository public keys'))
        monitor(['urpmi.update', '--urpmi-root', root, '-a', '--force-key', '-q'],
                logger=logger)
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

    urpmi_opts  = _urpmi_extra_options
    urpmi_opts += ["--auto", "--downloader=curl", "--curl-options='-s'"]
    urpmi_opts += ["--rsync-options=-q"]
    urpmi_opts += options

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
            cmd = ['urpmi', '--urpmi-root', root] + urpmi_opts + pkgs
            monitor_chroot(root, cmd, chrooter=None,
                           logger=logger,
                           stdout_handler=stdout_handler)

    # Make sure to set completion level specially in the case where the
    # packages are already installed.
    set_completion(completion_end)
