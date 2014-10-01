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

        #
        # This has been checked by the frontend previously.
        #
        assert(args.disks)

        #
        # See if the device is valid and is knonw by udev: currently,
        # the user must pass valid disk(s). We might accept partition
        # devs too in the future.
        #
        for path in args.disks:
            st = os.stat(path)

            if not stat.S_ISBLK(st.st_mode):
                raise ViewError(_("'%s' is not a block device" % path))

            major, minor = (os.major(st.st_rdev), os.minor(st.st_rdev))
            bdev = device.find_bdev(major, minor)
            assert(bdev)

            if bdev.devtype != 'disk':
                raise ViewError(_('%s is not a disk.') % path)

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
