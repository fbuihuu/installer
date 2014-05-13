# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer.settings import settings


class PasswordView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self._masked = False

        self.page = widgets.Page()

        self._passwd1 = widgets.Password(_("Password : "))
        self._passwd2 = widgets.Password(_("Confirm  : "))
        self._pile = urwid.Pile([self._passwd1, self._passwd2])
        attrmap = urwid.Padding(self._pile, align='center', width=('relative', 70))
        self.page.body = urwid.Filler(attrmap, 'middle')

        footer = urwid.Text("")
        self.page.footer = urwid.AttrMap(footer, 'list.entry.disabled')

        urwid.connect_signal(self._passwd1, 'validated', self._on_validated)
        urwid.connect_signal(self._passwd2, 'validated', self._on_validated)

    def redraw(self):
        self.page.title = _("Enter the root password")

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
            settings.password.root = p1
            self.run()
        else:
            self.logger.error(_("passwords mismatch"))

    def keypress(self, size, key):
        if key == 'meta v':
            self._masked = not self._masked
            self._passwd1.set_masked(self._masked)
            self._passwd2.set_masked(self._masked)
            self.redraw() # update the footer message
            return None
        return super(PasswordView, self).keypress(size, key)
