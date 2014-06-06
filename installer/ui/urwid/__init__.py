# -*- coding: utf-8 -*-
#

import os
import sys
import time
import collections
import logging
import urwid
from importlib import import_module

from installer.settings import settings
from installer import steps
from installer import device
from installer import utils
from .. import UI
from . import widgets


palette = [
    ('default',               'default',           'default'),
    ('line',                  'black',             'light gray'),
    ('title1',                'bold',              ''),
    ('options',               'light red',         'black'),
    ('focus heading',         'white',             'dark red'),
    ('focus line',            'black',             'dark red'),
    ('focus options',         'black',             'light gray'),
    ('button.active',         'bold',              ''),
    ('list.entry.active',     'bold',              ''),
    ('list.entry.disabled',   'dark blue',         ''),
    ('side.bar.mark.cross',   'light red',         ''),
    ('side.bar.mark.check',   'dark green',        ''),
    ('top.bar.label',         'black',             'light gray'),
    ('top.bar.hotkey',        'dark blue',         'light gray'),
    ('sum.section',           'underline',         ''),
    ('page.title',            'bold',              ''),
    ('page.legend',           'dark blue',         ''),
    ('progress.bar',          'black',             'dark green'),
    ('log.warn',              'light red',         ''),
    ('log.info',              'light green',       ''),
    ('reversed',              'standout',          '')]


def debug():
    import os, pdb
    os.system('reset')
    print('Entering debug mode')
    pdb.set_trace()


class LogHandler(logging.Handler):

    def __init__(self, ui):
        logging.Handler.__init__(self)
        self._ui = ui

    def emit(self, record):
        self._ui._on_log(record.levelno, self.format(record))


class UrwidUI(UI):

    _loop = None
    _main_frame = None
    _view  = None
    _navigator = None
    _top_bar = None
    _echo_area = None

    def __init__(self, lang):
        self._uevent_handlers = []
        self._watch_pipe_fd = None
        self._watch_pipe_queue = collections.deque()
        UI.__init__(self, lang)
        urwid.set_encoding("utf8")

        if not sys.stdout.isatty():
            utils.die(_("urwid frontend requires a tty"))

        device.listen_uevent(self._on_uevent)

    def _create_step_views(self):
        #
        # Dynamic loading of view modules is based on the english name
        # of the step.
        #
        lang = self.language
        self.language = 'en_US'

        for step in steps.get_steps():
            # Import view's module.
            mod = import_module('.' + step.name.lower(), 'installer.ui.urwid')
            # Retrieve view's class and instantiate it.
            view = getattr(mod, step.name + 'View')(self, step)
            step.view_data = view

        self.language = lang

    def _create_main_view(self):
        self._view = urwid.WidgetPlaceholder(urwid.Text(""))

    def _create_navigator(self):
        self._navigator = Navigator()

        def on_focus_changed(step):
            self._switch_to_step(step)
        urwid.connect_signal(self._navigator, 'focus_changed', on_focus_changed)

    def _create_main_frame(self):
        cols  = [("weight", 0.25, self._navigator)]
        cols += [self._view]
        cols  = urwid.Columns(cols, dividechars=1, focus_column=1)

        self._main_frame = urwid.Frame(cols, self._top_bar, self._echo_area)

    def _create_echo_area(self):
        self._echo_area = EchoArea()

    def _create_top_bar(self):
        self._top_bar = TopBar()

    def _create_log_view(self):
        self._log_view = LogView()

    def _init_logging(self):
        h = LogHandler(self)
        h.setLevel(logging.DEBUG)
        f = logging.Formatter('[%(asctime)s] %(name)s: %(message)s','%H:%M:%S')
        h.setFormatter(f)
        logger = logging.getLogger()
        logger.addHandler(h)
        logger.debug("starting logging facility.")

    def __init_watch_pipe(self):

        def watch_pipe_cb(unused):
            while self._watch_pipe_queue:
                func = self._watch_pipe_queue.pop()
                func()
            # make sure the pipe read side won't be closed.
            return True

        self._watch_pipe_fd = self._loop.watch_pipe(watch_pipe_cb)

    def suspend(self):
        raise NotImplementedError()

    def run(self):
        self._create_log_view()
        self._create_echo_area()
        self._init_logging()
        self._create_step_views()
        self._create_navigator()
        self._create_main_view()
        self._create_top_bar()
        self._create_main_frame()

        def toggle_navigator_focus():
            self._main_frame.body.focus_position ^= 1
        self.register_hotkey('tab', toggle_navigator_focus)
        self.register_hotkey('f1', self._switch_to_step)
        self.register_hotkey('f2', self._switch_to_summary)
        self.register_hotkey('f3', self._switch_to_logs)
        self.register_hotkey('f4', self._switch_to_help)
        self.register_hotkey('f5', self.quit)

        #
        # Since GUdev is used we need to use the even loop based on
        # GLib.
        #
        # In that case, before using Python threads we have to call
        # GObject.threads_init(). Contrary to the naming, this
        # function isn't provided by gobject but initializes thread
        # support in PyGObject (it was called gobject.threads_init()
        # in pygtk). Think of it as gi.threads_init().
        #
        # Since PyGObject 3.10.2, calling GObject.threads_init() this
        # is no longer needed.
        #
        #
        # FIXME: I'm still not sure if it's the right place to add
        # this.
        #
        from gi.repository import GObject
        GObject.threads_init()

        self._loop = urwid.MainLoop(self._main_frame, palette,
                                    event_loop=urwid.GLibEventLoop(),
                                    input_filter=self._handle_hotkeys,
                                    unhandled_input=self.handle_key)
        self._select_first_step()
        self.__init_watch_pipe()
        self._loop.run()

    def _redraw_view(self, view=None):
        if not view:
            view = self._current_step.view_data
        view.redraw()

    def _redraw(self):
        if self._loop:
            self._top_bar.refresh()
            self._navigator.refresh()
            self._loop.draw_screen()
            self._redraw_view()

    def _switch_to_step(self, step=None):
        """Switch the current view to the current step view"""
        UI._select_step(self, step)
        view = self._current_step.view_data
        self.redraw_view(view)
        self._view.original_widget = view

    def _switch_to_summary(self):
        """Switch the current view to the summary view"""
        self._view.original_widget = SummaryView()

    def _switch_to_help(self):
        """Switch the current view to the help view"""
        self._view.original_widget = HelpView()

    def _switch_to_logs(self):
        """Switch the current view to the log view"""
        self._view.original_widget = self._log_view

    def _handle_hotkeys(self, keys, raws):
        self._echo_area.clear()
        for key in keys:
            if self.handle_hotkey(key):
                keys.remove(key)
        return keys

    def register_uevent_handler(self, handler):
        self._uevent_handlers.append(handler)

    def __call(self, func):
        if self._watch_pipe_fd:
            self._watch_pipe_queue.appendleft(func)
            os.write(self._watch_pipe_fd, b'ping')
        else:
            # Used only during initialisation.
            func()

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
        self._redraw()   # Make sure that any pending gfx changes are redrawn.
        UI._quit(self)
        time.sleep(delay)
        raise urwid.ExitMainLoop()

    @ui_thread
    def redraw(self):
        self._redraw()

    @ui_thread
    def redraw_view(self, view=None):
        self._redraw_view(view)

    @ui_thread
    def _select_step(self, step):
        self._navigator.set_focus(step)

    @ui_thread
    def _on_step_finished(self, step, quit, delay=0):
        if quit:
            self.quit(delay)
        else:
            self._navigator.refresh()
            self._select_next_step()

    @ui_thread
    def _on_step_completion(self, step, percent):
        view = step.view_data
        view.set_completion(percent)

    @ui_thread
    def _on_log(self, lvl, msg):
        self._log_view.append_log(lvl, msg)
        self._echo_area.notify(lvl, msg)

    @ui_thread
    def _on_uevent(self, action, bdev):
        for fn in self._uevent_handlers:
            fn(action, bdev)


class View(urwid.WidgetWrap):

    def __init__(self, page=None, title=""):
        if not page:
            page = widgets.Page()
        elif not title:
            title = page.title
        self._page    = urwid.WidgetPlaceholder(page)
        self._linebox = urwid.LineBox(urwid.AttrMap(self._page, 'default'), title)
        attrmap = urwid.AttrMap(self._linebox, 'default', 'button.active')
        urwid.WidgetWrap.__init__(self, attrmap)

    # FIXME: should be removed once the redraw() method will be removed.
    def set_title(self, title):
        return self._linebox.set_title(title)

    def redraw(self):
        self._redraw()
        self.set_title(self.page.title) # FIXME: only for translation support to be removed

    @property
    def page(self):
        return self._page.original_widget

    @page.setter
    def page(self, page):
        self._page.original_widget = page
        self.set_title(page.title)


class StepView(View):

    def __init__(self, ui, step):
        self._ui = ui
        self._step = step
        self._step_page = None
        View.__init__(self)

        self._progress_bar  = widgets.ProgressBar(0, 100)
        # center the progress bar inside the body page.
        body = urwid.Padding(self._progress_bar, 'center', ('relative', 70))
        body = urwid.Filler(body)
        self._progress_page = widgets.Page()
        self._progress_page.body   = body
        self._progress_page.footer = urwid.Text(('page.legend',
                                                 _("Press <F3> to see logs")))

    @property
    def logger(self):
        return logging.getLogger(self._step.name)

    def run(self):
        self._step.process()

    def set_completion(self, percent):
        #
        # Hide the progress bar when the step's job is not yet started or
        # is finished.
        #
        if percent < 1 or percent > 99:
            if self.page == self._progress_page:
                self.page = self._step_page
            return
        #
        # Create an overlay to show a progress bar on top if it
        # doesn't exist yet.
        #
        if self.page != self._progress_page:
            self._step_page = self.page
            self._progress_page.title = self.page.title
            self.page = self._progress_page

        self._progress_bar.set_completion(percent)


class LogView(View):

    def __init__(self):
        page = widgets.Page(_("Logs"))
        self._walker = urwid.SimpleFocusListWalker([])
        page.body = urwid.ListBox(self._walker)
        View.__init__(self, page)

    def append_log(self, lvl, msg):
        txt = urwid.Text(msg)
        if lvl > logging.INFO:
            txt = urwid.AttrMap(txt, 'log.warn')
        self._walker.append(txt)
        self._walker.set_focus(len(self._walker) - 1)


class SummaryView(View):

    def __init__(self):
        page = widgets.Page(_("Summary"))
        items = []

        for section in settings.sections:
            items.append(urwid.Text(('sum.section', section.name)))
            for entry in section.entries:
                value = urwid.Text(str(settings.get(section.name, entry)))
                entry = "    " + entry
                entry = urwid.Text(entry, layout=widgets.FillRightLayout(b'.'))

                col = urwid.Columns([('weight', 0.6, entry),
                                     ('weight',   1, value)])
                items.append(col)
            items.append(urwid.Divider(" "))

        page.body = urwid.ListBox(urwid.SimpleListWalker(items))
        super(SummaryView, self).__init__(page)


class HelpView(View):

    def __init__(self):
        page      = widgets.Page(_("Help"))
        txt       = urwid.Text("Not Yet Implemented", align='center')
        page.body = urwid.Filler(txt)
        super(HelpView, self).__init__(page)


class EchoArea(urwid.Text):

    def __init__(self):
        urwid.Text.__init__(self, "")

    def notify(self, lvl, msg):
        if lvl < logging.INFO:
            return
        msg = msg.split('\n')[0]
        if lvl > logging.INFO:
            markup = ('log.warn', msg)
        elif lvl == logging.INFO:
            markup = ('log.info', msg)
        else:
            markup = msg
        self.set_text(markup)

    def clear(self):
        self.set_text("")


class Navigator(urwid.WidgetWrap):

    signals = ['focus_changed']

    def __init__(self):
        items = []
        for step in steps.get_steps():
            items.append(NavigatorEntry(step))
        walker = urwid.SimpleListWalker(items)
        self._walker = walker
        self._active_entry = self._walker.get_focus()[0]

        urwid.connect_signal(walker, 'modified', self._on_focus_changed)

        linebox = urwid.LineBox(urwid.ListBox(walker))
        linebox = urwid.AttrMap(linebox, 'default', 'button.active')
        super(Navigator, self).__init__(linebox)

    def _on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())
        self._active_entry.active = False
        self._active_entry = self._walker.get_focus()[0]
        self._active_entry.active = True

    def get_focus(self):
        return steps.get_steps()[self._walker.get_focus()[1]]

    def set_focus(self, step):
        assert(not step.is_disabled())
        self._walker.set_focus(steps.get_steps().index(step))

    def keypress(self, size, key):
        return super(Navigator, self).keypress(size, key)

    def refresh(self):
        for e in self._walker:
            e.refresh()


class NavigatorEntry(urwid.WidgetWrap):

    check_mark_markup = ('side.bar.mark.check', u'\N{BULLET}')
    cross_mark_markup = ('side.bar.mark.cross', u'\N{BULLET}')

    def __init__(self, step):
        self._step  = step
        self._title = urwid.Text("", align="left")
        self._mark  = urwid.Text("", align="right")
        self._active = False
        self.refresh()

        columns = urwid.Columns([self._title, (1, self._mark)])
        columns = urwid.AttrMap(columns, 'default')
        super(NavigatorEntry, self).__init__(columns)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, v):
        self._active = v
        self.refresh()

    def selectable(self):
        return self._step.is_enabled()

    def keypress(self, size, key):
        return key

    def refresh(self):
        title = self._step.name
        mark = ""
        if self._step.is_enabled():
            if self._step.is_done():
                mark = self.check_mark_markup
            elif self._step.is_failed():
                mark = self.cross_mark_markup
            if self.active:
                title = ('list.entry.active', title)
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

