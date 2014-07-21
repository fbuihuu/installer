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
        super(PresetPage, self).__init__(_("Type of server [1/3]"))

        items = [(_("Small/Basic"),  self._on_small_server),
                 (_("File/Mail"),    self._on_mail_server),
                 (_("Database/Web"), self._on_web_server)]
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
        urwid.CheckBox.__init__(self, "")
        self.bdev = bdev


class DiskTableWidget(urwid.WidgetWrap):

    def __init__(self, ui, priority=device.PRIORITY_DEFAULT):
        self._entries = []
        self._prio = priority
        super(DiskTableWidget, self).__init__(widgets.NullWidget())
        self._create_disk_table()
        ui.register_uevent_handler(self._on_uevent)

    def __get_bus(self, bdev):
        return bdev.bus.capitalize() if bdev.bus else ''

    def _create_disk_table(self, selected=[], focus=None):
        self._entries = []

        force_bus = None
        if selected:
            force_bus = self.__get_bus(selected[0])

        table = widgets.Table([("",           'left',    5),
                               (_("Bus"),     'left',    8),
                               (_("Model"),   'center', 34),
                               (_("Size"),    'right',   9)])
        self._w = table

        # candidates are sorted by prio and grouped by bus already.
        for groups in disk.get_candidates():

            bus = self.__get_bus(groups[0])
            if force_bus is not None and bus != force_bus:
                # skip this group
                continue

            for bdev in groups:
                if bdev.priority < self._prio:
                    continue

                entry = DiskEntryWidget(bdev)
                entry.state = bdev in selected
                self._entries.append(entry)

                row  = [entry, urwid.Text(bus)]
                row += [urwid.Text(bdev.model)]
                row += [urwid.Text(pretty_size(bdev.size))]
                table.append_row(row)

                #
                # Make sure to set the focus on a device item:
                # otherwise urwid will pick up the first item which is
                # not selectable (Divider)...
                #
                if not focus:
                    focus = entry.bdev
                if entry.bdev == focus:
                    table.set_focus(-1)
                urwid.connect_signal(entry, 'change', self._on_change, bus)

    @property
    def priority(self):
        return self._prio

    @priority.setter
    def priority(self, prio):
        self._prio = prio
        selected = [d for d in self.get_selected() if d.priority >= self._prio]
        self._create_disk_table(selected, focus=self.get_focus())

    def _on_uevent(self, action, bdev):
        #
        # Display all disks known by the system. We'll check the
        # validity of the selected disks later. Note that 'change'
        # events might add new disks, loop devices is an example.
        #
        selected = self.get_selected()
        if action == 'remove' and bdev in selected:
            selected.remove(bdev)

        self._create_disk_table(selected, self.get_focus())

    def _on_change(self, widget, state, bus):
        selected = self.get_selected()
        if state == True:
            selected.append(widget.bdev)
        else:
            selected.remove(widget.bdev)
        self._create_disk_table(selected, self.get_focus())

    def get_focus(self):
        cols = self._w.get_focus()
        return cols[0].bdev

    def set_focus(self, bdev):
        for i, entry in enumerate(self._entries):
            if entry.bdev == bdev:
                self._w.set_focus(i)
                return

    def get_selected(self):
        return [e.bdev for e in self._entries if e.state == True]

    def set_selected(self, selected):
        self._create_disk_table(selected, focus=self.get_focus())

    def auto_select(self):
        candidates = disk.select_candidates(map(lambda e: e.bdev, self._entries))
        if candidates:
            self.set_selected(candidates)
        else:
            logger.info(_("Automatic drive(s) selection failed, choose drive(s) manually"))

    def unselect_all(self):
        # Unselecting items doesn't modify the focus.
        self._create_disk_table(focus=self.get_focus())


class DiskSelectionPage(widgets.Page):

    signals = ['done', 'cancel']

    def __init__(self, ui):
        super(DiskSelectionPage, self).__init__(_("Choose the disk(s) to use [2/3]"))

        self._prio = device.PRIORITY_DEFAULT
        self._table = DiskTableWidget(ui, self._prio)
        self.body   = urwid.Filler(self._table, valign='middle',
                                    height=('relative', 70))

        self.footer = urwid.Pile([
            urwid.Columns([widgets.Button(_("Auto"),   on_press=self._on_detect),
                           widgets.Button(_("Clear"),  on_press=self._on_clear)]),
            urwid.Columns([widgets.Button(_("Cancel"), on_press=self._on_cancel),
                           widgets.Button(_("Done"),   on_press=self._on_done)]),
            urwid.Divider('─'),
            urwid.Text(('page.legend', _("Press <alt>-a to see all devices")))
            ])

    def keypress(self, size, key):
        if key == 'meta a':
            if self._prio == device.PRIORITY_DEFAULT:
                self._prio = device.PRIORITY_LOW
            else:
                self._prio = device.PRIORITY_DEFAULT
            self._table.priority = self._prio
            return None
        return super(DiskSelectionPage, self).keypress(size, key)

    def _on_focus_changed(self, bdev):
        self.footer.base_widget.set_text(str(bdev))

    def _on_clear(self, widget):
        self._table.unselect_all()

    def _on_detect(self, widget):
        self._table.auto_select()

    def _on_done(self, widget):
        disks = self._table.get_selected()

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
        super(ReviewPage, self).__init__(_("Disk Review [3/3]"))
        has_raid = len(setup.disks) > 1

        #
        # Disk Table
        #
        # FIXME: show somehow if the disks contains data
        #
        t1 = widgets.Table([(_("Disk. #"), 'center', 10),
                            (_("Model"),   'center', 34),
                            (_("Size"),    'right',   9)])

        for i, drive in enumerate(setup.disks, 1):
            t1.append_row([urwid.Text(str(i)), urwid.Text(drive.model),
                           urwid.Text(pretty_size(drive.size))])

        #
        # Partition Table
        #
        fields = [(_("Part. #"), 'center', 10),
                  (_("Name"),    'left',   10),
                  (_("Size"),    'right',   9),
                  (_("FS"),      'right',  10)]
        if has_raid:
            fields.append((_("RAID"), 'right', 15))
        t2 = widgets.Table(fields)

        for i, part in enumerate(setup.partitions, 1):
            fs = widgets.ClickableText(part.setup.fs)
            urwid.connect_signal(fs, 'click', self._on_modify_fs, part)

            fields = [urwid.Text(str(i)), urwid.Text(part.name),
                      urwid.Text(part.setup.estimate_size(pretty=True)), fs]
            if has_raid:
                fields.append(urwid.Text(part.setup.raid_level[0]))
            t2.append_row(fields)

        self.body = urwid.Filler(urwid.Pile([t1, t2]), 'middle',
                                 height=('relative', 80))
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

    def _on_modify_fs(self, widget, part):
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
