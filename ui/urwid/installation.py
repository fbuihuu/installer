# -*- coding: utf-8 -*-
#

import menu
import urwid
import widgets
import utils
import partition


class PartitionEntryWidget(urwid.WidgetWrap):

    def __init__(self, part, on_click=None):
        self._on_click = on_click
        self._partition = part
        widget1 = urwid.Text(part.name, layout=widgets.FillRightLayout('.'))
        self._devpath = widgets.ClickableText()
        widget2 = urwid.AttrMap(self._devpath, None, focus_map='reversed')

        columns = urwid.Columns([('weight', 0.9, widget1),
                                 ('pack', urwid.Text(" : ")),
                                 widget2])
        super(PartitionEntryWidget, self).__init__(columns)
        self.set_device(part.device)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "backspace" or key == "delete":
            self.set_device(None)
            return None
        if key == "enter":
            self._on_click(self._partition)
            return None
        return key

    def set_device(self, dev):
        self._partition.device = dev
        txt = dev.devpath if dev else ""
        self._devpath.set_text(txt)


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
        return self._walker.get_focus()[0]

    def set_device(self, dev):
        self.get_focus().set_device(dev)


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
        if self._widget.original_widget != self._partition_page:
            return

        self._header.set_text(_("Map partitions to block devices"))

        w = self._install_button
        for part in partition.partitions:
            if not part.is_optional and part.device is None:
                w = urwid.Text("")
                break
        self._footer.original_widget = w

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

    def _create_device_page(self, part, devices):
        header = widgets.Title1(_("Choose device to use for %s\n") % part.name)
        body   = DeviceListWidget(part, devices)
        footer = urwid.Text(str(body.get_focus()))

        urwid.connect_signal(body, 'focus_changed',
                             lambda dev: footer.set_text(str(dev)))
        urwid.connect_signal(body, 'click', self._on_selected_device)

        return urwid.Frame(body, header, urwid.LineBox(footer))

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
            self._partition_list_widget.set_device(dev)
        self._widget.original_widget = self._partition_page

    def do_install(self, widget):
        self.logger.info(_("starting installation"))

        for mntpnt, dev in mandatory_mountpoints.items():
            if mntpnt == "/":
                mntpnt = "/root"
            self.installer.data["partition" + mntpnt] = dev

        for mntpnt, dev in mandatory_mountpoints.items():
            if dev:
                self.installer.data["partition" + mntpnt] = dev
