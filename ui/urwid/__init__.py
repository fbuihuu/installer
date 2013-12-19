# -*- coding: utf-8 -*-
#

import logging
import urwid
from ui import UI
#from installer import installer


palette = [
    (None,                    'light gray',        'black'),
    ('heading',               'black',             'light gray'),
    ('line',                  'black',             'light gray'),
    ('options',               'light red',         'black'),
    ('focus heading',         'white',             'dark red'),
    ('focus line',            'black',             'dark red'),
    ('focus options',         'black',             'light gray'),
    ('selected',              'white',             'dark blue'),
    ('mark_ko',               'light red',         ''),
    ('mark_ok',               'dark green',        ''),
    ('entry.disabled',        'dark blue',         ''),
    ('top.bar.hotkey',        'dark blue',         'light gray'),
    ('log.warn',              'light red',         ''),
    ('log.info',              'light green',       ''),
    ('reversed',              'standout',          '')]


def debug():
    import os, pdb
    os.system('reset')
    print 'Entering debug mode'
    pdb.set_trace()


class UrwidUI(UI):

    __loop = None
    __main_frame = None
    __menu_frame = None
    __menu_page  = None
    __menu_navigator = None
    __top_bar = None

    header = ""
    footer = ""

    def __init__(self, installer):
        UI.__init__(self, installer)
        urwid.set_encoding("utf8")

    def _load_menus(self):
        # FIXME: modules loading should be in abstract class.
        import welcome, licence
        self._menus.append(welcome.Menu(self, self.on_menu_event))
        self._menus.append(licence.Menu(self, self.on_menu_event))

    def __create_menu_page(self):
        self.__menu_frame = urwid.Frame(urwid.Filler(urwid.Text("")))
        columns  = [("weight", 0.2, self.__menu_navigator)]
        columns += [urwid.LineBox(self.__menu_frame)]
        self.__menu_page = urwid.Columns(columns, dividechars=1)

    def __create_menu_navigator(self):
        self.__menu_navigator = MenuNavigator(self._menus)

        def on_focus_changed(menu):
            self.__menu_frame.body = menu.ui_content
        urwid.connect_signal(self.__menu_navigator, 'focus_changed', on_focus_changed)

    def __create_main_frame(self):
        header = urwid.AttrMap(self.__top_bar, 'heading')
        footer = self.__echo_area
        self.__main_frame = urwid.Frame(self.__menu_page, header, footer)

    def __create_echo_area(self):
        self.__echo_area = EchoArea()

    def __create_top_bar(self):
        self.__top_bar = TopBar(["Main", "Summary", "Logs", "About"])

    def redraw(self):
        self.__loop.draw_screen()

    def notify(self, lvl, msg):
        self.__echo_area.notify(lvl, msg)

    def quit(self, delay=0):
        if delay:
            import time
            # flush any pending screen changes before sleeping.
            self.redraw()
            time.sleep(delay)
        raise urwid.ExitMainLoop()

    def suspend(self):
        # see ovirt, ui/urwid_builder.py, suspended() method.
        raise NotImplementedError()

    def run(self):
        self.__create_menu_navigator()
        self.__create_menu_page()
        self.__create_top_bar()
        self.__create_echo_area()
        self.__create_main_frame()

        self.switch_to_first_menu()

        def toggle_menu_page_focus():
            self.__menu_page.focus_position ^= 1
        self.register_hotkey('tab', toggle_menu_page_focus)
        self.register_hotkey('f1', self.switch_to_menu)
        self.register_hotkey('f3', self.switch_to_logs)

        self.__loop = urwid.MainLoop(self.__main_frame, palette,
                                     input_filter=self.filter_input)
        self.__loop.run()

    def on_menu_event(self, menu):
        UI.on_menu_event(self, menu)
        self.__menu_navigator.refresh()
        self.switch_to_next_menu()

    def _switch_to_menu(self, menu):
        self.__menu_navigator.set_focus(self._menus.index(menu))

    def switch_to_logs(self):
        self.__menu_frame.body = LogFrame(self.logs)

    def __handle_hotkeys(self, keys, raws):
        for key in keys:
            if self.handle_hotkey(key):
                keys.remove(key)
        return keys

    def filter_input(self, keys, raws):
        self.__echo_area.clear()
        self.__handle_hotkeys(keys, raws)
        return keys


class LogFrame(urwid.WidgetWrap):

    def __init__(self, logs):
        items = []
        for (lvl, msg) in logs:
            txt = urwid.Text(msg)
            if lvl > logging.INFO:
                txt = urwid.AttrMap(txt, 'log.warn')
            items.append(txt)

        if not items:
            w = urwid.Filler(urwid.Text(""))
        else:
            w = urwid.ListBox(items)

        urwid.WidgetWrap.__init__(self, w)


class EchoArea(urwid.Text):

    def __init__(self):
         urwid.Text.__init__(self, "")

    def notify(self, lvl, msg):
        if lvl > logging.INFO:
            markup = ('log.warn', msg)
        elif lvl == logging.INFO:
            markup = ('log.info', msg)
        else:
            markup = msg
        self.set_text(markup)

    def clear(self):
        self.set_text("")


class MenuNavigator(urwid.WidgetWrap):

    signals = ['focus_changed']

    __menus = None
    __list  = None
    __linebox = None

    def __init__(self, menus):
        self.__menus = menus

        items = []
        for menu in self.__menus:
            items.append(MenuNavigatorEntry(menu))
        walker = urwid.SimpleListWalker(items)
        self.__walker = walker

        urwid.connect_signal(walker, 'modified', self.__on_focus_changed)
        self.__list = urwid.ListBox(walker)
        self.__linebox = urwid.LineBox(self.__list)
        super(MenuNavigator, self).__init__(self.__linebox)

    def __on_focus_changed(self):
        widget, index = self.get_focus()
        urwid.emit_signal(self, "focus_changed", self.__menus[index])

    def get_focus(self):
        return self.__list.get_focus()

    def set_focus(self, n):
        self.__list.set_focus(n)

    def keypress(self, size, key):
        return super(MenuNavigator, self).keypress(size, key)

    def refresh(self):
        for e in self.__walker:
            e.refresh()


class MenuNavigatorEntry(urwid.WidgetWrap):

    check_mark_markup = ('mark_ok', u'\u2714')
    cross_mark_markup = ('mark_ko', u'\u2718')

    def __init__(self, menu):
        self._menu  = menu
        self._title = urwid.Text("", align="left")
        self._mark  = urwid.Text("", align="right")
        self.refresh()

        columns = urwid.Columns([self._title, (1, self._mark)])
        columns = urwid.AttrMap(columns, None, focus_map='reversed')
        super(MenuNavigatorEntry, self).__init__(columns)

    def selectable(self):
        return self._menu.is_enabled()

    def keypress(self, size, key):
        return key

    def refresh(self):
        title = self._menu.name
        mark = ""
        if self._menu.is_enabled():
            if self._menu.is_done():
                mark = self.check_mark_markup
            elif self._menu.is_failed():
                mark = self.cross_mark_markup
        else:
            title = ('entry.disabled', title)

        self._title.set_text(title)
        self._mark.set_text(mark)


class TopBar(urwid.WidgetWrap):

    def __init__(self, menus):
        items = []
        for (i, menu) in enumerate(menus, 1):
            if i > 1:
                items.append("  ")
            items.append(('top.bar.hotkey', "F"+str(i)+" "))
            items.append(menu)

        bar = urwid.Text(items)
        urwid.WidgetWrap.__init__(self, bar)
