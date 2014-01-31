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


class Field(urwid.Edit):
    """Edit widget with a limited number of chars.

    It also sends a signal when <enter> has been pressed.
    """

    signals = ['validated']

    def __init__(self, caption, max_length=-1):
        super(Field, self).__init__(caption, wrap='clip')
        self._max_len = max_length

    def keypress(self, size, key):
        if key == 'enter' and self.edit_text:
            urwid.emit_signal(self, "validated")
            return None

        if len(self.edit_text) == self._max_len:
            if self.valid_char(key):
                # No more room for printable chars.
                return None

        return super(Field, self).keypress(size, key)


class Password(Field):
    """An EditBox widget initialize to match password requierements"""

    default_mask = u'\u2022' # bullet

    def __init__(self, caption):
        self._is_masked = False
        self._mask = self.default_mask
        self._saved_mask = self._mask
        super(Password, self).__init__(caption, 32)
        self.set_mask(self.default_mask)

    def is_masked(self):
        return self._is_masked

    def set_masked(self, masked):
        if masked != self.is_masked():
            if masked:
                self._saved_mask = self._mask
                super(Password, self).set_mask(None)
            else:
                super(Password, self).set_mask(self._saved_mask)
            self._is_masked = masked

    def set_mask(self, mask):
        if self.is_masked():
            self._saved_mask = mask
        else:
            super(Password, self).set_mask(mask)


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
