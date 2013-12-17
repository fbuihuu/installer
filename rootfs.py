from threading import Thread, Event
from Queue import Queue

#
# Note: the run() method of Work is run in a seperate thread so be
# carefull.
#
class Work(object):

    STATE_INIT    = -1
    STATE_SUCCESS = 0
    STATE_FAILED  = 1

    def __init__(self, name):
        self.name = name
        self._state = STATE_INIT

    @property
    def state(self):
        return self._state

    def execute(self):
        raise NotImplementedError()

    def callback(self):
        pass


class RootFS(object):

    def __init__(self):
        self.__device = None
        self.__canceled_works = []
        self.__works = []
        self.__worker = Thread(name="rootfs-finalizer", target=self.__do_finalize)
        self.__terminated = Event()
        self.__terminated.set()
        self.is_synchronized = False
        self.workqueue = Queue()

    # schedule a work that will be executed inside the rootfs (chrooted)
    def schedule_work(self, work):
        # put in the work queue
#        self.logger("scheduling new work '%s'" % work.name)
        self.workqueue.put(work)

    def cancel_work(self, work):
        # Remove from the workqueue.
        # FIXME: does it need a lock or is it already protected by the
        # "big" lock ?
        self.__canceled_works.append(work)

    def mount(self, node):
        self.__device = node
        self.__mntpoint = mktemp()
        # FIXME: os.system("mount ...")
        if self.is_synchronized:
            self.__finalizer__enter()

    def umount(self):
        self.__finalizer_exit()
        # FIXME: os.system("umount " + self.__device)
        # FIXME: os.system("rmdir  " + self.__mntpoint)
        self.__device = None
        self.__mntpoint = None

    def synchronize(self, source):
        self.__finalizer_exit()
        # FIXME: rsync -av source/ self.__path
        self.is_synchronized = True
        self.__finalizer__enter()

    def __finalizer__enter(self):
        if self.__terminated.is_set():
            self.__terminated.clear()
            self.__worker.start()

    def __finalizer_exit(self):
        if not self.__terminated.is_set():
            self.__terminated.set()
            # put a dummy work which should wake up the worker thread. It
            # will then notice it's time to stop.
            w = Work("terminator")
            self.schedule_work(w)
            self.__worker.join()

    def __do_finalize(self):
        while not self.__terminated.is_set():
            w = self.workqueue.get()
            if w in self.__canceled_works:
                self.__canceled_works.remove(work)
            else:
                w.execute()


class RootfsThread(Thread):

    def __init__(self, rootfs):
        super(RootfsThread, self).__init__()
        self.rootfs = rootfs

    def run(self):
        pass

    def terminate(self):
        pass
