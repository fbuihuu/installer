# -*- coding: utf-8 -*-
#
import os

from . import Step, StepError
from installer.settings import settings
from installer import l10n
from installer.system import distribution
from installer.process import CalledProcessError


class _L10nStep(Step):

    requires = ["rootfs"]
    provides = ["localization"]

    def __init__(self):
        Step.__init__(self)

    @property
    def name(self):
        return _("Localization")

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

        if not '.' in locale:
            # default charmap is utf-8
            locale = locale + '.UTF-8'

        self.logger.debug("using locale '%s'", locale)
        self.logger.debug("using keymap '%s'", keymap)
        self.logger.debug("using timezone '%s'", tzone)

        try:
            self._do_locale(locale)
        except CalledProcessError:
            raise StepError("Unsupported locale '%s'" % locale)

        self._do_timezone(tzone)
        self._do_keymap(keymap)

    def _do_keymap(self, keymap):
        with open(self._root + '/etc/vconsole.conf', 'w') as f:
            f.write("KEYMAP=%s\n" % keymap)

    def _do_timezone(self, tz):
        # Old versions of systemd-nspawn bind mount localtime
        tz_path = os.path.join(l10n.timezones_path, tz)
        self._chroot(['ln', '-sf', tz_path, '/etc/localtime'], chrooter='chroot')

    def _do_locale(self, locale):
        with open(self._root + '/etc/locale.conf', 'w') as f:
            f.write("LANG=%s\n" % locale)


class ArchL10nStep(_L10nStep):

    def _do_locale(self, locale):
        # make sure the locale is supported
        self._chroot(['grep', '-q', locale, '/etc/locale.gen'])
        # Uncomment all related locales
        self._chroot(['sed', '-i', 's/^#\(%s.*\)/\\1/' % locale, '/etc/locale.gen'])
        self._chroot(['locale-gen'])
        _L10nStep._do_locale(self, locale)


class MandrivaL10nStep(_L10nStep):

    def _do_locale(self, locale):
        self._chroot_install(['locales-%s' % locale.split('_')[0]], 90)
        _L10nStep._do_locale(self, locale)


def LocalizationStep():
    if distribution.distributor == 'Mandriva':
        return MandrivaL10nStep()

    elif distribution.distributor == 'Arch':
        return ArchL10nStep()

    raise NotImplementedError()
