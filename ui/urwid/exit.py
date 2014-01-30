# -*- coding: utf-8 -*-
#

from ui.urwid import StepView
import urwid
import widgets

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class ExitView(StepView):

    _actions = ["Quit", "Reboot", "Shutdown"]

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self.page = widgets.Page()
        # Make the list centered inside its container
        body = widgets.ClickableTextList(self._actions, self.on_click)
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.page.body = body

    def redraw(self):
        self.page.title = _("Your system is ready to be used")

    def on_click(self, entry):
        self._ui.installer.data["exit/action"] = entry.text
        self.run()
