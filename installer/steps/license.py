# -*- coding: utf-8 -*-
#

from installer.settings import settings
from . import Step, StepError


class LicenseStep(Step):

    requires = ["language"]
    provides = ["license"]

    @property
    def name(self):
        return _("License")

    def _process(self):
        if settings.License.status != "accepted":
            raise StepError(_('you rejected the terms of the license.'))
        self.logger.info(_('you accepted the terms of the license'))
