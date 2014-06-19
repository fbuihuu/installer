# -*- coding: utf-8 -*-
#
import os

from . import Step
from installer.settings import settings
from installer import l10n


class LocalizationStep(Step):

    requires = ["rootfs"]
    provides = ["localization"]

    def __init__(self):
        Step.__init__(self)

    @property
    def name(self):
        return _("Localization")

    def _cancel(self):
        pass

    def _process(self):
        #
        # The installation step should had taken care of the
        # installation of the locale package.
        #
        # Don't rely on localectl(1), it may be missing on old
        # systems.
        #
        locale = settings.I18n.locale
        keymap = settings.I18n.keymap
        tzone  = settings.I18n.timezone
        charmap = "UTF-8"

        self.logger.debug("using locale '%s'", locale)
        self.logger.debug("using keymap '%s'", keymap)
        self.logger.debug("using timezone '%s'", tzone)

        with open(self._root + '/etc/locale.conf', 'w') as f:
            f.write("LANG=%s.%s\n" % (locale, charmap))

        with open(self._root + '/etc/vconsole.conf', 'w') as f:
            f.write("KEYMAP=%s\n" % keymap)

        # Old versions of systemd-nspawn bind mount localtime
        tz_path = os.path.join(l10n.timezones_path, tzone)
        self._chroot('ln -sf %s /etc/localtime' % tz_path, with_nspawn=False)
