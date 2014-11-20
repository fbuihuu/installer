# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid

from . import StepView
from . import widgets
from installer.settings import settings


class PasswordView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self._masked = False

        self.page = widgets.Page(_("Enter the root password"))

        self._passwd1 = widgets.Password(_("Password : "))
        self._passwd2 = widgets.Password(_("Confirm  : "))
        self._pile = urwid.Pile([self._passwd1, self._passwd2])
        attrmap = urwid.Padding(self._pile, align='center', width=('relative', 70))
        self.page.body = urwid.Filler(attrmap, 'middle')
        self.page.footer = urwid.AttrMap(urwid.Text(""), 'page.legend')
        self._update_footer()

        urwid.connect_signal(self._passwd1, 'validated', self._on_validated)
        urwid.connect_signal(self._passwd2, 'validated', self._on_validated)

    def _update_footer(self):
        if self._masked:
            txt = _("Press <alt>-v to hide password")
        else:
            txt = _("Press <alt>-v to show password")
        self.page.footer.original_widget.set_text(txt)

    def _on_validated(self):
        p1 = self._passwd1.edit_text
        p2 = self._passwd2.edit_text

        if not p1:
            self._pile.focus_position = 0
        elif not p2:
            self._pile.focus_position = 1
        elif p1 == p2:
            # password section may not exist yet, so use set().
            settings.set('Password', 'root', p1)
            self.run()
        else:
            self.logger.error(_("passwords mismatch"))

    def keypress(self, size, key):
        if key == 'meta v':
            self._masked = not self._masked
            self._passwd1.set_masked(self._masked)
            self._passwd2.set_masked(self._masked)
            self._update_footer()
            return None
        return super(PasswordView, self).keypress(size, key)
