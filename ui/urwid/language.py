#!/usr/bin/python
# -*- coding: utf-8 -*-
#

from ui import AbstractMenu
import urwid


# [1]: geographic zone (same one used by timezone)
# [2]: default keymap
# [3]: default timezone
# [4]: default locale

countries = {
    'America':  [ 'America', 'us',       'New_York', 'en_US'],
    'Brasil':   [ 'Brazil',  'br-abnt2', 'West',     'pt_BR'],
    'Deutsch':  [ 'Europe',  'de',       'Berlin',   'de_DE'],
    'France':   [ 'Europe',  'fr',       'Paris',    'fr_FR'],
}

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class MenuNavigatorEntry(urwid.Text):

    def __init__(self, title):
        urwid.Text.__init__(self, title, align="center")

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class LanguageMenu(Menu):

    def __init__(self):
        Menu.__init__(self)
        self._country = None

    @property
    def country(self):
        return self._country

    @country.setter
    def country(self, country):
        self._country = country
        self.ui.notify(_("selected %s as country, will set locale, timezone accordingly") % country)
        (continent, kbd, timezone, locale) = countries[country]

        # register immediate work to call loadkeys
        w = Work(self.set_kbd_layout)
        wq.put(w, PRIO_IMMEDIATE)

        # register local, kbd and timezone setting
        w1 = Work(self.set_timezone)
        w2 = Work(self.set_kbd_layout)
        w3 = Work(self.set_locale)
        wq.put([w1, w2, w3], PHASE_AFTER_ROOT)


class Menu(urwid.WidgetWrap, LanguageMenu):

    __list_kbd_layout = []
    __list_locales = []
    __list_timezones = []
    __list_zones = []

    __list_countries = None

    def __init__(self):
        AbstractMenu.__init__(self, u'Language \u2714')

        items = []

        for c in countries.keys():
            item = MenuNavigatorEntry(c)
            item = urwid.AttrMap(item, None, focus_map='reversed')
            items.append(item)

        walker = urwid.SimpleListWalker(items)
        urwid.connect_signal(walker, 'click', self.on_click)
        self.__list_countries = urwid.ListBox(walker)

        urwid.WidgetWrap.__init__(self, self.__list_countries)

    def ui_content(self):
        #return urwid.Columns([self.__list_countries])
        return urwid.Filler(self.__list_countries, 'middle', height=('relative', 40))

    def on_click(self):
        # FIXME: do the right call
        self.country = self.__list_countries.get_focus

    def set_focus(self, n):
        self.__list_countries.set_focus(n)

