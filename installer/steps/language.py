# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

from . import Step
from installer import l10n
from installer.settings import settings


class LanguageStep(Step):

    provides = ["language"]

    @property
    def name(self):
        return _("Language")

    # This only initializes unset l10n settings by using the language
    # choosen by the user. The l10n settings will be used by the
    # 'localization' step.
    def _process(self, zone):
        if not zone:
            zone = l10n.get_default_zone()

        if not settings.Localization.locale:
            settings.Localization.locale = zone.locale
        if not settings.Localization.timezone:
            settings.Localization.timezone = zone.timezone
        if not settings.Localization.keymap:
            settings.Localization.keymap = zone.keymap

        self.logger.info(_('set location to %s' % zone.country))
