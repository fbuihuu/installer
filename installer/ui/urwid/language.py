# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer import l10n
from installer.settings import settings


#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class LanguageView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self.page = widgets.Page(_("Select your location"))
        # Make the list centered inside its container
        countries = sorted(l10n.country_names.values())
        body = widgets.ClickableTextList(countries, self.on_click)
        # Try to move the focus on the entry that matches (roughly)
        # the current locale.
        body.set_focus(l10n.country_names[settings.I18n.country])
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body,'center', width=('relative', 60))
        self.page.body = body

    def on_click(self, entry):
        country = entry.text

        for code in l10n.country_names:
            if l10n.country_names[code] == country:
                zi = l10n.country_zones[code][0]
                break
        try:
            # Change the language of the whole ui.
            self._ui.language = zi.locale

        except l10n.TranslationError:
            self.logger.warn(_("UI is using '%s' language as fallback"),
                             settings.I18n.locale)

        # Only init I18 settings if the user didn't already.
        settings.I18n.country  = code
        if not settings.I18n.timezone:
            settings.I18n.timezone = zi.timezone
        if not settings.I18n.keymap:
            settings.I18n.keymap = zi.keymap
        if not settings.I18n.locale:
            settings.I18n.locale = zi.locale

        self.run()
