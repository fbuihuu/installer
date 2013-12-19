# -*- coding: utf-8 -*-
#

import menu
import urwid


class Menu(urwid.WidgetWrap, menu.Menu):

    requires = ["language"]
    provides = ["licence"]

    def __init__(self, menu_event_cb, logger):

        menu.Menu.__init__(self, "licence", menu_event_cb, logger)

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
        urwid.WidgetWrap.__init__(self, urwid.ListBox(walker))

    def ui_content(self):
        return self

    def on_accepted(self, button):
        self.logger.info("you accepted the terms of the licence")
        self.state = Menu._STATE_DONE

    def on_disagreed(self, button):
        self.logger.critical("you rejected the terms of the licence")
        self.state = Menu._STATE_FAILED
        #raise urwid.ExitMainLoop()
