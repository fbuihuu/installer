# -*- coding: utf-8 -*-
#

import menu
import urwid


class Menu(urwid.WidgetWrap, menu.Menu):

    requires = ["language"]
    provides = ["license"]

    def __init__(self, ui, menu_event_cb):
        menu.Menu.__init__(self, _("License"), ui, menu_event_cb)

    def build_ui_content(self):
        content = []
        with open("LICENCE", "r") as f:
            for line in f:
                content.append(line)
        items = []
        items.append(urwid.Padding(urwid.Text(content), "center", ('relative', 90)))
        items.append(urwid.Divider())
        items.append(urwid.Button("Accept", on_press=self.on_accepted))
        items.append(urwid.Button("Disagree", on_press=self.on_disagreed))
        walker = urwid.SimpleListWalker(items)

        return urwid.ListBox(walker)

    def on_accepted(self, button):
        self.logger.info("you accepted the terms of the license")
        self.state = Menu._STATE_DONE

    def on_disagreed(self, button):
        self.logger.critical("you rejected the terms of the license, aborting")
        self.state = Menu._STATE_FAILED
        self.ui.quit(3)
