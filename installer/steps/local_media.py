# -*- coding: utf-8 -*-
#
# This step is used to fetch additionnal packages. Once downloaded a
# new local media will be created and added to the list of the medias
# to use.
#
# The primary usage is to create a self contained system which may
# have only an intranet connection. It will still be possible to
# install additionnal (specified during the installation) packages
# without the needs of physical access to the target system.
#
from __future__ import unicode_literals

import os

from installer import distro
from installer.system import distribution
from installer.settings import settings, SettingsError
from installer.utils import rsync
from . import Step, StepError


class _LocalMediaStep(Step):

    requires = ['rootfs']

    @property
    def name(self):
        return _("Local Media")


class ArchLocalMediaStep(_LocalMediaStep):

    def __init__(self):
        _LocalMediaStep.__init__(self)

        if not self._skip:
            raise SettingsError(_('Local Media step not implemented'))


class MandrivaLocalMediaStep(_LocalMediaStep):

    _BROKEN_URPMI_MSG = _("""Local media can't be created on the target.

Some medias/repos used during the installation process were also local.
Due to a limitation (or a bug ?) of urpmi(1), packages installed on the
target system can't be found.""")

    def __init__(self):
        #
        # By default this step is disabled, the user has to enable it
        # explicitely (by using --no-skip option). If enabled, we still
        # check for 'location' setting later since it can be set
        # through the view.
        #
        _LocalMediaStep.__init__(self)
        self._urpmi = self._chroot_install # alias
        if not self._skip:
            # Inform urpmi to keep all installed packages
            distro.urpmi_add_extra_options(['--noclean'])
            #
            # Do sanity checkings early on the packages file list but
            # don't store the result to allow the user to do
            # modifications while the installer is running.
            #
            settings.LocalMedia.packages

    def _process(self):
        #
        # Since 'location' has no default value, it will raise a
        # SettingsError exception if the user did not set it up
        # through the config file.
        #
        dst = settings.LocalMedia.location

        #
        # There's no way to request urpmi(1) to keep *installed*
        # packages somewhere for later reinstallation.
        #
        # It only keeps *downloaded* packages (in the target at
        # /var/cache/urpmi/rpms) so if the repo used during the
        # installation is local, none of the installed packages will
        # be saved (even though we used both --no-clean and
        # --urpmi-root options).
        #
        # This behaviour makes impossible to implement correctly this
        # step.
        #
        # As a workaround, we do the following:
        #
        #   - if the local media is already present on the host
        #     system, import *all* packages from it. We assume that
        #     the host was installed by us with the same package list.
        #
        #   - if only local medias were used during the installation
        #     step then the cache is empty (it's been cleaned up
        #     before starting). Trap this case and fail.
        #
        #   - otherwise either a mix of local/remote medias or only
        #     remotes medias were used. We currently can't detect the
        #     case (unless we parse urpmi.cfg) so we hope for the
        #     better :-/
        #
        if os.path.exists(dst):
            self.logger.info(_('Importing host\'s media %s') % dst)
            self._chroot(['mkdir', '-p', dst])
            self._rsync(dst + '/', self._root + dst, 50)
            self._chroot(['sh', '-c', 'rm -f /var/cache/urpmi/rpms/*.rpm'])

        elif not os.listdir(self._root + '/var/cache/urpmi/rpms'):
            # Unfortunately this won't trap the case where local *and*
            # remote repositories are used together.
            raise StepError(self._BROKEN_URPMI_MSG)

        else:
            self.logger.info(_('Populating media %s using urpmi(1) cache') % dst)
            # assume that only remote media will be used.
            if settings.LocalMedia.packages:
                self._urpmi(settings.LocalMedia.packages, 50, ['--no-install'])

            self._chroot(['mkdir', '-p', dst])
            self._rsync('/var/cache/urpmi/rpms/', dst, 60, rootfs=self._root,
                        options=['--remove-source-files'])

        self._urpmi(['genhdlist2'], 70)
        self._chroot(['genhdlist2', '--xml-info', '--clean', dst])
        self.set_completion(90)

        # Delete local media just in case it's already registered, so
        # we can add it (back) safely.
        distro.del_media('Local Media', self._root, self.logger, ignore_error=True)
        distro.add_media('Local Media', dst, self._root, self.logger, ['--virtual'])


def LocalMediaStep():
    if distribution.distributor == 'Mandriva':
        return MandrivaLocalMediaStep()

    elif distribution.distributor == 'Arch':
        return ArchLocalMediaStep()

    raise NotImplementedError()
