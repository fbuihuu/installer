# -*- coding: utf-8 -*-
#

from ui.urwid import UrwidMenu
import urwid
import widgets
from l10n import country_dict

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class Menu(UrwidMenu):

    def __init__(self, ui):
        UrwidMenu.__init__(self, ui)

        self.page = widgets.Page()
        # Make the list centered inside its container
        body = widgets.ClickableTextList(country_dict.keys(), self.on_click)
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.page.body = body

    def redraw(self):
        self.page.title = _("Select your location")

    def on_click(self, entry):
        place = entry.text
        if self._ui.installer.data["localization/country"] != place:
            self._ui.installer.data["localization/country"] = place
            self.ready()
