#!/usr/bin/python
# -*- coding: utf-8 -*-
#

from menus import BaseMenu
import widgets
import urwid
from urwid.command_map import ACTIVATE
import system
from l10n import country_dict

#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class Menu(BaseMenu):

    provides = ["language"]

    def __init__(self, ui, callback_event):
        BaseMenu.__init__(self, ui, callback_event)
        self._country = None
        if self.installer.data["localization/country"]:
            self.country = self.installer.data["localization/country"]

    @property
    def name(self):
        return _("Language")

    @property
    def country(self):
        return self._country

    @country.setter
    def country(self, place):
        self._country = place
        self.installer.data["localization/country"] = place

        # Change the language of the whole ui.
        lang = self.installer.data["localization/locale"]
        self.ui.language = lang

        # Switch the keyboard layout accordingly.
        layout = self.installer.data["localization/keyboard"]
        # if system.keyboard.get_layout() != layout:
        #  self.logger.info(_("switching keyboard layout to %s") % layout)
        #   system.keyboard.set_layout(layout)

        self.state = Menu._STATE_DONE
        self.redraw()

    def redraw(self):
        self._widget.title = _("Select your location")

    def _create_widget(self):
        page = widgets.Page()
        # Make the list centered inside its container
        body = widgets.ClickableTextList(country_dict.keys(), self.on_click)
        body = urwid.Filler(body, 'middle', height=('relative', 40))
        page.body = urwid.Padding(body, align='center', width=('relative', 60))

        self._widget = page

    def on_click(self, entry):
        place = entry.text
        if self.country != place:
            self.country = place
            self.logger.info(_("set location to %s"), place)
