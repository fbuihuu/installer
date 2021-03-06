# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

import urwid

from . import StepView
from . import widgets
from installer import l10n


#
# Language selection should be immediate.
#
# Layout should be effective when validating since keyboard is needed
# later (root password setup for example).
#

class LanguageView(StepView):

    def __init__(self, ui, step):
        StepView.__init__(self, ui, step)
        self.page = widgets.Page(_("Select your location"))

        # Build a self._country_zones, which is a list of prefered
        # zones in each country.
        self._country_zones = []
        ccode_set = set()

        for zi in l10n.get_country_zones():
            if zi.ccode not in ccode_set:
                self._country_zones.append(zi)
                ccode_set.add(zi.ccode)
        countries = [z.country for z in self._country_zones]

        body = widgets.ClickableTextList(countries, self.on_click)

        # Try to move the focus on the entry that matches (roughly)
        # the current locale.
        for zi in self._country_zones:
            if zi.locale.startswith(l10n.language):
                body.set_focus(zi.country)
                break

        body = urwid.Filler(body, 'middle', height=('relative', 40))
        body = urwid.Padding(body,'center', width=('relative', 60))
        self.page.body = body

    def on_click(self, country, index):
        #
        # step is run simply to update its state to 'done'
        #
        self.run()

        #
        # Setting the locale may fail if it's not installed on the
        # host system, but that's not an issue since we're interested
        # mostly in setting up the language.
        #
        locale = self._country_zones[index].locale

        l10n.set_locale(locale)
        l10n.set_language(locale)

        self._ui._reload()
