"""
The CentralLogger class is a wrapper for a global app
logger. It's instantiated with a collection of pipes to
each process that are used for transmitting logs.
"""

# TODO:
# - add option for logging to stdout or file based on
# value of 'STAGE' env variable.

import logging
from multiprocessing import Lock
from os import environ
from select import select
from sys import stdout, exit as sysexit
from time import asctime, gmtime, sleep, time


class CentralLogger():

    def __init__(self, pipes, level):
        # pipes must be a list to be used with select
        if type(pipes) == list:
            self.pipes = pipes
        else:
            raise TypeError
        logging.basicConfig(format='%(date)s %(name)-12s %(levelname)-8s %(message)s')
        self.lock = Lock()
        self.logger = logging.getLogger('central')
        self.logger.setLevel(logging.DEBUG)
        if level == "INFO":
            self.logger.setLevel(logging.INFO)
        elif level == "WARNING":
            self.logger.setLevel(logging.WARNING)
        elif level == "ERROR":
            self.logger.setLevel(logging.ERROR)
        elif level == "CRITICAL":
            self.logger.setLevel(logging.CRITICAL)

    def start(self, logger, signal):
        """The start() function runs as a Process()
        and checks pipes for logs.
        """
        # handler = logging.StreamHandler(stdout)
        # handler.setLevel(logging.DEBUG)
        # self.logger.addHandler(handler)

        last_pass = False
        while True:
            try:
                if signal.value:
                    last_pass = True
                    sleep(1)
                readable, _, _ = select(self.pipes, [], [], 1)
                logs = []
                for p in readable:
                    logs.append(p.recv())
                self._to_log(logs)
                if last_pass:
                    self.logger.log(20, "loggerprocess: Kill signal received, stopping...", extra={ 'date': asctime(gmtime(time())) })
                    self._stop()
            except KeyboardInterrupt:
                continue
            except Exception as ex:
                self.logger.log(50, "loggerprocess: " + str(ex) + ", stopping...", extra={ 'date': asctime(gmtime(time())) })
                self._stop()

    def _to_log(self, logs):
        """The _to_log function is called by the
        class instance to send a collection of storted
        logs to the main logger. Iterate over list
        of [<component>, <log>, <severity>, <timestamp>]
        """
        self.lock.acquire()
        for log in logs:
            date = asctime(gmtime(log[3]))
            self.logger.log(log[2], log[0] + ": " + log[1], extra={ 'date': date })
        self.lock.release()

    def _stop(self):
        """_stop() is called by the instance when
        the application signal is given to stop.
        """
        for pipe in self.pipes:
            pipe.close()
        sysexit(0)
