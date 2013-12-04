# Copyright 2013 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#
# Code taken from the pyanaconda.keyboard module

"""
Module providing the LocaledWrapper class wrapping the systemd-localed DBus API.

"""

import dbus

LOCALED_SERVICE = "org.freedesktop.locale1"
LOCALED_OBJECT_PATH = "/org/freedesktop/locale1"
LOCALED_IFACE = "org.freedesktop.locale1"

class LocaledWrapperError(Exception):
    """Exception class for reporting Localed-related problems"""
    pass

class LocaledWrapper(object):
    """
    Class wrapping systemd-localed daemon functionality.

    """

    def __init__(self):
        bus = dbus.SystemBus()

        try:
            localed = bus.get_object(LOCALED_SERVICE, LOCALED_OBJECT_PATH)
        except dbus.DBusException:
            raise LocaledWrapperError("Failed to get locale object")

        try:
            self._locale_iface = dbus.Interface(localed, LOCALED_IFACE)
        except dbus.DBusException:
            raise LocaledWrapperError("Failed to get locale interface")

        try:
            self._props_iface = dbus.Interface(localed, dbus.PROPERTIES_IFACE)
        except dbus.DBusException:
            raise LocaledWrapperError("Failed to get properties interface")

    def set_layout_variant(self, layout, variant, model, options):
        """ Method that sets X11 layout and variant (for later X sessions). """

        # args: layout, model, variant, options, convert, user_interaction
        # where convert indicates whether the layout should be converted to a
        # VConsole keymap and user_interaction indicates whether PolicyKit
        # should ask for credentials or not
        try:
            self._locale_iface.SetX11Keyboard(layout, model, variant, options,
                                              False, True)
        except dbus.DBusException:
            msg = "Failed to call SetX11Keyboard method"
            raise LocaledWrapperError(msg)

    def set_keymap(self, keymap):
        """ Method that sets VConsole keymap. """

        # args: keymap, keymap_toggle, convert, user_interaction
        # where convert indicates whether the keymap should be converted to an
        # X11 layout and user_interaction indicates whether PolicyKit should ask
        # for credentials or not
        try:
            self._locale_iface.SetVConsoleKeyboard(keymap, "", False, True)
        except dbus.DBusException:
            msg = "Failed to call SetVConsoleKeyboard method"
            raise LocaledWrapperError(msg)

    def get_keyboard_info(self):
        """
        Method that returns the information about the Keyboard configuration.

        :return: dictionary containing the key-value pairs representing the
                 current keyboard configuration
        :rtype: dict(string -> string)

        """

        rdict = dict()

        # try to get as much values as we can
        try:
            rdict["KEYTABLE"] = str(self._props_iface.Get(LOCALED_IFACE, "VConsoleKeymap"))
        except dbus.DBusException:
            pass

        try:
            rdict["MODEL"] = str(self._props_iface.Get(LOCALED_IFACE, "X11Model"))
        except dbus.DBusException:
            pass

        try:
            rdict["LAYOUT"] = str(self._props_iface.Get(LOCALED_IFACE, "X11Layout"))
        except dbus.DBusException:
            pass

        try:
            rdict["VARIANT"] = str(self._props_iface.Get(LOCALED_IFACE, "X11Variant"))
        except dbus.DBusException:
            pass

        try:
            rdict["OPTIONS"] = str(self._props_iface.Get(LOCALED_IFACE, "X11Options"))
        except dbus.DBusException:
            pass

        return rdict
