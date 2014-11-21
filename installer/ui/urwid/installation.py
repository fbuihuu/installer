# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid

from . import StepView
from . import widgets
from installer import utils
from installer import partition
from installer import device
from installer.settings import settings



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

    def __init__(self, on_click, on_clear):
        self._entries  = []
        self._walker   = None
        self._sections = []
        for part in partition.partitions:
            field = widgets.Field(part.name)
            field.partition = part
            self._entries.append(field)
            urwid.connect_signal(field, 'click', on_click, part)
            urwid.connect_signal(field, 'clear', on_clear, part)

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
                    self._walker.set_focus(self._walker.index(section))
                    section.focus_position = i
                    return

    def refresh(self):
        mandatories = PartitionSectionWidget(_('Mandatory mountpoints'))
        optionals   = PartitionSectionWidget(_('Optional mountpoints'))
        swaps       = PartitionSectionWidget(_('Swaps'))
        self._sections = [mandatories, optionals, swaps]

        for entry in self._entries:
            part    = entry.partition
            section = optionals
            if not part.is_optional():
                section = mandatories
            elif part.is_swap:
                section = swaps
            section.append(entry)
            entry.value = part.device.devpath if part.device else None

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

    def __init__(self, devices):
        super(DeviceListWidget, self).__init__([], self._on_click)
        self.update(devices)
        urwid.connect_signal(self._walker, 'modified', self._on_focus_changed)

    def _on_focus_changed(self):
        urwid.emit_signal(self, "focus_changed", self.get_focus())

    def _on_click(self, widget):
        urwid.emit_signal(self, "click", self.get_focus())

    def update(self, devices):
        self._devices = devices
        items = [dev.devpath for dev in self._devices]
        widgets.ClickableTextList.update(self, items)

    def keypress(self, size, key):
        if key == "esc":
            urwid.emit_signal(self, "click", None)
            return None
        return super(DeviceListWidget, self).keypress(size, key)

    def get_focus(self):
        if self._devices:
            widget, idx = self._walker.get_focus()
            return self._devices[idx]

    def set_focus(self, device):
        self._walker.set_focus(self._devices.index(device))


class InstallationView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)

        self._install_button = widgets.Button(_("Install"), on_press=self.do_install)
        self._partition_list_widget = PartitionListWidget(self._on_select_partition,
                                                          self._on_clear_partition)
        self._partition_page = widgets.Page(_("Map partitions to block devices"))
        self._partition_page.body = self._partition_list_widget
        self.page = self._partition_page

        self._devlist = DeviceListWidget([])
        self._devlist_page = widgets.Page()
        body   = urwid.Filler(self._devlist, 'middle', height=('relative', 80))
        body   = urwid.Padding(body, 'center', width=('relative', 60))
        footer = urwid.Text("")
        self._devlist_page.body   = body
        self._devlist_page.footer = urwid.LineBox(footer)

        urwid.connect_signal(self._devlist, 'click', self._on_select_device)
        urwid.connect_signal(self._devlist, 'focus_changed',
                             lambda dev: footer.set_text('%s' % dev))

        ui.register_uevent_handler(self._on_uevent)

    def _redraw(self):
        # When switching to the install view, devices can have been
        # already assigned to partitions by the 'disk' step.
        self._partition_list_widget.refresh()
        self._update_install_button(focus=True)

    def _update_install_button(self, focus=False):
        for part in partition.partitions:
            if not part.is_optional() and part.device is None:
                self._partition_page.footer = None
                return
        self._partition_page.footer = self._install_button
        if focus:
            self._partition_page.set_focus('footer')

    def _update_device_list(self, part):
        devices = partition.get_candidates(part)
        if not devices:
            self.logger.warning(_("No valid device found for %s"), part.name)
        self._devlist.update(devices)
        if part.device:
            self._devlist.set_focus(part.device)

    def _on_clear_partition(self, part):
        part.device = None
        self._partition_list_widget.refresh()
        self._update_install_button()

    def _on_select_partition(self, part):
        self._devlist_page.title = _("Choose device to use for %s") % part.name
        self._update_device_list(part)
        self.page = self._devlist_page

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
        # Note: we can enter this function when the current page is
        # the progress one.
        #
        if self.page == self._devlist_page:
            #
            # update the device list.
            #
            part = self._partition_list_widget.get_focus()
            self._update_device_list(part)

        elif self.page == self._partition_page:
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
