import os
import stat

from . import StepView, ViewError
from installer import device
from installer import partition
from installer import disk


class PartitioningView(StepView):

    def _run(self, args):
        disks  = []
        preset = 'small'

        # if no disks were passed then skip this test. The
        # installation step will check that partitions have been
        # specified.
        if not args.disks:
            return False

        #
        # see if the device is valid and is knonw by udev
        #
        for path in args.disks:
            st = os.stat(path)

            if not stat.S_ISBLK(st.st_mode):
                raise ViewError(_("'%s' is not a block device" % path))

            major, minor = (os.major(st.st_rdev), os.minor(st.st_rdev))
            bdev = device.find_bdev(major, minor)
            assert(bdev)

            for group in disk.get_candidates():
                if bdev in group:
                    break
            else:
                raise ViewError(_('device is not valid for an installation'))

            disks.append(bdev)

        try:
            disk.check_candidates(disks)
        except disk.DiskError as e:
            raise ViewError(e)

        try:
            self._step.initialize(disks, preset)
        except partition.PartitionSetupError:
            logger.critical(_("disk(s) too small for a %s server setup") % preset)
            return

        self._step.process()
