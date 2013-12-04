# -*- coding: utf-8 -*-
#

from ui import AbstractUI
import urwid


palette = [
    (None,            'light gray', 'black'),
    ('heading',       'black',      'light gray'),
    ('line',          'black',      'light gray'),
    ('options',       'light red',       'black'),
    ('focus heading', 'white',      'dark red'),
    ('focus line',    'black',      'dark red'),
    ('focus options', 'black',      'light gray'),
    ('selected',      'white',      'dark blue'),
    ('reversed',      'standout',   '')]


def debug():
    import os, pdb
    os.system('reset')
    print 'Entering debug mode'
    pdb.set_trace()


class UrwidUI(AbstractUI):

    __loop = None
    __main_frame = None
    __page_frame = None

    header = ""
    footer = ""

    def __init__(self):
        AbstractUI.__init__(self)
        urwid.set_encoding("utf8")
        self.__load_menus() # FIXME: should be in AbstractUI class

    def __create_screen(self):
        columns  = [("weight", 0.2, self.__menu_navigator)]
        columns += [urwid.LineBox(self.__page_frame)]

        body = urwid.Columns(columns, 1)
        header = urwid.Text(self.header, wrap='clip', align='center')
        header = urwid.AttrMap(header, 'heading')
        footer = urwid.Text(self.footer, wrap='clip')
        footer = urwid.AttrMap(footer, 'footer')
        screen = urwid.Frame(body, header, footer)

        return screen

    def switch_to_menu(self, menu):
        self.__page_frame.body = menu.ui_content()
        self.redraw()

    def redraw(self):
        self.__loop.draw_screen()

    def run(self):
        # create the side menu navigator
        self.__menu_navigator = MenuNavigator(self._menus)
        self.__menu_navigator.set_focus(0)
        urwid.connect_signal(self.__menu_navigator, 'focus_changed', self.switch_to_menu)

        # create an empty menu frame
        self.__page_frame = urwid.Frame(urwid.Filler(urwid.Text("")))

        # create the main frame
        self.__main_frame = self.__create_screen()

        self.__loop = urwid.MainLoop(self.__main_frame, palette,
                                     input_filter=self.__handle_hotkeys)
        self.__loop.run()
        self.switch_to_menu(self._menus[0])

    def __load_menus(self):
        import language, welcome
        self._menus.append(welcome.Menu())
        self._menus.append(language.Menu())

    def quit(self):
        self.logger.info("Quitting, exitting mainloop")
        raise urwid.ExitMainLoop()

    def __handle_hotkeys(self, keys, raws):
        for key in keys:

            if self._hotkeys.get(key) is not None:
                self.logger.debug("Running hotkeys: %s" % key)
                self._hotkeys[key]()
                keys.remove(key)
            elif key == 'tab':
                self.__main_frame.body.focus_position ^= 1
                keys.remove('tab')

        return keys


class MenuNavigator(urwid.WidgetWrap):

    signals = ['focus_changed']

    __menus = None
    __list = None
    __linebox = None

    def __init__(self, menus):
        self.__has_focus = True
        self.__menus = menus
        items = []

        for m in self.__menus:
            item = MenuNavigatorEntry(m.name)
            item = urwid.AttrMap(item, None, focus_map='reversed')
            items.append(item)

        walker = urwid.SimpleListWalker(items)
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
        if not self.__has_focus:
            return key
        return super(MenuNavigator, self).keypress(size, key)


class MenuNavigatorEntry(urwid.Text):

    def __init__(self, title):
        urwid.Text.__init__(self, title)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key
