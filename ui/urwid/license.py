# -*- coding: utf-8 -*-
#

from ui.urwid import StepView
import urwid
import widgets


class LicenseView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self._locale = None
        self.page = widgets.Page()
        self.page.body = urwid.ListBox(urwid.SimpleListWalker([]))

    def redraw(self):
        if self._locale == self._ui.language:
            return
        self._locale = self._ui.language

        self.page.title = _("License Agreement")

        walker  = self.page.body.body
        content = []
        with open("LICENCE-" + self._ui.language, "r") as f:
            for line in f:
                content.append(line)
        content = urwid.Text(content)

        del walker[:]
        walker.append(urwid.Padding(content, "center", ('relative', 90)))
        walker.append(urwid.Divider())
        walker.append(urwid.Button(_("Accept"), on_press=self.on_accepted))
        walker.append(urwid.Button(_("Refuse"), on_press=self.on_disagreed))

    def on_accepted(self, button):
        self._ui.installer.data["license/status"] = "accepted"
        self.ready()

    def on_disagreed(self, button):
        self._ui.installer.data["license/status"] = "refused"
        self.ready()
