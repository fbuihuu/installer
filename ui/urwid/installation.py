# -*- coding: utf-8 -*-
#

import gudev
import menu
import urwid
import widgets

mandatory_mountpoints = {
    "/":        None,
}

optional_mountpoints = {
    "/boot":    None,
    "/home":    None,
    "/var":     None,
    "swap":     None,
}

class PartitionDevice(object):

    def __init__(self, gudev):
        self._gudev = gudev
        self._mntpoint = None

    @property
    def _syspath(self):
        return self._gudev.get_sysfs_path()

    @property
    def filesystem(self):
        return self._gudev.get_property("ID_FS_TYPE")

    @property
    def size(self):
        with open(self._syspath + "/size", 'r') as f:
            size = f.read()
        return int(size)

    @property
    def devpath(self):
        return self._gudev.get_device_file()

    @property
    def model(self):
        return self._gudev.get_property("ID_MODEL")

    @property
    def bus(self):
        return self._gudev.get_property("ID_BUS")

    @property
    def scheme(self):
        return self._gudev.get_property("ID_PART_ENTRY_SCHEME")

    def __str__(self):
        lines = [(_("Model"),      self.model),
                 (_("Bus"),        self.bus),
                 (_("Filesystem"), self.filesystem),
                 (_("Size"),       self.size),
                 (_("Scheme"),     self.scheme)]
        width = max([len(line[0]) for line in lines])

        return "\n".join(["%s : %s" % (("{0:%d}" % width).format(a), b)
                         for a, b in lines])


def get_installable_devices():
    rv = []
    client = gudev.Client(None)
    for bdev in client.query_by_subsystem("block"):
        if bdev.get_devtype() != "partition":
            continue
        if bdev.get_property("ID_FS_TYPE") is None:
            continue
        part = PartitionDevice(bdev)
        rv.append(part)
    return rv


class MountpointListEntryWidget(urwid.WidgetWrap):

    def __init__(self, mntpnt, dev=None, on_click=None):
        self._callback = on_click
        self._mntpnt = urwid.Text(mntpnt, align="left")
        self._device = widgets.ClickableText(dev if dev else _("< None >"))
        urwid.connect_signal(self._device, 'click', self.__on_click)
        self._device = urwid.AttrMap(self._device, None, focus_map='reversed')

        columns = urwid.Columns([('weight', 0.3, self._mntpnt), self._device])
        padding = urwid.Padding(columns, align='center', width=('relative', 60))
        super(MountpointListEntryWidget, self).__init__(padding)

    def __on_click(self, button):
        if self._callback:
            self._callback(self._mntpnt.text)


class MountpointListWidget(urwid.WidgetWrap):

    def __init__(self, on_selected=None):
        items = list()

        for mntpnt, dev in mandatory_mountpoints.items():
            entry = MountpointListEntryWidget(mntpnt, dev, on_selected)
            items.append(entry)

        items.append(urwid.Divider(" "))

        for mntpnt, dev in optional_mountpoints.items():
            entry = MountpointListEntryWidget(mntpnt, dev, on_selected)
            items.append(entry)

        walker = urwid.SimpleListWalker(items)
        super(MountpointListWidget, self).__init__(urwid.ListBox(walker))


class DeviceListWidget(widgets.ClickableTextList):

    signals = ['focus_changed', 'click']

    def __init__(self):
        self._devices = get_installable_devices()
        items = [ dev.devpath for dev in self._devices ]
        super(DeviceListWidget, self).__init__(items, self.__on_click)
        urwid.connect_signal(self._walker, 'modified', self.__on_focus_changed)

    def __on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())

    def __on_click(self, widget):
        urwid.emit_signal(self, "click", self.get_focus())

    def get_focus(self):
        widget, idx = self._walker.get_focus()
        return self._devices[idx]


class Menu(menu.Menu):

    #requires = ["license"]
    provides = ["rootfs"]

    def __init__(self, ui, menu_event_cb):
        menu.Menu.__init__(self, ui, menu_event_cb)
        self._current_mntpnt = None

    @property
    def name(self):
        return _("Installation")

    def redraw(self):
        if self._widget.original_widget != self._mountpoint_widget:
            return

        self._header.set_text(_("Map partitions to block devices"))
        self._body.original_widget = MountpointListWidget(self._on_selected_mntpoint)

        w = urwid.Text("")
        if None not in mandatory_mountpoints.values():
            w = self._install_button
        self._footer.original_widget = w

    def _create_widget(self):
        self._header = urwid.Text("", align='center')
        self._body   = urwid.WidgetPlaceholder(urwid.SelectableIcon(""))
        self._footer = urwid.WidgetPlaceholder(urwid.Text(""))
        # use a Pile since the footer must be selectable.
        self._mountpoint_widget = urwid.Pile([
            ('pack', self._header),
            ('pack', urwid.Divider(" ")),
            ('weight', 1, self._body),
            ('pack', self._footer)
            ])

        self._install_button = urwid.Button("Install", on_press=self.do_install)
        self._widget = urwid.WidgetPlaceholder(self._mountpoint_widget)

    def _create_device_page(self, mntpnt):
        header = urwid.Text(_("Choose device to use for %s\n") % mntpnt)
        body   = DeviceListWidget()
        footer = urwid.Text(str(body.get_focus()))

        urwid.connect_signal(body, 'focus_changed',
                             lambda dev: footer.set_text(str(dev)))
        urwid.connect_signal(body, 'click', self._on_selected_device)

        return urwid.Frame(body, header, urwid.LineBox(footer))

    def _on_selected_mntpoint(self, mntpnt):
        self._current_mntpnt = mntpnt
        self._widget.original_widget = self._create_device_page(mntpnt)

    def _on_selected_device(self, dev):
        mntpnt = self._current_mntpnt
        if mandatory_mountpoints.has_key(mntpnt):
            mandatory_mountpoints[mntpnt] = dev.devpath
        else:
            optional_mountpoints[mntpnt] = dev.devpath
        self._widget.original_widget = self._mountpoint_widget
        self._current_mntpnt = None
        self.redraw()

    def do_install(self, widget):
        self.logger.info(_("starting installation"))

        for mntpnt, dev in mandatory_mountpoints.items():
            if mntpnt == "/":
                mntpnt = "/root"
            self.installer.data["partition" + mntpnt] = dev

        for mntpnt, dev in mandatory_mountpoints.items():
            if dev:
                self.installer.data["partition" + mntpnt] = dev
