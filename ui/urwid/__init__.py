# -*- coding: utf-8 -*-
#

import os
import time
import collections
import logging
import urwid
from ui import UI
from menus import BaseMenu
import widgets


palette = [
#    (None,                    'light gray',        'black'),
    ('line',                  'black',             'light gray'),
    ('title1',                'bold',              ''),
    ('options',               'light red',         'black'),
    ('focus heading',         'white',             'dark red'),
    ('focus line',            'black',             'dark red'),
    ('focus options',         'black',             'light gray'),
    ('list.entry.disabled',   'dark blue',         ''),
    ('side.bar.mark.cross',   'light red',         ''),
    ('side.bar.mark.check',   'dark green',        ''),
    ('top.bar.label',         'black',             'light gray'),
    ('top.bar.hotkey',        'dark blue',         'light gray'),
    ('sum.section',           'underline',         ''),
    ('progress.bar',          'black',             'dark green'),
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
    __menu_page  = None
    __menu_navigator = None
    __top_bar = None
    __echo_area = None

    def __init__(self, installer, lang):
        self._watch_pipe_fd = None
        self._watch_pipe_queue = collections.deque()
        UI.__init__(self, installer, lang)
        urwid.set_encoding("utf8")

    def _load_menus(self):
        # FIXME: modules loading should be in abstract class.
        import welcome, license, installation, exit
        from menus.welcome import WelcomeMenu
        from menus.license import LicenseMenu
        from menus.installation import InstallMenu
        from menus.exit import ExitMenu

        view = welcome.Menu(self)
        menu = WelcomeMenu(self, view)
        self._menus.append(menu)

        view = license.Menu(self)
        menu = LicenseMenu(self, view)
        self._menus.append(menu)

        view = installation.Menu(self)
        menu = InstallMenu(self, view)
        self._menus.append(menu)

        view = exit.Menu(self)
        menu = ExitMenu(self, view)
        self._menus.append(menu)

    def __create_menu_page(self):
        self.__menu_page = urwid.WidgetPlaceholder(urwid.Text(""))

    def __create_menu_navigator(self):
        self.__menu_navigator = MenuNavigator(self._menus)

        def on_focus_changed(menu):
            self._switch_to_menu(menu)
        urwid.connect_signal(self.__menu_navigator, 'focus_changed', on_focus_changed)

    def __create_main_frame(self):
        cols  = [("weight", 0.2, self.__menu_navigator)]
        cols += [urwid.LineBox(self.__menu_page)]
        cols  = urwid.Columns(cols, dividechars=1, focus_column=1)

        self.__main_frame = urwid.Frame(cols, self.__top_bar, self.__echo_area)

    def __create_echo_area(self):
        self.__echo_area = EchoArea()

    def __create_top_bar(self):
        self.__top_bar = TopBar()

    def __init_watch_pipe(self):

        def watch_pipe_cb(unused):
            while self._watch_pipe_queue:
                func = self._watch_pipe_queue.pop()
                func()
            # make sure the pipe read side won't be closed.
            return True

        self._watch_pipe_fd = self.__loop.watch_pipe(watch_pipe_cb)

    def __call(self, func):
        if self._watch_pipe_fd:
            self._watch_pipe_queue.appendleft(func)
            os.write(self._watch_pipe_fd, "ping")
        else:
            # Used only during initialisation.
            func()

    def suspend(self):
        raise NotImplementedError()

    def run(self):
        self.__create_menu_navigator()
        self.__create_menu_page()
        self.__create_top_bar()
        self.__create_echo_area()
        self.__create_main_frame()

        self._switch_to_first_menu()

        def toggle_menu_page_focus():
            self.__main_frame.body.focus_position ^= 1
        self.register_hotkey('tab', toggle_menu_page_focus)
        self.register_hotkey('f1', self._switch_to_menu)
        self.register_hotkey('f2', self._switch_to_summary)
        self.register_hotkey('f3', self._switch_to_logs)
        self.register_hotkey('f4', self._switch_to_help)
        self.register_hotkey('f5', self.quit)

        self.__loop = urwid.MainLoop(self.__main_frame, palette,
#                                     event_loop=urwid.GLibEventLoop(),
                                     input_filter=self._handle_hotkeys,
                                     unhandled_input=self.handle_key)
        self.__init_watch_pipe()
        self.__loop.run()

    def _switch_to_menu(self, menu=None):
        UI._switch_to_menu(self, menu)
        self.__menu_page.original_widget = self._current_menu.view

    def _switch_to_summary(self):
        self.__menu_page.original_widget = SummaryPage(self.installer.data)

    def _switch_to_help(self):
        self.__menu_page.original_widget = HelpPage()

    def _switch_to_logs(self):
        self.__menu_page.original_widget = LogPage(self.logs)

    def _handle_hotkeys(self, keys, raws):
        self.__echo_area.clear()
        for key in keys:
            if self.handle_hotkey(key):
                keys.remove(key)
        return keys

    def ui_thread(func):
        """This decorator is used to make sure that decorated
        functions will be executed by the UI thread. Even if the
        current thread is the UI one, we still serialize the func call
        so they're executed in order.
        """
        def wrapper(self, *args):
            self.__call(lambda: func(self, *args))
        return wrapper

    @ui_thread
    def quit(self, delay=0):
        UI._quit(self)
        time.sleep(delay)
        raise urwid.ExitMainLoop()

    @ui_thread
    def redraw(self):
        if self.__loop:
            self.__top_bar.refresh()
            self.__menu_navigator.refresh()
            self.__loop.draw_screen()
            self._switch_to_next_menu()

    @ui_thread
    def set_completion(self, percent, view):
        view.set_completion(percent)

    @ui_thread
    def notify(self, lvl, msg):
        if self.__echo_area:
            self.__echo_area.notify(lvl, msg)


class UrwidMenu(urwid.WidgetWrap):

    def __init__(self, ui):
        self._ui = ui
        self._page = urwid.WidgetPlaceholder(urwid.Text(""))
        self._progressbar = widgets.ProgressBar(0, 100)
        self._overlay = urwid.Overlay(self._progressbar, self._page,
                                      'center', ('relative', 55),
                                      'middle', 'pack')

        urwid.WidgetWrap.__init__(self, urwid.WidgetPlaceholder(self._page))

    @property
    def logger(self):
        return self._ui.logger

    @property
    def page(self):
        return self._page.original_widget

    @page.setter
    def page(self, page):
        self._page.original_widget = page

    def redraw(self):
        return

    def ready(self):
        self._ui.on_view_event(self)

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


class LogPage(urwid.WidgetWrap):

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


class SummaryPage(urwid.WidgetWrap):

    def __init__(self, data):
        items = []

        parent = ""
        keys = data.keys()
        keys.sort()

        for k in keys:
            if parent != k.split('/', 1)[0]:
                parent = k.split('/', 1)[0]
                items.append(urwid.Divider(" "))
                items.append(urwid.Text(('sum.section', parent)))

            child = "    " + k.split('/', 1)[1]
            child = urwid.Text(child, layout=widgets.FillRightLayout('.'))
            col = urwid.Columns([('weight', 0.6, child),
                                 ('weight', 1, urwid.Text(data[k]))])
            items.append(col)

        walker = urwid.SimpleListWalker(items)
        super(SummaryPage, self).__init__(urwid.ListBox(walker))


class HelpPage(urwid.WidgetWrap):

    def __init__(self):
        txt = urwid.Text("Not Yet Implemented", align='center')
        txt = urwid.Filler(txt)
        super(HelpPage, self).__init__(txt)


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

    def __init__(self, menus):
        self._menus = menus

        items = []
        for menu in self._menus:
            items.append(MenuNavigatorEntry(menu))
        walker = urwid.SimpleListWalker(items)
        self._walker = walker

        urwid.connect_signal(walker, 'modified', self.__on_focus_changed)
        self._list = urwid.ListBox(walker)
        super(MenuNavigator, self).__init__(urwid.LineBox(self._list))

    def __on_focus_changed(self):
        widget, index = self.get_focus()
        urwid.emit_signal(self, "focus_changed", self._menus[index])

    def get_focus(self):
        return self._list.get_focus()

    def set_focus(self, n):
        self._list.set_focus(n)

    def keypress(self, size, key):
        return super(MenuNavigator, self).keypress(size, key)

    def refresh(self):
        for e in self._walker:
            e.refresh()


class MenuNavigatorEntry(urwid.WidgetWrap):

    check_mark_markup = ('side.bar.mark.check', u'\u2714')
    cross_mark_markup = ('side.bar.mark.cross', u'\u2718')

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
            title = ('list.entry.disabled', title)

        self._title.set_text(title)
        self._mark.set_text(mark)


class TopBar(urwid.WidgetWrap):

    def __init__(self):
        self._text = urwid.Text("")
        attrmap = urwid.AttrMap(self._text, 'top.bar.label')
        urwid.WidgetWrap.__init__(self, attrmap)
        self.refresh()

    def refresh(self):
        items = [_("Main"), _("Summary"), _("Logs"), _("Help"), _("Exit")]
        txt = []
        for (i, item) in enumerate(items, 1):
            if i > 1:
                txt.append("  ")
            txt.append(('top.bar.hotkey', "F"+str(i)+" "))
            txt.append(item)
        self._text.set_text(txt)

