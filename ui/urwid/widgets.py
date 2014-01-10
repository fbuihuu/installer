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
