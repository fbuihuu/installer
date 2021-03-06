# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid

from . import StepView
from . import widgets
from installer import l10n
from installer.settings import settings



class SelectionListWidget(widgets.ClickableTextList):

    signals = ['click']

    def __init__(self):
        super(SelectionListWidget, self).__init__([], self._on_click, 'left')

    def _on_click(self, tz, idx):
        urwid.emit_signal(self, "click", tz)

    def update(self, items, prefix=None):
        if prefix:
            items = [item for item in items if item.startswith(prefix)]
        self._items = items
        widgets.ClickableTextList.update(self, items)

    def get_focus(self):
        widget, idx = self._walker.get_focus()
        return self._items[idx]

    def set_focus(self, tz):
        self._walker.set_focus(self._items.index(tz))


class SelectionPage(widgets.Page):

    signals = ['done']

    def __init__(self, list_widget, title):
        widgets.Page.__init__(self, title)
        self._show_all   = False
        self._lst_widget = list_widget
        urwid.connect_signal(self._lst_widget, 'click', self._on_selected)
        body = urwid.Filler(self._lst_widget, 'middle', height=('relative', 70))
        body = urwid.Padding(body, 'center', width=('relative', 60))
        self.body   = body
        self.footer = urwid.AttrMap(urwid.Text(""), 'page.legend')

    def _redraw_footer(self):
        if self._show_all:
            txt = _('Press <alt>-v to minimize the list')
        else:
            txt = _('Press <alt>-v to show them all')
        self.footer.original_widget.set_text(txt)

    def redraw(self):
        self._redraw_body()
        self._redraw_footer()

    def keypress(self, size, key):
        if key == 'meta v':
            self._show_all = not self._show_all
            self.redraw()
            return None
        if key == 'esc':
            urwid.emit_signal(self, "done")
        return super(SelectionPage, self).keypress(size, key)


class TimezoneSelectionPage(SelectionPage):

    def __init__(self):
        SelectionPage.__init__(self, SelectionListWidget(),
                               _('Select a time zone'))

    def _on_selected(self, tz):
        settings.Localization.timezone = tz
        urwid.emit_signal(self, "done")

    def _redraw_body(self):
        prefix = None
        if not self._show_all and '/' in settings.Localization.timezone:
            prefix = settings.Localization.timezone.split('/')[0]
        self._lst_widget.update(l10n.timezones, prefix)
        self._lst_widget.set_focus(settings.Localization.timezone)


class KeymapSelectionPage(SelectionPage):

    def __init__(self):
        SelectionPage.__init__(self, SelectionListWidget(),
                               _('Select a keyboard layout'))

    def _on_selected(self, kmap):
        settings.Localization.keymap = kmap
        urwid.emit_signal(self, "done")

    def _redraw_body(self):
        prefix = None if self._show_all else settings.Localization.keymap
        self._lst_widget.update(l10n.keymaps, prefix)
        self._lst_widget.set_focus(settings.Localization.keymap)


class LocalizationPage(widgets.Page):

    signals = ['done', 'timezone', 'keymap']

    def __init__(self):
        widgets.Page.__init__(self, _('Localization'))

        self._timezone = widgets.Field(_('Time Zone'))
        self._keymap   = widgets.Field(_('Keyboard Layout'))
        body = urwid.Pile([self._timezone, self._keymap])
        body = urwid.Padding(body, 'center', ('relative', 90))
        self.body   = urwid.Filler(body, 'middle')
        self.footer = widgets.Button(_('Done'), on_press=self._done)
        self.set_focus('footer')

        urwid.connect_signal(self._timezone, 'click', self._on_timezone_click)
        urwid.connect_signal(self._keymap, 'click', self._on_keymap_click)

    def redraw(self):
        self._timezone.value = settings.Localization.timezone
        self._keymap.value   = settings.Localization.keymap

    def _on_timezone_click(self):
        urwid.emit_signal(self, 'timezone')

    def _on_keymap_click(self):
        urwid.emit_signal(self, 'keymap')

    def _done(self, w):
        urwid.emit_signal(self, 'done')


class LocalizationView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self._main_page = LocalizationPage()
        urwid.connect_signal(self._main_page, 'done', self._do_localization)
        urwid.connect_signal(self._main_page, 'timezone', self._on_setup_tz)
        urwid.connect_signal(self._main_page, 'keymap', self._on_setup_kmap)

        self._timezone_page = TimezoneSelectionPage()
        urwid.connect_signal(self._timezone_page, 'done', self._on_tz_done)

        self._keymap_page = KeymapSelectionPage()
        urwid.connect_signal(self._keymap_page, 'done', self._on_kmap_done)

        self.page = self._main_page

    def _redraw(self):
        # timezones/keymaps has been populated during the installation
        # step and timezone/keymap settings have been initialized
        # during the language step.
        self._keymap_page.redraw()
        self._timezone_page.redraw()
        self._main_page.redraw()

    def _on_tz_done(self):
        self._main_page.redraw()
        self.page = self._main_page

    def _on_kmap_done(self):
        self._main_page.redraw()
        self.page = self._main_page

    def _on_setup_tz(self):
        self.page = self._timezone_page

    def _on_setup_kmap(self):
        self.page = self._keymap_page

    def _do_localization(self):
        self.run()
