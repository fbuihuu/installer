# -*- coding: utf-8 -*-
#

from ui.urwid import UrwidMenu
import urwid
import widgets


class Menu(UrwidMenu):

    def __init__(self, ui):
        UrwidMenu.__init__(self, ui)
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
        self.logger.info(_("you accepted the terms of the license"))
        self._ui.installer.data["license"] = "accepted"
        self.ready()

    def on_disagreed(self, button):
        self.logger.critical(_("you rejected the terms of the license, aborting"))
        self._ui.installer.data["license"] = "refused"
        self.ready()
