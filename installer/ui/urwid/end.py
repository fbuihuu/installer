# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer.settings import settings


class EndView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self.page = widgets.Page()
        # Make the list centered inside its container
        body = widgets.ClickableTextPile([(_("Quit"),     self.on_quit),
                                          (_("Reboot"),   self.on_reboot),
                                          (_("Shutdown"), self.on_shutdown)])
        body = urwid.Filler(body, 'middle')
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.page.body = body

    def _redraw(self):
        self.page.title = _("Your system is ready to be used")

    def on_quit(self, widget):
        settings.exit.action = "Quit"
        self.run()

    def on_reboot(self, widget):
        settings.exit.action = "Reboot"
        self.run()

    def on_shutdown(self, widget):
        settings.exit.action = "Shutdown"
        self.run()
