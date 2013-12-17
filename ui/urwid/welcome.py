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

    provides = ["language"]

    __list_kbd_layout = []
    __list_locales = []
    __list_timezones = []
    __list_zones = []

    __list_countries = None

    def __init__(self, menu_event_cb=None):
        menu.Menu.__init__(self, u"Language", menu_event_cb)

        items = []

        for c in country_dict.keys():
            item = MenuNavigatorEntry(c)
            items.append(item)
            urwid.connect_signal(item, 'click', self.on_click)

        walker = urwid.SimpleListWalker(items)
        self.__list_countries = urwid.ListBox(walker)
        self.__list_countries = urwid.Filler(self.__list_countries, 'middle', height=('relative', 40))
        #self.__list_countries = urwid.Padding(self.__list_countries, align='right')

        header = urwid.Text(u"Select your location", align='center')

        frame = urwid.Padding(urwid.Frame(self.__list_countries, header), 'center')
        urwid.WidgetWrap.__init__(self, frame)

    def ui_content(self):
        #return urwid.Columns([self.__list_countries])
        #return urwid.Filler(self.__list_countries, 'middle', height=('relative', 40))
        return self

    def on_click(self, entry):
        self.country = entry.name

    def set_focus(self, n):
        self.__list_countries.set_focus(n)
