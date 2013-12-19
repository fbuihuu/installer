#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import menu
import urwid
from urwid.command_map import ACTIVATE
import system
from installer import rootfs
from localisation import country_dict

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class MenuNavigatorEntry(urwid.Button):

    def __init__(self, title):
        self._title = title
        super(MenuNavigatorEntry, self).__init__("")
        w = urwid.SelectableIcon(title, 1)
        w = urwid.AttrMap(w, None, focus_map='reversed')
        self._w = w

    @property
    def name(self):
        return self._title


class ClickableText(urwid.SelectableIcon):

    signals = ["click"]

    def __init__(self, txt):
        urwid.SelectableIcon.__init__(self, txt, -1)

    def keypress(self, size, key):
        if self._command_map[key] != ACTIVATE:
            return key
        self._emit('click')


class ClickableTextList(urwid.WidgetWrap):

    def __init__(self, items, on_click=None):
        lst = []

        for item in items:
            txt = ClickableText(item)
            txt.set_layout('center', 'clip', None)
            urwid.connect_signal(txt, 'click', on_click)
            lst.append(urwid.AttrMap(txt, None, focus_map='reversed'))

        walker = urwid.SimpleListWalker(lst)
        urwid.WidgetWrap.__init__(self, urwid.ListBox(walker))


class Menu(menu.Menu):

    provides = ["language"]

    def __init__(self, callback_event, logger):
        menu.Menu.__init__(self, u"Language", callback_event, logger)

        header = urwid.Text(_("Select your location"), align='center')
        body = ClickableTextList(country_dict.keys(), self.on_click)
        # Make the list centered inside its containers
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body, align='center', width=('relative', 30))

        self._ui_content = urwid.Frame(body, header)
        self.country = None

    def ui_content(self):
        return self._ui_content

    def on_click(self, entry):
        if self.country != entry.text:
            self.logger.info("Set location to %s", entry.text)
            self.country = entry.text
            self.state = Menu._STATE_DONE
