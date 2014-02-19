# -*- coding: utf-8 -*-
#

import os
import sys
import time
import collections
import logging
import urwid
from ui import UI
import widgets
import steps
from settings import settings
import utils


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


class LogHandler(logging.Handler):

    def __init__(self, ui):
        logging.Handler.__init__(self)
        self._ui = ui

    def emit(self, record):
        msg = self.format(record).split('\n')[0]
        self._ui._on_log(record.levelno, msg)


class UrwidUI(UI):

    _loop = None
    _main_frame = None
    _view  = None
    _step_views = {}
    _navigator = None
    _top_bar = None
    _echo_area = None

    def __init__(self, lang):
        self._watch_pipe_fd = None
        self._watch_pipe_queue = collections.deque()
        UI.__init__(self, lang)
        urwid.set_encoding("utf8")

        if not sys.stdout.isatty():
            utils.die(_("urwid frontend requires a tty"))

        h = LogHandler(self)
        h.setLevel(logging.DEBUG)
        f = logging.Formatter('[%(asctime)s] %(name)s: %(message)s','%H:%M:%S')
        h.setFormatter(f)
        logger = logging.getLogger()
        logger.addHandler(h)

    def _load_steps(self):
        # FIXME: modules loading should be in abstract class.
        from welcome import WelcomeView
        from license import LicenseView
        from installation import InstallView
        from password import PasswordView
        from exit import ExitView

        from steps.welcome import WelcomeStep
        from steps.license import LicenseStep
        from steps.installation import InstallStep
        from steps.password import PasswordStep
        from steps.exit import ExitStep

        step = WelcomeStep(self)
        view = WelcomeView(self, step)
        self._steps.append(step)
        self._step_views[step] = view

        step = LicenseStep(self)
        view = LicenseView(self, step)
        self._steps.append(step)
        self._step_views[step] = view

        step = InstallStep(self)
        view = InstallView(self, step)
        self._steps.append(step)
        self._step_views[step] = view

        step = PasswordStep(self)
        view = PasswordView(self, step)
        self._steps.append(step)
        self._step_views[step] = view

        step = ExitStep(self)
        view = ExitView(self, step)
        self._steps.append(step)
        self._step_views[step] = view

    def __create_main_view(self):
        self._view = urwid.WidgetPlaceholder(urwid.Text(""))

    def __create_navigator(self):
        self._navigator = Navigator(self._steps)

        def on_focus_changed(step):
            self._switch_to_step(step)
        urwid.connect_signal(self._navigator, 'focus_changed', on_focus_changed)

    def __create_main_frame(self):
        cols  = [("weight", 0.2, self._navigator)]
        cols += [urwid.LineBox(self._view)]
        cols  = urwid.Columns(cols, dividechars=1, focus_column=1)

        self._main_frame = urwid.Frame(cols, self._top_bar, self._echo_area)

    def __create_echo_area(self):
        self._echo_area = EchoArea()

    def __create_top_bar(self):
        self._top_bar = TopBar()

    def __create_log_view(self):
        self._log_view = LogView()

    def __init_watch_pipe(self):

        def watch_pipe_cb(unused):
            while self._watch_pipe_queue:
                func = self._watch_pipe_queue.pop()
                func()
            # make sure the pipe read side won't be closed.
            return True

        self._watch_pipe_fd = self._loop.watch_pipe(watch_pipe_cb)

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
        self.__create_navigator()
        self.__create_main_view()
        self.__create_top_bar()
        self.__create_echo_area()
        self.__create_main_frame()
        self.__create_log_view()

        def toggle_navigator_focus():
            self._main_frame.body.focus_position ^= 1
        self.register_hotkey('tab', toggle_navigator_focus)
        self.register_hotkey('f1', self._switch_to_step)
        self.register_hotkey('f2', self._switch_to_summary)
        self.register_hotkey('f3', self._switch_to_logs)
        self.register_hotkey('f4', self._switch_to_help)
        self.register_hotkey('f5', self.quit)

        self._loop = urwid.MainLoop(self._main_frame, palette,
#                                     event_loop=urwid.GLibEventLoop(),
                                     input_filter=self._handle_hotkeys,
                                     unhandled_input=self.handle_key)
        self._select_first_step()
        self.__init_watch_pipe()
        self._loop.run()

    def _switch_to_step(self, step=None):
        """Switch the current view to the current step view"""
        UI._select_step(self, step)
        view = self._step_views[self._current_step]
        view.redraw()
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
        if self._loop:
            self._top_bar.refresh()
            self._navigator.refresh()
            self._loop.draw_screen()
            self._select_next_step()

    @ui_thread
    def _select_step(self, step):
        self._navigator.set_focus(step)

    @ui_thread
    def _on_step_finished(self, step):
        self._navigator.refresh()
        self._select_next_step()

    @ui_thread
    def _on_step_completion(self, step, percent):
        view = self._step_views[step]
        view.set_completion(percent)

    @ui_thread
    def _on_log(self, lvl, msg):
        self._log_view.append_log(lvl, msg)
        self._echo_area.notify(lvl, msg)


class StepView(urwid.WidgetWrap):

    def __init__(self, ui, step):
        self._ui = ui
        self._step = step
        self._page = urwid.WidgetPlaceholder(urwid.Text(""))
        self._progressbar = widgets.ProgressBar(0, 100)
        self._overlay = urwid.Overlay(self._progressbar, self._page,
                                      'center', ('relative', 55),
                                      'middle', 'pack')

        urwid.WidgetWrap.__init__(self, urwid.WidgetPlaceholder(self._page))

    @property
    def logger(self):
        return logging.getLogger(self._step.name)

    @property
    def page(self):
        return self._page.original_widget

    @page.setter
    def page(self, page):
        self._page.original_widget = page

    def redraw(self):
        return

    def run(self):
        self._step.process()

    def set_completion(self, percent):
        #
        # Hide the progress bar when the step's job is not yet started or
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


class LogView(urwid.WidgetWrap):

    def __init__(self):
        self._walker = urwid.SimpleFocusListWalker([])
        urwid.WidgetWrap.__init__(self, urwid.ListBox(self._walker))

    def append_log(self, lvl, msg):
        txt = urwid.Text(msg)
        if lvl > logging.INFO:
            txt = urwid.AttrMap(txt, 'log.warn')
        self._walker.append(txt)
        self._walker.set_focus(len(self._walker) - 1)


class SummaryView(urwid.WidgetWrap):

    def __init__(self):
        items = []

        for section in settings.sections:
            items.append(urwid.Text(('sum.section', section.name)))
            for entry in section.entries:
                value = urwid.Text(settings.get(section.name, entry))
                entry = "    " + entry
                entry = urwid.Text(entry, layout=widgets.FillRightLayout('.'))

                col = urwid.Columns([('weight', 0.6, entry),
                                     ('weight',   1, value)])
                items.append(col)
            items.append(urwid.Divider(" "))

        walker = urwid.SimpleListWalker(items)
        super(SummaryView, self).__init__(urwid.ListBox(walker))


class HelpView(urwid.WidgetWrap):

    def __init__(self):
        txt = urwid.Text("Not Yet Implemented", align='center')
        txt = urwid.Filler(txt)
        super(HelpView, self).__init__(txt)


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

    def __init__(self, steps):
        self._steps = steps

        items = []
        for step in self._steps:
            items.append(NavigatorEntry(step))
        walker = urwid.SimpleListWalker(items)
        self._walker = walker

        urwid.connect_signal(walker, 'modified', self.__on_focus_changed)
        self._list = urwid.ListBox(walker)
        super(Navigator, self).__init__(urwid.LineBox(self._list))

    def __on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())

    def get_focus(self):
        return self._steps[self._list.get_focus()[1]]

    def set_focus(self, step):
        if step.is_disabled():
            raise IndexValueError
        self._list.set_focus(self._steps.index(step))

    def keypress(self, size, key):
        return super(Navigator, self).keypress(size, key)

    def refresh(self):
        for e in self._walker:
            e.refresh()


class NavigatorEntry(urwid.WidgetWrap):

    check_mark_markup = ('side.bar.mark.check', u'\u2714')
    cross_mark_markup = ('side.bar.mark.cross', u'\u2718')

    def __init__(self, step):
        self._step  = step
        self._title = urwid.Text("", align="left")
        self._mark  = urwid.Text("", align="right")
        self.refresh()

        columns = urwid.Columns([self._title, (1, self._mark)])
        columns = urwid.AttrMap(columns, None, focus_map='reversed')
        super(NavigatorEntry, self).__init__(columns)

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

