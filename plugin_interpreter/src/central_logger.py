"""
The CentralLogger class is a wrapper for a global app
logger. Each plugin will use this logging function to
establish logging.
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

logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)

class CentralLogger():

    def __init__(self, level):
        # pipes must be a list to be used with select
        if isinstance(level, str):
            self.level = level
        else:
            raise TypeError
        self.logger = logging.getLogger('central')
        self.logger.addHandler(logging.StreamHandler())
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
        """Start the logger

        The 'start' method is used as a target for the
        LinkedProcess that is run by the Supervisor.
        
        Arguments:
            logger  -- the central logger object to be
            used for the plugin to be stood up
        """
        last_pass = False
        while True:
            try:
                if signal.value:
                    # Do one last pass to catch any logs
                    last_pass = True
                    sleep(1)
#                readable, _, _ = select(self.pipes, [], [], 1)
#                logs = []readable
                for p in readable:
                    logs.append(p.recv())
                self._to_log(logs)
                if last_pass:
                    self._stop()
            except KeyboardInterrupt:
                continue
            except TypeError:
                self._stop_exception("improperly formatted log")
            except IndexError:
                self._stop_exception("improper log list length")
            except Exception as ex:
                self._stop_exception(ex)

    def _to_log(self, logs):
        """The _to_log function is called by the
        class instance to send a collection of sorted
        logs to the main logger. Iterate over list
        of [<component>, <log>, <severity>, <timestamp>]
        """
        for log in logs:
            date = asctime(gmtime(log[3]))
            self.logger.log(
                log[2],
                "".join([log[0], ": ", log[1]]),
                extra={ 'date': date }
            )

    def _stop(self):
        """_stop() is called by the instance when
        the application signal is given to stop.
        """
        self.logger.log(
            20,
            "loggerprocess: Kill signal received, \
            stopping...",
            extra={
                "date": asctime(gmtime(time()))
            }
        )
        for pipe in self.pipes:
            pipe.close()
        sysexit(0)

    def _stop_exception(self, ex):
        """_stop_exception() is called by the instance
        when an unhandled exception occurs and the process
        tmust exit.
        """
        self.logger.log(
            50,
            "loggerprocess: " 
            + str(ex) 
            + ", stopping...",
            extra={ 'date': asctime(gmtime(time()))
            }
        )
        for pipe in self.pipes:
            pipe.close()
        sysexit(99)
