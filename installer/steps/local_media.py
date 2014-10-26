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

import os

from installer import distro
from installer.system import distribution
from installer.settings import settings, SettingsError
from installer.utils import rsync
from . import Step


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

    def _process(self):
        #
        # Since 'location' has no default value, it will raise a
        # SettingsError exception if the user did not set it up
        # through the config file.
        #
        dst = settings.LocalMedia.location

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
