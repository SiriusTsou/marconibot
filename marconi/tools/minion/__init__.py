from . import Thread, logging

logger = logging.getLogger(__name__)


class Minion(object):
    """ Minions control child processes that do the Daemon's bidding. """

    def start(self):
        """ Start Minion.run Process """
        self.__thread = Thread(target=self.run)
        self.__thread.daemon = True
        self._running = True
        self.__thread.start()

    def stop(self):
        """ Force the Minion to stop """
        self._running = False
        try:
            self.__thread.join()
        except Exception as e:
            logger.exception(e)

    def run(self):
        """ Method ran in a child process. It should be over written when
        subclassed """
        self.stop()
