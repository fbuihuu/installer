# -*- coding: utf-8 -*-
#

import urwid

from . import StepView
from . import widgets
from installer import utils
from installer import partition
from installer import device
from installer.settings import settings


class PartitionEntryWidget(urwid.WidgetWrap):

    def __init__(self, part, on_click, on_clear):
        self._on_click = on_click
        self._on_clear = on_clear
        self.partition = part
        widget1 = urwid.Text(part.name, layout=widgets.FillRightLayout(b'.'))
        self._devpath = widgets.ClickableText()

        columns = urwid.Columns([('weight', 0.9, widget1),
                                 ('pack', urwid.Text(" : ")),
                                 self._devpath])
        super(PartitionEntryWidget, self).__init__(columns)
        self.refresh()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "backspace" or key == "delete":
            self._on_clear(self.partition)
            return None
        if key == "enter":
            self._on_click(self.partition)
            return None
        return key

    def refresh(self):
        dev = self.partition.device
        self._devpath.set_text(dev.devpath if dev else "")


class PartitionListWidget(urwid.WidgetWrap):

    def __init__(self, on_select, on_clear):
        self._entries = []
        for part in partition.partitions:
            self._entries.append(PartitionEntryWidget(part, on_select, on_clear))

        # First list contains mandatory partitions, the second
        # contains optional ones.
        items = [urwid.ListBox(urwid.SimpleListWalker([])),
                 ('pack', urwid.Divider(" ")),
                 urwid.ListBox(urwid.SimpleListWalker([])),
                 ('pack', urwid.Divider(" ")),
                 urwid.ListBox(urwid.SimpleListWalker([]))] # swaps
        self._pile = urwid.Pile(items)
        linebox = urwid.LineBox(self._pile)
        attrmap = urwid.Padding(linebox, align='center', width=('relative', 70))
        attrmap = urwid.Filler(attrmap, 'middle', height=('relative', 90))
        super(PartitionListWidget, self).__init__(attrmap)
        self.refresh()

    @property
    def _walkers(self):
        return ((0, self._pile[0].body), (2, self._pile[2].body),
                (4, self._pile[4].body))

    def get_focus(self):
        return self._pile.focus.get_focus()[0].partition

    def update_focus(self):
        """Move the focus on the first unconfigured entry"""
        for i, walker in self._walkers:
            for j, entry in enumerate(walker):
                if not entry.partition.device:
                    walker.set_focus(j)
                    self._pile.focus_position = i
                    return

    def refresh(self):
        for idx, walker in self._walkers:
            del walker[:]
        for entry in self._entries:
            if not entry.partition.is_optional():
                self._walkers[0][1].append(entry)
            elif entry.partition.is_swap:
                self._walkers[2][1].append(entry)
            else:
                self._walkers[1][1].append(entry)
            entry.refresh()


class DeviceListWidget(widgets.ClickableTextList):

    signals = ['focus_changed', 'click']

    def __init__(self, part, devices):
        self._devices = devices
        items = [ dev.devpath for dev in self._devices ]
        super(DeviceListWidget, self).__init__(items, self.__on_click)
        urwid.connect_signal(self._walker, 'modified', self.__on_focus_changed)

        if part.device:
            self._walker.set_focus(self._devices.index(part.device))

    def __on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())

    def __on_click(self, widget):
        urwid.emit_signal(self, "click", self.get_focus())

    def keypress(self, size, key):
        if key == "esc":
            urwid.emit_signal(self, "click", None)
            return None
        return super(DeviceListWidget, self).keypress(size, key)

    def get_focus(self):
        widget, idx = self._walker.get_focus()
        return self._devices[idx]


class InstallationView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self._install_button = widgets.Button(_("Install"), on_press=self.do_install)
        self._partition_list_widget = PartitionListWidget(self._on_select_partition,
                                                          self._on_clear_partition)
        self._partition_page = widgets.Page()
        self._partition_page.body = self._partition_list_widget
        self.page = self._partition_page

        ui.register_uevent_handler(self._on_uevent)

    def _redraw(self):
        self._partition_page.title = _("Map partitions to block devices")
        # When switching to the install view, devices can have been
        # already assigned to partitions by the partitioning step.
        self._partition_list_widget.refresh()
        self._update_install_button()

    def _create_device_page(self, part, devices):
        page = widgets.Page()
        page.title  = _("Choose device to use for %s\n") % part.name
        page.body   = DeviceListWidget(part, devices)
        footer      = urwid.Text(str(page.body.get_focus()))
        page.footer = urwid.LineBox(footer)

        urwid.connect_signal(page.body, 'click', self._on_select_device)
        urwid.connect_signal(page.body, 'focus_changed',
                             lambda dev: footer.set_text(str(dev)))
        return page

    def _update_install_button(self):
        for part in partition.partitions:
            if not part.is_optional() and part.device is None:
                self._partition_page.footer = None
                return
        self._partition_page.footer = self._install_button

    def _on_clear_partition(self, part):
        part.device = None
        self._partition_list_widget.refresh()
        self._update_install_button()

    def _on_select_partition(self, part):
        devices = partition.get_candidates(part)
        if devices:
            self.page = self._create_device_page(part, devices)
        else:
            name = part.name
            self.logger.warning(_("No valid device found for %s"), name)

    def _on_select_device(self, dev):
        if dev:
            if dev.mountpoints:
                self.logger.error(_("%s is mounted, no harm will be done"),
                                  dev.devpath)
                return
            try:
                part = self._partition_list_widget.get_focus()
                part.device = dev
            except device.DeviceError as e:
                self.logger.error(e)
                return
            except partition.PartitionError as e:
                self.logger.error(e)
                return

        #
        # Always refresh the partition list page so any removed
        # devices (while showing the device list) will be handled
        # correctly.
        #
        self._partition_list_widget.refresh()
        self._partition_list_widget.update_focus()
        self.page = self._partition_page
        self._update_install_button()

    def _on_uevent(self, action, bdev):
        #
        # If we're currently showing the device list then we
        # recreate the whole page so that any added/removed devices
        # will be showed/hidden accordingly.
        #
        if self.page != self._partition_page:
            #
            # switch back to the partition list, so it won't fail if
            # the new list is empty.
            #
            self.page = self._partition_page
            #
            # recreate and display the new device list.
            #
            part = self._partition_list_widget.get_focus()
            self._on_select_partition(part)
        else:
            #
            # Refresh the partition list page only if it's currently
            # displayed. For the other case, it will be refreshed by
            # _on_select_device().
            #
            if action == "remove" or action == "change":
                self._partition_list_widget.refresh()
                self._update_install_button()

    def do_install(self, widget):
        self.run()
