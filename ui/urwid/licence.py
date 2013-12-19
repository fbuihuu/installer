# -*- coding: utf-8 -*-
#

import menu
import urwid


text_padding = (u"Padding widgets have many options.  This "
                u"is a standard Text widget wrapped with a Padding widget "
                u"with the alignment set to relative 20% and with its width "
                u"fixed at 40.")

class Menu(urwid.WidgetWrap, menu.Menu):

    requires = ["language"]
    provides = ["licence"]

    def __init__(self, menu_event_cb, logger):

        menu.Menu.__init__(self, "licence", menu_event_cb, logger)

        # Add text licence
        self.licence_text = urwid.Text("")

        content = []
        items = []

        with open("LICENCE", "r") as f:
            for line in f:
                content.append(line)

        items.append(urwid.Padding(urwid.Text(content), "center", ('relative', 90)))
        items.append(urwid.Divider())
        items.append(urwid.Button("Accept", on_press=self.on_accepted))
        items.append(urwid.Button("Disagree", on_press=self.on_disagreed))

        self._page = urwid.ListBox(urwid.SimpleListWalker(items))

        urwid.WidgetWrap.__init__(self, self._page)

    def ui_content(self):
        return self

    def on_accepted(self, button):
        self.state = Menu._STATE_DONE

    def on_disagreed(self, button):
        self.state = Menu._STATE_FAILED
        #raise urwid.ExitMainLoop()
