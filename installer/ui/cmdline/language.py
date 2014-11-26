# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

from . import StepView
from installer import l10n


class LanguageView(StepView):

    def _run(self, args):
        self._step.process(l10n.get_current_zone())
