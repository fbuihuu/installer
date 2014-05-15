# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer.settings import settings
from installer.l10n import country_dict


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

        self.page = widgets.Page()
        # Make the list centered inside its container
        body = widgets.ClickableTextList(country_dict.keys(), self.on_click)
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.page.body = body

    def redraw(self):
        self.page.title = _("Select your location")

    def on_click(self, entry):
        zone = entry.text

        if self._zone != zone:
            self._zone = zone
            settings.I18n.country  = zone
            settings.I18n.timezone = country_dict[zone][0]
            settings.I18n.keymap   = country_dict[zone][1]
            settings.I18n.locale   = country_dict[zone][2]

            # Change the language of the whole ui.
            self._ui.language = settings.I18n.locale

            self.run()
        else:
            self._ui._select_next_step()
