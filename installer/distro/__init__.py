# -*- coding: utf-8 -*-
#
from __future__ import unicode_literals

__all__ = ['paths', 'install']


from installer.system import distribution


if distribution.distributor == 'Mandriva':
    from .mandriva import *

elif distribution.distributor == 'Arch':
    from .archlinux import *

else:
    raise NotImplementedError()
