# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid
from urwid.command_map import ACTIVATE


class Button(urwid.WidgetWrap):
    """A plain button but with reverse focus attribute by default."""

    def __init__(self, *args, **kwargs):
        b = urwid.Button(*args, **kwargs)
        m = urwid.AttrMap(b, None, focus_map='button.active')
        urwid.WidgetWrap.__init__(self, m)


class ClickableText(urwid.WidgetWrap):
    """A button that doesn't have the marks around the label, doesn't show
    the cursor.
    """

    signals = ["click"]

    def __init__(self, txt=""):
        self._text = urwid.Text(txt)
        attrmap = urwid.AttrMap(self._text, None, focus_map='reversed')
        urwid.WidgetWrap.__init__(self, attrmap)

    @property
    def text(self):
        return self._text.text

    def selectable(self):
        return True

    def keypress(self, size, key):
        if self._command_map[key] != ACTIVATE:
            return key
        self._emit('click')

    def get_cursor_coords(self, size):
        # Disable cursor.
        return None

    def set_text(self, *args, **kwargs):
        self._text.set_text(*args, **kwargs)

    def set_layout(self, *args, **kwargs):
        self._text.set_layout(*args, **kwargs)


class ClickableTextList(urwid.WidgetWrap):

    def __init__(self, items, on_click=None, align='center'):
        self._walker = urwid.SimpleListWalker([])
        self._align = align
        self._callback = on_click
        self.update(items)
        urwid.WidgetWrap.__init__(self, urwid.ListBox(self._walker))

    def update(self, items):
        clickables = []
        for item in items:
            clickable = ClickableText(item)
            clickable.set_layout(self._align, 'clip', None)
            if self._callback:
                urwid.connect_signal(clickable, 'click', self.__on_click)
            clickables.append(clickable)
        # update walker contents once so we will trigger only one 'modified'
        # signal.
        self._walker[:] = clickables

    def set_focus(self, item):
        for clickable in self._walker:
            if clickable.text == item:
                self._walker.set_focus(self._walker.index(clickable))
                return

    # Make it private so it won't clash with callback names implemented
    # by derived classes.
    def __on_click(self, clickable):
        self._callback(clickable.text, self._walker.index(clickable))


class ClickableTextPile(urwid.WidgetWrap):

    def __init__(self, items):
        lst = []

        for i, item in enumerate(items):
            if not item:
                w = urwid.Divider('─')
            else:
                if isinstance(item, tuple):
                    txt, callback = item
                else:
                    txt, callback = (item, None)
                w = ClickableText(txt)
                if callback:
                    urwid.connect_signal(w, 'click', callback)
                w.set_layout('center', 'clip', None)
                w = urwid.AttrMap(w, None, focus_map='reversed')
            lst.append(w)

        urwid.WidgetWrap.__init__(self, urwid.Pile(lst))


class Field(urwid.WidgetWrap):

    signals = ['click', 'clear']

    def __init__(self, name, value=""):
        self._value = ClickableText(value)
        field = urwid.Text(name, layout=FillRightLayout(b'.'))
        cols = urwid.Columns([('weight', 0.9, field),
                              ('pack', urwid.Text(" : ")),
                              ('weight', 1, self._value)])
        urwid.WidgetWrap.__init__(self, cols)
        urwid.connect_signal(self._value, 'click', self._on_click)

    @property
    def value(self):
        return self._value.text

    @value.setter
    def value(self, txt):
        self._value.set_text(txt if txt else "")

    def _on_click(self, widget):
        urwid.emit_signal(self, 'click')

    def keypress(self, size, key):
        if key == "backspace" or key == "delete":
            urwid.emit_signal(self, 'clear')
            return None
        return super(Field, self).keypress(size, key)


class LimitedEdit(urwid.Edit):
    """Edit widget with a limited number of chars.

    It also sends a signal when <enter> has been pressed.
    """

    signals = ['validated']

    def __init__(self, caption, max_length=-1):
        super(LimitedEdit, self).__init__(caption, wrap='clip')
        self._max_len = max_length

    def keypress(self, size, key):
        if key == 'enter' and self.edit_text:
            urwid.emit_signal(self, "validated")
            return None

        if len(self.edit_text) == self._max_len:
            if self.valid_char(key):
                # No more room for printable chars.
                return None

        return super(LimitedEdit, self).keypress(size, key)


class Password(LimitedEdit):
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

    def __init__(self, filler=b'_'):
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


class _NullWidget(urwid.WidgetWrap):
    """A dummy widget that does nothing."""

    def __init__(self):
        urwid.WidgetWrap.__init__(self, urwid.Text(""))


_null_widget = _NullWidget()
def NullWidget():
    return _null_widget


class Page(urwid.WidgetWrap):
    """Page's body must be a box widget whereas footer and title
    should be flow widgets.
    """
    def __init__(self, title=""):
        self.title   = title
        self._body   = urwid.WidgetPlaceholder(urwid.Filler(NullWidget()))
        self._footer = urwid.WidgetPlaceholder(NullWidget())

        items = [
            ('pack', urwid.Divider(" ")),
            ('weight', 1, self._body),
            ('pack', self._footer)
        ]
        self._pile = urwid.Pile(items, focus_item=1)
        urwid.WidgetWrap.__init__(self, urwid.WidgetPlaceholder(self._pile))

    @property
    def body(self):
        if self._body.original_widget != NullWidget():
            return self._body.original_widget

    @body.setter
    def body(self, widget=None):
        if not widget:
            widget = NullWidget()
        self._body.original_widget = widget

    @property
    def footer(self):
        if self._footer.original_widget != NullWidget():
            return self._footer.original_widget

    @footer.setter
    def footer(self, widget=None):
        if not widget:
            widget = NullWidget()
        self._footer.original_widget = widget

    def set_focus(self, what):
        if what == 'footer':
            self._pile.focus_position = 2
        else:
            self._pile.focus_position = 1


class Table(urwid.WidgetWrap):

    def __init__(self, columns):
        """columns : (widget, alignment, width) """
        self._widths = []
        self._alignments = []
        self._numsep = 1
        self._walker = urwid.SimpleListWalker([])

        # build the table header
        items = []
        for name, align, width in columns:
            if width < len(name):
                width = len(name)
            items.append((width, urwid.Text(name, wrap='clip', align=align)))
            self._widths.append(width)
            self._alignments.append(align)

        self._walker.append(urwid.Columns(items, dividechars=self._numsep))
        self._walker.append(urwid.Divider('─'))

        # build the content of the table
        listbox = urwid.ListBox(self._walker)
        table_width = (sum(self._widths) + self._numsep * (len(self._widths)-1))
        urwid.WidgetWrap.__init__(self, urwid.Padding(listbox, width=table_width))

    def append_row(self, cols):
        for i, w in enumerate(cols):
            cols[i] = urwid.Padding(w, self._alignments[i], 'pack')
        self._walker.append(urwid.Columns(zip(self._widths, cols),
                                          dividechars=self._numsep))

    def get_focus(self):
        """Returns the row (list of widget) which has the focus"""
        cols = self._walker.get_focus()[0]
        return [padding.original_widget for padding, options in cols.contents]

    def set_focus(self, index):
        # Skip the table header.
        if index < 0:
            index = len(self._walker) + index - 2
        self._walker.set_focus(index + 2)
