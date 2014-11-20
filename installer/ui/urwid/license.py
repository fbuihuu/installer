# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid

from . import StepView
from . import widgets
from installer.settings import settings


class LicenseView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self._locale = None
        self.page = widgets.Page(_("License Agreement"))

        content = []
        with open("LICENCE-" + self._ui.language, "r") as f:
            for line in f:
                content.append(line)
        content = urwid.Text(content)

        walker = urwid.SimpleListWalker([])
        walker.append(urwid.Padding(content, "center", ('relative', 90)))
        walker.append(urwid.Divider())
        walker.append(widgets.Button(_("Accept"), on_press=self.on_accepted))
        walker.append(widgets.Button(_("Refuse"), on_press=self.on_disagreed))
        self.page.body = urwid.ListBox(walker)

    def on_accepted(self, button):
        settings.License.status = "accepted"
        self.run()

    def on_disagreed(self, button):
        settings.License.status = "refused"
        self.run()
