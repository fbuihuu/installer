# -*- coding: utf-8 -*-
#

import urwid
from ui.urwid import StepView
from . import widgets
from settings import settings


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
        settings.exit.action = entry.text
        self.run()
