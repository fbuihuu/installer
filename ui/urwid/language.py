#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import menu
import urwid
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


class Menu(urwid.WidgetWrap, menu.Menu):

    requires = ["licence"]
    provides = ["language"]

    __list_kbd_layout = []
    __list_locales = []
    __list_timezones = []
    __list_zones = []

    __list_countries = None

    def __init__(self, callback_event=None):
        menu.Menu.__init__(self, u"Language", callback_event)

        items = []

        for c in country_dict.keys():
            item = MenuNavigatorEntry(c)
            items.append(item)
            urwid.connect_signal(item, 'click', self.on_click)

        walker = urwid.SimpleListWalker(items)
        self.__list_countries = urwid.ListBox(walker)

        urwid.WidgetWrap.__init__(self, self.__list_countries)

    def ui_content(self):
        #return urwid.Columns([self.__list_countries])
        return urwid.Filler(self.__list_countries, 'middle', height=('relative', 40))

    def on_click(self, entry):
        self.country = entry.name

    def set_focus(self, n):
        self.__list_countries.set_focus(n)
