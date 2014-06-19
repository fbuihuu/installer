# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer.settings import settings
from installer.l10n import country_names, country_zones


#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class LanguageView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self._zone = None

        self.page = widgets.Page(_("Select your location"))
        # Make the list centered inside its container
        countries = sorted(country_names.values())
        body = widgets.ClickableTextList(countries, self.on_click)
        # Try to move the focus on the entry that matches (roughly)
        # the current locale.
        body.set_focus(country_names[settings.I18n.country])
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body,'center', width=('relative', 60))
        self.page.body = body

    def on_click(self, entry):
        country = entry.text

        for code in country_names:
            if country_names[code] == country:
                break

        zi = country_zones[code][0]
        settings.I18n.country  = code
        settings.I18n.timezone = zi.timezone
        settings.I18n.keymap   = zi.keymap
        settings.I18n.locale   = zi.locale

        # Change the language of the whole ui.
        self._ui.language = settings.I18n.locale

        self.run()
