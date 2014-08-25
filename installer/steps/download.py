# -*- coding: utf-8 -*-
#

import os

from installer.system import distribution
from installer.settings import settings
from installer.utils import rsync
from . import Step


class _DownloadStep(Step):

    requires = ['rootfs']

    @property
    def name(self):
        return _("Download")


class ArchDownloadStep(_DownloadStep):

    def __init__(self):
        _DownloadStep.__init__(self)
        self.logger.info("disabling download step: not yet implemented")
        self._skip = True # Not Yet Implemented


class MandrivaDownloadStep(_DownloadStep):

    def __init__(self):
        _DownloadStep.__init__(self)
        # Too much PITA to parse urpmi.cfg to retrieve media urls so
        # to make it simple allow the download step only if a distrib
        # url has been specified.

        # By default the download step is enabled.
        if not settings.Step.download:
            self._skip = True
        else:
            # Run the download step only if an alternate distrib has
            # been specified.
            self._skip = not bool(settings.Urpmi.distrib_src) or \
                         not bool(settings.Urpmi.dsitrib_dst)

    def _process(self):
        if not settings.Urpmi.distrib_dst:
            return

        src = settings.Urpmi.distrib_src
        dst = settings.Urpmi.distrib_dst

        if src.startswith("file://"):
            src = src[6:]
        elif src.startswith("rsync://"):
            pass
        elif not src.startswith("/"):
            SettingsError(_("unsupported protocol used by 'distrib_src' option"))

        if dst[0] != '/':
            SettingsError(_("abosulte path must be used for 'distrib_dst'"))

        self._chroot(['mkdir', '-p', dst])
        self._rsync(src, self._root + dst, 2, 90)

        self._chroot(['urpmi.addmedia', '--distrib', dst])


def DownloadStep():
    if distribution.distributor == 'Mandriva':
        return MandrivaDownloadStep()

    elif distribution.distributor == 'Arch':
        return ArchDownloadStep()

    raise NotImplementedError()
