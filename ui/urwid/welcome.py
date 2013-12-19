#!/usr/bin/python
# -*- coding: utf-8 -*-
#

import menu
import urwid
from urwid.command_map import ACTIVATE
import system
from localisation import country_dict

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class ClickableText(urwid.SelectableIcon):

    signals = ["click"]

    def __init__(self, txt):
        urwid.SelectableIcon.__init__(self, txt, -1)

    def keypress(self, size, key):
        if self._command_map[key] != ACTIVATE:
            return key
        self._emit('click')

    def get_cursor_coords(self, size):
        # Disable cursor.
        return None


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

    def __init__(self, ui, callback_event):
        menu.Menu.__init__(self, _("Language"), ui, callback_event)
        self._country = None
        if self.installer.data["location/country"]:
            self.country = self.installer.data["location/country"]

    @property
    def country(self):
        return self._country

    @country.setter
    def country(self, place):
        self._country = place
        self.installer.data["location/country"] = place
        self.state = Menu._STATE_DONE

    def build_ui_content(self):
        header = urwid.Text(_("Select your location"), align='center')
        body = ClickableTextList(country_dict.keys(), self.on_click)
        # Make the list centered inside its containers
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body, align='center', width=('relative', 30))

        return urwid.Frame(body, header)

    def on_click(self, entry):
        place = entry.text
        if self.country != place:
            self.country = place
            self.logger.info(_("Set location to %s"), place)
