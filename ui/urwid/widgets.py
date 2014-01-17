# -*- coding: utf-8 -*-
#
import urwid
from urwid.command_map import ACTIVATE


class Title1(urwid.WidgetWrap):

    def __init__(self, title="", align='center'):
        self._text = urwid.Text(title, align=align)
        urwid.WidgetWrap.__init__(self, urwid.AttrMap(self._text, 'title1'))

    def set_text(self, txt):
        self._text.set_text(txt)


class ClickableText(urwid.SelectableIcon):

    signals = ["click"]

    def __init__(self, txt=None):
        if not txt:
            txt = ""
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
            if on_click:
                urwid.connect_signal(txt, 'click', on_click)
            lst.append(urwid.AttrMap(txt, None, focus_map='reversed'))

        self._walker = urwid.SimpleListWalker(lst)
        urwid.WidgetWrap.__init__(self, urwid.ListBox(self._walker))


class FillRightLayout(urwid.StandardTextLayout):

    def __init__(self, filler='_'):
        self._filler = filler
        urwid.StandardTextLayout.__init__(self)

    def layout(self, text, width, align, wrap):
        s = urwid.StandardTextLayout.layout(self, text, width, align, wrap)
        out = []
        last_offset = 0
        for row in s:
            used = 0
            for seg in row:
                used += seg[0]
                if len(seg) == 3:
                    last_offset = seg[2]
            if used == width:
                out.append(row)
                continue
            fill = width - used
            out.append(row + [(fill, last_offset, self._filler * fill)])
        return out


class ProgressBar(urwid.WidgetWrap):

    def __init__(self, current, done):
        self._progressbar = urwid.ProgressBar(None, "progress.bar",
                                              current, done)
        linebox = urwid.LineBox(self._progressbar)
        urwid.WidgetWrap.__init__(self, linebox)

    def set_completion(self, current):
        self._progressbar.set_completion(current)


class Page(urwid.WidgetWrap):

    empty_text_widget = urwid.Text("")

    def __init__(self):
        self._title  = Title1()
        self._body   = urwid.WidgetPlaceholder(self.empty_text_widget)
        self._footer = urwid.WidgetPlaceholder(self.empty_text_widget)

        items = [
            ('pack', self._title),
            ('pack', urwid.Divider(" ")),
            ('weight', 1, self._body),
            ('pack', self._footer)
        ]
        self._pile = urwid.Pile(items, focus_item=2)
        urwid.WidgetWrap.__init__(self, urwid.WidgetPlaceholder(self._pile))

    @property
    def title(self):
        return title.text

    @title.setter
    def title(self, txt):
        self._title.set_text(txt)

    @property
    def body(self):
        if self._body.original_widget == self.empty_text_widget:
            return None
        return self._body.original_widget

    @body.setter
    def body(self, widget=None):
        if not widget:
            widget = self.empty_text_widget
        self._body.original_widget = widget

    @property
    def footer(self):
        if self._footer.original_widget == self.empty_text_widget:
            return None
        return self._footer.original_widget

    @footer.setter
    def footer(self, widget=None):
        if not widget:
            widget = self.empty_text_widget
        self._footer.original_widget = widget


class MenuWidget(urwid.WidgetWrap):

    def __init__(self, ui):
        self.ui = ui
        self._page = urwid.WidgetPlaceholder(urwid.Text(""))
        self._progressbar = ProgressBar(0, 100)

        self._overlay = urwid.Overlay(self._progressbar, self._page,
                                      'center', ('relative', 55),
                                      'middle', 'pack')

        urwid.WidgetWrap.__init__(self, urwid.WidgetPlaceholder(self._page))

    @property
    def page(self):
        return self._page.original_widget

    @page.setter
    def page(self, page):
        self._page.original_widget = page

    def redraw(self):
        return

    def set_completion(self, percent):
        #
        # Hide the progress bar when the menu's job is not yet started or
        # is finished.
        #
        if percent < 1 or percent > 99:
            self._w.original_widget = self._page
            return
        #
        # Create an overlay to show a progress bar on top if it
        # doesn't exist yet.
        #
        if self._w.original_widget == self._page:
            self._w.original_widget = self._overlay

        self._progressbar.set_completion(percent)
        self.ui.redraw()

