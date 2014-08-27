# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer.settings import settings


class EndView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self.page = widgets.Page(_("Your system is ready to be used"))
        # Make the list centered inside its container
        body = widgets.ClickableTextPile([(_("Quit"),     self.on_quit),
                                          (_("Reboot"),   self.on_reboot),
                                          (_("Shutdown"), self.on_shutdown)])
        body = urwid.Filler(body, 'middle')
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.page.body = body

    def on_quit(self, widget):
        self.do_end('quit')

    def on_reboot(self, widget):
        self.do_end('reboot')

    def on_shutdown(self, widget):
        self.do_end('shutdown')

    def do_end(self, action):
        settings.End.action = action
        # Wait for End step to finish so we can quit easily and safely.
        self._step.process()
        self._ui.quit()
