# -*- coding: utf-8 -*-
#
import os

from . import Step
from installer.settings import settings
from installer import l10n
from installer.system import distribution


class _L10nStep(Step):

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

        self.logger.debug("using locale '%s'", locale)
        self.logger.debug("using keymap '%s'", keymap)
        self.logger.debug("using timezone '%s'", tzone)

        self._do_locale(locale, "UTF-8")
        self._do_timezone(tzone)
        self._do_keymap(keymap)

    def _do_keymap(self, keymap):
        with open(self._root + '/etc/vconsole.conf', 'w') as f:
            f.write("KEYMAP=%s\n" % keymap)

    def _do_timezone(self, tz):
        # Old versions of systemd-nspawn bind mount localtime
        tz_path = os.path.join(l10n.timezones_path, tz)
        self._chroot('ln -sf %s /etc/localtime' % tz_path, with_nspawn=False)

    def _do_locale(self, locale, charmap):
        with open(self._root + '/etc/locale.conf', 'w') as f:
            f.write("LANG=%s.%s\n" % (locale, charmap))


class ArchL10nStep(_L10nStep):

    def _do_locale(self, locale, charmap):
        # Uncomment all related locales
        self._chroot("sed -i 's/^#\(%s.*\)/\\1/' /etc/locale.gen" % locale)
        self._chroot("locale-gen")
        _L10nStep._do_locale(self, locale, charmap)


class MandrivaL10nStep(_L10nStep):

    def _do_locale(self, locale, charmap):
        self._chroot_install(['locales-%s' % locale.split('_')[0]], 90)
        _L10nStep._do_locale(self, locale, charmap)


def LocalizationStep():
    if distribution.distributor == 'Mandriva':
        return MandrivaL10nStep()

    elif distribution.distributor == 'Arch':
        return ArchL10nStep()

    raise NotImplementedError()
