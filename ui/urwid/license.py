# -*- coding: utf-8 -*-
#

from menus import BaseMenu
import urwid
import widgets


class Menu(BaseMenu, widgets.MenuWidget):

    requires = ["language"]
    provides = ["license"]

    def __init__(self, ui, menu_event_cb):
        BaseMenu.__init__(self, ui, menu_event_cb)
        widgets.MenuWidget.__init__(self, ui)
        self._locale = None

        self.page = widgets.Page()
        self.page.body = urwid.ListBox(urwid.SimpleListWalker([]))

    @property
    def name(self):
        return _("License")

    def redraw(self):
        if self._locale == self.ui.language:
            return
        self._locale = self.ui.language

        self.page.title = _("License Agreement")

        walker  = self.page.body.body
        content = []
        with open("LICENCE-" + self.ui.language, "r") as f:
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
        self.state = Menu._STATE_DONE

    def on_disagreed(self, button):
        self.logger.critical(_("you rejected the terms of the license, aborting"))
        self.state = Menu._STATE_FAILED
        self.ui.quit(3)
