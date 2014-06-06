# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer import disk
from installer import device
from installer import partition
from installer.settings import settings
from installer.utils import pretty_size


logger=None

class PresetPage(widgets.Page):

    signals = ['preset']

    def __init__(self):
        super(PresetPage, self).__init__(_("Type of server"))

        items = [(_("Small/Basic server"),  self._on_small_server),
                 (_("File/Mail server"),    self._on_mail_server),
                 (_("Database/Web server"), self._on_web_server)]
        body = widgets.ClickableTextPile(items)
        body = urwid.Filler(body, 'middle')
        body = urwid.Padding(body, align='center', width=('relative', 60))
        self.body = body

    def _on_small_server(self, widget):
        urwid.emit_signal(self, "preset", "small")

    def _on_mail_server(self, widget):
        urwid.emit_signal(self, "preset", "mail")

    def _on_web_server(self, widget):
        urwid.emit_signal(self, "preset", "web")


class DiskEntryWidget(urwid.CheckBox):

    def __init__(self, bdev):
        model = bdev.model if bdev.model else bdev.devpath
        urwid.CheckBox.__init__(self, model)
        self.bdev = bdev


class DiskListWidget(urwid.WidgetWrap):

    signals = ['focus_changed']

    def __init__(self, ui):
        self._entries = []
        super(DiskListWidget, self).__init__(self._create_disk_list())
        ui.register_uevent_handler(self._on_uevent)

    def __get_bus(self, bdev):
        return bdev.bus.capitalize() if bdev.bus else 'Others'

    def _create_disk_list(self, selected=[], focus=None):
        self._entries = []
        self._walker = urwid.SimpleListWalker([])

        force_bus = None
        if selected:
            force_bus = self.__get_bus(selected[0])

        # candidates are sorted by prio and grouped by bus already.
        for groups in disk.get_candidates():

            bus = self.__get_bus(groups[0])
            if force_bus and bus != force_bus:
                # skip this group
                continue

            self._walker.append(urwid.Divider(" "))
            self._walker.append(urwid.Text(('sum.section', bus)))
            self._walker.append(urwid.Divider(" "))

            for bdev in groups:
                entry = DiskEntryWidget(bdev)
                entry.state = bdev in selected
                self._entries.append(entry)
                self._walker.append(entry)
                #
                # Make sure to set the focus on a device item:
                # otherwise urwid will pick up the first item which is
                # not selectable (Divider)...
                #
                if not focus:
                    focus = entry.bdev
                if entry.bdev == focus:
                    self._walker.set_focus(len(self._walker) - 1)
                urwid.connect_signal(entry, 'change', self._on_change, bus)
        #
        # 'modified' signal is normally used to track changed in
        # walker's content. But SimpleListWalker uses it also to
        # notify focus changes, unlike SimpleFocusListWalker.
        #
        urwid.connect_signal(self._walker, 'modified', self._on_focus_changed)
        return urwid.ListBox(self._walker)

    def _on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())

    def _on_uevent(self, action, bdev):
        #
        # We're not interested by 'change' events since disk validity is
        # checked later. We simply want to display all disks connected
        # to this system.
        #
        if action != 'change':
            selected = self.get_selected()
            if action == 'remove' and bdev in selected:
                selected.remove(bdev)

            self._w = self._create_disk_list(selected, self.get_focus())

    def _on_change(self, widget, state, bus):
        selected = self.get_selected()
        if state == True:
            selected.append(widget.bdev)
        else:
            selected.remove(widget.bdev)

        self._w = self._create_disk_list(selected, self.get_focus())

    def get_focus(self):
        widget, idx = self._walker.get_focus()
        return widget.bdev

    def set_focus(self, bdev):
        for idx, entry in enumerate(self._walker):
            if isinstance(entry, DiskEntryWidget):
                if entry.bdev == bdev:
                    self._walker.set_focus(idx)
                    return

    def get_selected(self):
        return [e.bdev for e in self._entries if e.state == True]

    def set_selected(self, selected):
        self._w = self._create_disk_list(selected, focus=self.get_focus())

    def auto_select(self):
        candidates = disk.select_candidates(map(lambda e: e.bdev, self._entries))
        if candidates:
            self.set_selected(candidates)
        else:
            logger.info(_("Automatic drive(s) selection failed, choose drive(s) manually"))

    def unselect_all(self):
        # Unselecting items doesn't modify the focus.
        self._w = self._create_disk_list(focus=self.get_focus())


class DiskSelectionPage(widgets.Page):

    signals = ['done', 'cancel']

    def __init__(self, ui):
        super(DiskSelectionPage, self).__init__(_("Choose the disk(s) to use"))

        # Body
        pile = widgets.ClickableTextPile([(_("Auto"), self._on_detect),
                                          (_("Clear"),  self._on_clear),
                                          None,
                                          (_("Cancel"), self._on_cancel),
                                          (_("Done"),   self._on_done)])
        pile = urwid.LineBox(pile)
        pile = urwid.Filler(pile, 'middle')
        pile = urwid.Padding(pile, align='center', width=('relative', 70))

        disks = DiskListWidget(ui)
        self._disk_list_w = disks
        disks = urwid.Filler(disks, valign='middle', height=('relative', 70))
        #disks = urwid.Padding(disks, align='center', width=('relative', 80))

        self.body = urwid.Columns([('weight',   1, disks),
                                   ('weight', 0.4, pile)])

        urwid.connect_signal(self._disk_list_w, 'focus_changed',
                             self._on_focus_changed)

        self.footer = urwid.LineBox(urwid.Text(""))
        self._on_focus_changed(self._disk_list_w.get_focus())

    def _on_focus_changed(self, bdev):
        self.footer.base_widget.set_text(str(bdev))

    def _on_clear(self, widget):
        self._disk_list_w.unselect_all()

    def _on_detect(self, widget):
        self._disk_list_w.auto_select()

    def _on_done(self, widget):
        disks = self._disk_list_w.get_selected()

        try:
            disk.check_candidates(disks)
        except disk.DiskError as e:
            logger.error(e)
            self._on_clear(widget)
            return

        # signal that disk(s) is selected and we can calculate the
        # final disk layout.
        urwid.emit_signal(self, "done", disks)

    def _on_cancel(self, widget):
        urwid.emit_signal(self, "cancel")


class ReviewPage(widgets.Page):

    signals = ['create', 'cancel']

    def __init__(self, setup):
        super(ReviewPage, self).__init__(_("Disk Review"))
        has_raid = len(setup.disks) > 1

        #
        # Disk Table
        #
        # FIXME: show somehow if the disks contains data
        #
        t1 = widgets.Table([(_("Disk. #"), 10),
                            (_("Model"),   30),
                            (_("Size"),    15)])

        for i, drive in enumerate(setup.disks, 1):
            t1.append_row([i, drive.model, pretty_size(drive.size)])

        #
        # Partition Table
        #
        fields = [(_("Part. #"), 10),
                  (_("Name"),    10),
                  (_("Size"),    15),
                  (_("FS"),      10)]
        if has_raid:
            fields.append((_("RAID"), 15))
        t2 = widgets.Table(fields)

        for i, part in enumerate(setup.partitions, 1):
            fields = [i, part.name, part.setup.estimate_size(pretty=True),
                      part.setup.fs]
            if has_raid:
                fields.append(part.setup.raid_level[0])
            t2.append_row(fields, [(3, self._on_modify_fs, part)])

        self.body = urwid.Pile([t1, t2, urwid.Filler(urwid.Divider(" "), 'top')])

        #
        # Buttons
        #
        self.footer = urwid.Columns([
            widgets.Button(_("Cancel"), on_press=self._on_cancel),
            widgets.Button(_("Create"), on_press=self._on_create)])
        self.set_focus('footer')

    def _on_create(self, widget):
        urwid.emit_signal(self, "create")

    def _on_cancel(self, widget):
        urwid.emit_signal(self, "cancel")

    def _on_modify_fs(self, part):
        # FIXME: not yet implemented
        pass


class PartitioningView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self.preset = None

        global logger
        logger = self.logger

        self._page1 = PresetPage()
        urwid.connect_signal(self._page1, 'preset', self._on_select_server_type)

        self._page2 = DiskSelectionPage(ui)
        urwid.connect_signal(self._page2, 'cancel', self._on_page2_cancel)
        urwid.connect_signal(self._page2, 'done', self._on_page2_done)

        self.page = self._page1

    def _on_select_server_type(self, preset):
        self.logger.debug("using %s preset" % preset)
        self.page = self._page2
        # load preconfiguration data
        self.preset = preset

    def _on_page2_cancel(self):
        self.page = self._page1

    def _on_page2_done(self, disks):
        # create a disk template and pass it to the reviewer.
        if not disks:
            self.logger.error("you must select at least 1 disk")
            return

        try:
            setup = self._step.initialize(disks, self.preset)
        except partition.PartitionSetupError:
            logger.critical(_("disk(s) too small for a %s server setup") % self.preset)
            return

        page3 = ReviewPage(setup)
        urwid.connect_signal(page3, 'create', self._on_page3_create)
        urwid.connect_signal(page3, 'cancel', self._on_page3_cancel)
        self.page = page3

    def _on_page3_create(self):
        # pass the template to the stepper.
        self.run()

    def _on_page3_cancel(self):
        self.page = self._page1
