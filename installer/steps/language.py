# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

from . import Step


class LanguageStep(Step):

    provides = ["language"]

    @property
    def name(self):
        return _("Language")

    def _process(self):
        #
        # The 'Language' step is a nop since the whole work is done by
        # the UI. Indeed switching language needs redrawing mostly.
        #
        pass
