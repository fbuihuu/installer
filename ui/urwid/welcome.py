# -*- coding: utf-8 -*-
#

from ui.urwid import StepView
import urwid
import widgets
from l10n import country_dict

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class WelcomeView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

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
