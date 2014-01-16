# -*- coding: utf-8 -*-
#

import menu
import urwid
import widgets
import utils
import partition
import device


class PartitionEntryWidget(urwid.WidgetWrap):

    def __init__(self, part, on_click=None):
        self._on_click = on_click
        self.partition = part
        widget1 = urwid.Text(part.name, layout=widgets.FillRightLayout('.'))
        self._devpath = widgets.ClickableText()
        widget2 = urwid.AttrMap(self._devpath, None, focus_map='reversed')

        columns = urwid.Columns([('weight', 0.9, widget1),
                                 ('pack', urwid.Text(" : ")),
                                 widget2])
        super(PartitionEntryWidget, self).__init__(columns)
        self.refresh()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "backspace" or key == "delete":
            self.partition.device = None
            self.refresh()
            return None
        if key == "enter":
            self._on_click(self.partition)
            return None
        return key

    def refresh(self):
        dev = self.partition.device
        self._devpath.set_text(dev.devpath if dev else "")


class PartitionListWidget(urwid.WidgetWrap):

    def __init__(self, on_selected=None, on_cleared=None):
        items = []
        for part in partition.partitions:
            if not part.is_optional:
                items.append(PartitionEntryWidget(part, on_selected))
        items.append(urwid.Divider(" "))
        for part in partition.partitions:
            if part.is_optional:
                items.append(PartitionEntryWidget(part, on_selected))

        self._walker = urwid.SimpleListWalker(items)
        listbox = urwid.ListBox(self._walker)
        linebox = urwid.LineBox(listbox)
        attrmap = urwid.Padding(linebox, align='center', width=('relative', 70))
        attrmap = urwid.Filler(attrmap, 'middle', height=('relative', 90))
        super(PartitionListWidget, self).__init__(attrmap)

    def get_focus(self):
        return self._walker.get_focus()[0].partition

    def refresh(self):
        for entry in self._walker:
            if isinstance(entry, PartitionEntryWidget):
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


class Menu(menu.Menu):

    #requires = ["license"]
    provides = ["rootfs"]

    def __init__(self, ui, menu_event_cb):
        menu.Menu.__init__(self, ui, menu_event_cb)
        self._current_partition = None

    @property
    def name(self):
        return _("Installation")

    def redraw(self):
        self._header.set_text(_("Map partitions to block devices"))

    def _create_widget(self):
        self._partition_list_widget = PartitionListWidget(self._on_selected_partition)

        self._header = widgets.Title1()
        self._footer = urwid.WidgetPlaceholder(urwid.Text(""))
        # use a Pile since the footer must be selectable.
        self._partition_page = urwid.Pile([
            ('pack', self._header),
            ('pack', urwid.Divider(" ")),
            ('weight', 1, self._partition_list_widget),
            ('pack', self._footer)
            ])

        self._install_button = urwid.Button("Install", on_press=self.do_install)
        self._widget = urwid.WidgetPlaceholder(self._partition_page)
        device.listen_uevent(self._on_uevent)

    def _create_device_page(self, part, devices):
        header = widgets.Title1(_("Choose device to use for %s\n") % part.name)
        body   = DeviceListWidget(part, devices)
        footer = urwid.Text(str(body.get_focus()))

        urwid.connect_signal(body, 'focus_changed',
                             lambda dev: footer.set_text(str(dev)))
        urwid.connect_signal(body, 'click', self._on_selected_device)

        return urwid.Frame(body, header, urwid.LineBox(footer))

    def _update_install_button(self):
        w = self._install_button
        for part in partition.partitions:
            if not part.is_optional and part.device is None:
                w = urwid.Text("")
                break
        self._footer.original_widget = w

    def _on_selected_partition(self, part):
        devices = partition.get_candidates(part)
        if devices:
            device_page = self._create_device_page(part, devices)
            self._widget.original_widget = device_page
        else:
            name = part.name
            self.logger.critical(_("No valid device found for %s") % name)

    def _on_selected_device(self, dev):
        if dev:
            self._partition_list_widget.get_focus().device = dev
        #
        # Always refresh the partition list page so any removed
        # devices (while showing the device list) will be handled
        # correctly.
        #
        self._partition_list_widget.refresh()
        self._widget.original_widget = self._partition_page
        self._update_install_button()

    def _on_uevent(self, action, bdev):
        #
        # If we're currently showing the device list then we
        # recreate the whole page so that any added/removed devices
        # will be showed/hidden accordingly.
        #
        if self._widget.original_widget != self._partition_page:
            #
            # switch back to the partition list, so it won't fail if
            # the new list is empty.
            #
            self._widget.original_widget = self._partition_page
            #
            # recreate and display the new device list.
            #
            part = self._partition_list_widget.get_focus()
            self._on_selected_partition(part)
        else:
            #
            # Refresh the partition list page only if it's currently
            # displayed. For the other case, it will be refreshed by
            # _on_selected_device().
            #
            if action == "remove":
                self._partition_list_widget.refresh()
                self._update_install_button()
        #
        # Triggering widget changes from a gudev event has no visual
        # effects. For some reason we have to force a redraw of the
        # whole screen.
        #
        self.ui.redraw()

    def do_install(self, widget):
        self.logger.info(_("starting installation"))

        for mntpnt, dev in mandatory_mountpoints.items():
            if mntpnt == "/":
                mntpnt = "/root"
            self.installer.data["partition" + mntpnt] = dev

        for mntpnt, dev in mandatory_mountpoints.items():
            if dev:
                self.installer.data["partition" + mntpnt] = dev
