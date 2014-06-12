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


class PartitionSectionWidget(urwid.WidgetWrap):
    """Only flow widdgets can be added to the section content."""

    def __init__(self, title):
        self._pile = urwid.Pile([('pack', urwid.Text(('page.section', title)))])
        urwid.WidgetWrap.__init__(self, self._pile)

    @property
    def focus(self):
        return self._pile.focus

    @property
    def focus_position(self):
        return self._pile.focus_position - 1

    @focus_position.setter
    def focus_position(self, index):
        self._pile.focus_position = index + 1

    def get_contents(self):
        return [widget for widget, opts in self._pile.contents[1:]]

    def append(self, widget):
        self._pile.contents.append((widget, ('pack', None)))
        if len(self._pile.contents) == 2:
            self.focus_position = 0


class PartitionListWidget(urwid.WidgetWrap):

    def __init__(self, on_select, on_clear):
        self._entries  = []
        self._walker   = None
        self._sections = []
        for part in partition.partitions:
            self._entries.append(PartitionEntryWidget(part, on_select, on_clear))
        urwid.WidgetWrap.__init__(self, widgets.NullWidget())
        self.refresh()

    def get_focus(self):
        section, index = self._walker.get_focus()
        return section.focus.partition

    def update_focus(self):
        """Move the focus on the first unconfigured entry"""
        for section in self._sections:
            for i, entry in enumerate(section.get_contents()):
                if not entry.partition.device:
                    section.focus_position = i
                    return

    def refresh(self):
        mandatories = PartitionSectionWidget(_('Mandatory mountpoints'))
        optionals   = PartitionSectionWidget(_('Optional mountpoints'))
        swaps       = PartitionSectionWidget(_('Swaps'))
        self._sections = [mandatories, optionals, swaps]

        for entry in self._entries:
            section = optionals
            if not entry.partition.is_optional():
                section = mandatories
            elif entry.partition.is_swap:
                section = swaps
            section.append(entry)
            entry.refresh()

        self._walker = urwid.SimpleListWalker([])
        self._walker.append(mandatories)
        self._walker.append(urwid.Divider(" "))
        self._walker.append(optionals)
        self._walker.append(urwid.Divider(" "))
        self._walker.append(swaps)
        listbox = urwid.ListBox(self._walker) # swaps
        self._w = urwid.Filler(listbox, 'middle', height=('relative', 80))
        self.update_focus()


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
        self._partition_page = widgets.Page(_("Map partitions to block devices"))
        self._partition_page.body = self._partition_list_widget
        self.page = self._partition_page

        ui.register_uevent_handler(self._on_uevent)

    def _redraw(self):
        # When switching to the install view, devices can have been
        # already assigned to partitions by the partitioning step.
        self._partition_list_widget.refresh()
        self._update_install_button(focus=True)

    def _create_device_page(self, part, devices):
        devlist = DeviceListWidget(part, devices)

        page   = widgets.Page(_("Choose device to use for %s") % part.name)
        body   = urwid.Filler(devlist, 'middle', height=('relative', 80))
        body   = urwid.Padding(body, 'center', width=('relative', 60))
        footer = urwid.Text(str(devlist.get_focus()))
        page.body   = body
        page.footer = urwid.LineBox(footer)

        urwid.connect_signal(devlist, 'click', self._on_select_device)
        urwid.connect_signal(devlist, 'focus_changed',
                             lambda dev: footer.set_text(str(dev)))
        return page

    def _update_install_button(self, focus=False):
        for part in partition.partitions:
            if not part.is_optional() and part.device is None:
                self._partition_page.footer = None
                return
        self._partition_page.footer = self._install_button
        if focus:
            self._partition_page.set_focus('footer')

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
