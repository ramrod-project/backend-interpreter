"""
The LinkedProcess class is a wrapper for the multiprocessing
Process class. It allows processes to be restarted if they die
and stores the Pipe() being used by the process.
"""

from multiprocessing import connection, Process, sharedctypes
from time import sleep, time

LOGGER_NAME = "loggerprocess"
LOG_PIPE = "logger_pipe"
LP_TARGET = "target"
LP_SIGNAL = "signal"
LP_NAME = "name"
BASE_CONNECTION = connection._ConnectionBase

class LinkedProcess:
    """
    The LinkedProcess class is a wrapper for a single mutliprocessing
    Process() object. The primary purpose for this class is to procide
    the ability to restart a Process() if it has exited. It takes
    an optional Pipe() conection object.
    """
    def __init__(self, **kwargs):
        self.name = kwargs[LP_NAME]
        if self._verify_init_kwargs(**kwargs):  # might throw TypeError
            self.logger_pipe = None
            if self.name is not LOGGER_NAME:
                self.logger_pipe = kwargs[LOG_PIPE]
            self.proc = None
            self.target = kwargs[LP_TARGET]
            self.signal = kwargs[LP_SIGNAL]

    def _verify_init_kwargs(self, **kwargs):
        """
        May raise typeerror if the params are not correct

        1. kwargs["logger_pipe"], it must be a (c) connection or (n) None
        2. kwargs["target"] must be a callable function
        3. kwargs["signal"] must be a Synchronized signal

        any check fails, this raises typeerror

        :param kwargs:
        :return: <bool>
        """
        good_args = False
        if (kwargs[LOG_PIPE] and isinstance(kwargs[LOG_PIPE],
                                            BASE_CONNECTION)
                or not kwargs[LOG_PIPE] ) \
                and callable(kwargs["target"]) \
                and isinstance(kwargs["signal"],
                               sharedctypes.Synchronized):
            good_args = True
        else:
            raise TypeError("Bad LP Args {}".format(kwargs))
        return good_args

    def start(self):
        """Create process and start"""
        self.proc = Process(
            target=self.target,
            name=self.name,
            args=(self.logger_pipe, self.signal)
        )

        try:
            self.proc.start()
        except Exception as ex:
            print(ex)
            exit(99)

        #  Validate that the process started successfully
        return self._did_start()

    def restart(self):
        """Restart (create and start a new instance)
        of the process.

        Returns:
            bool -- Process is alive (or not)
        """
        if not self.proc:
            log_str = "{} never started, cannot restart".format(self.name)
            self._log_create(log_str, level=20)
            return False
        if self.is_alive():
            return True
        else:
            self._log_create("{} restarting...".format(self.name),
                             level=20)
            self.start()
            return self._did_start()

    def check_alive_until(self, done_time, expected):
        """
        Checks is_alive until done_time has pased
        or
        expected condition is met

        returns if the condition has been met in the given time

        :param done_time: <float> time.time()
        :param expected:  <bool> expects condition alive or dead
        :return: <bool> if the expected condition is met in the given time

        """
        expectation_met = False
        while not expectation_met and time() < done_time:
            expectation_met = expected == self.is_alive()
            if not expectation_met:
                sleep(0.5)
        return expectation_met

    def is_alive(self):
        """
        Check to see if contained process is alive.

        Returns:
            Boolean -- Return False if process doesn't exist or
            is dead, othewise True.
        """
        if not self.proc:
            self._log_create("{} not started!".format(self.name),
                             level=20)
            return False
        if self.proc.is_alive():
            return True
        return False

    def join(self):
        """
        Implements the Process.join() function.

        Returns:
            Method -- join() process method, blocks until
            process terminates.
        """
        return self.proc.join()

    def get_exitcode(self):
        """Returns the last process exit code.

        Returns:
            int -- Process exit code.
        """
        return self.proc.exitcode

    def terminate(self):
        """Terminate process"""
        if self.proc \
                and self.is_alive() \
                and (self.proc.terminate() is None) \
                and self.check_alive_until(time() + 3, False):
            log = "{} terminated with exit code {}".format(self.name,
                                                           self.get_exitcode())
            self._log_create(log,
                             level=20)
        else:
            log = "{} failed to terminate".format(self.name)
            self._log_create(log,
                             level=20)

    def _did_start(self):
        begin = time()
        while time() - begin < 5:
            if self.is_alive() and time() - begin > 3:
                self._log_create("{} started!".format(self.name),
                                 level=20)
                return True
            sleep(0.5)
        self._log_create("{} failed to start!".format(self.name),
                         level=50)
        return False

    def _log_create(self, log_str, level=20, timestamp=None):
        timestamp = timestamp or time()
        self._log([self.name,
                   log_str,
                   level,
                   timestamp])

    def _log(self, message):
        if self.logger_pipe:
            self.logger_pipe.send(message)
