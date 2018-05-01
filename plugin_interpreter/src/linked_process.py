"""
The LinkedProcess class is a wrapper for the multiprocessing
Process class. It allows processes to be restarted if they die
and stores the Pipe() being used by the process.
"""

from multiprocessing import connection, Process, sharedctypes, Value
from time import sleep, time


class LinkedProcess:
    """
    The LinkedProcess class is a wrapper for a single mutliprocessing
    Process() object. The primary purpose for this class is to procide
    the ability to restart a Process() if it has exited. It takes
    an optional Pipe() conection object.
    """
    def __init__(self, **kwargs):
        self.name = kwargs["name"]
        self.logger_pipe = None
        if self.name is not "loggerprocess":
            self.logger_pipe = kwargs["logger_pipe"]
        if not isinstance(self.logger_pipe, connection._ConnectionBase:
            raise TypeError
        self.proc = None
        self.target = kwargs["target"]
        if not callable(self.target):
            raise TypeError
        self.signal = kwargs["signal"]
        if not isinstance(self.signal, sharedctypes.Synchronized):
            raise TypeError

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

        """Validate that the process started successfully"""
        return self._did_start()

    def restart(self):
        """Restart (create and start a new instance)
        of the process.
        
        Returns:
            bool -- Successful restart (or not)
        """

        if not self.proc:
            self._log([
                self.name,
                "".join((
                    self.name,
                    " never started, cannot restart."
                )),
                20,
                time()
            ])
            return False
        if not self.is_alive():
            self._log([
                self.name,
                "".join((self.name, " restarting...")),
                20,
                time()
            ])
            self.start()
            return self._did_start()
        else:
            self._log([
                self.name,
                "".join((self.name, " already running.")),
                20,
                time()
            ])
        return False

    def is_alive(self):
        """Check to see if contained process is alive.
        
        Returns:
            Boolean -- Return False if process doesn't exist or 
            is dead, othewise True.
        """
        if not self.proc:
            self._log([
                self.name,
                "".join((self.name, " not started!")),
                20,
                time()
            ])
            return False
        if self.proc.is_alive():
            return True
        return False

    def join(self):
        """Implements the Process.join() function.
        
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
        if self.proc and self.is_alive():
            self.proc.terminate()
            now = time()
            while time() - now < 3:
                if not self.is_alive():
                    break
                sleep(0.5)
            self._log([
                self.name,
                "".join([
                    self.name,
                    " terminated with exit code ",
                    str(self.get_exitcode())
                ]),
                20,
                time()
            ])
        
    def _did_start(self):
        begin = time()
        while time() - begin < 5:
            if self.is_alive() and time() - begin > 3:
                self._log([
                    self.name,
                    "".join((self.name, " started!")),
                    20,
                    time()
                ])
                return True
            sleep(0.5)
        self._log([
            self.name,
            "".join((self.name, " failed to start!")),
            50,
            time()
        ])
        return False

        def _log(self, message):
            if self.logger_pipe:
                self.logger_pipe.send(message)
