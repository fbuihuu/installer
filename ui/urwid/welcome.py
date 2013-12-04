#!/usr/bin/python
# -*- coding: utf-8 -*-
#

from ui import AbstractMenu
import urwid

class Menu(AbstractMenu):

    def __init__(self, notify):
        AbstractMenu.__init__(self, u"Welcome  \u2718")

    def ui_content(self):
        return urwid.Filler(urwid.Text(self._title, align='center'))
