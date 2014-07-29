# -*- coding: utf-8 -*-
#

import urwid


from . import StepView
from . import widgets
from installer import l10n
from installer.settings import settings


class DownloadView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self.page  = widgets.Page(_("Import package repository"))
        self._f1   = widgets.Field(_("Destination"), settings.Urpmi.distrib_dst)
        self._pile = urwid.Pile([self._f1])
        attrmap = urwid.Padding(self._pile, align='center', width=('relative', 70))
        self.page.body   = urwid.Filler(attrmap, 'middle')
        self.page.footer = widgets.Button(_("Import"), on_press=self.on_click)

    def on_click(self, button):
        if not self._f1.value:
            self.logger.error(_("You must provide a path for destination"))
            return
        self.run()
