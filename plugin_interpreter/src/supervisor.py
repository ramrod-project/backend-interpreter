"""Supervisor module

The Supervisor module...

TODO:
- Add handler class for SIGTERM event (docker stop is received)
"""

__version__ = "0.3"
__author__ = "Christopher Manzi/Luke Hitch/Matt Trippy"


from ctypes import c_bool
from multiprocessing import Pipe, Value
from os import environ, path as ospath, name as osname
from pkgutil import iter_modules
from sys import exit as sysexit
from time import sleep

from src import central_logger, linked_process, rethink_interface
from plugins import *


def get_class_instance(plugin_name):
    """Returns class instances from 'plugins' folder.

    Returns:
        list -- List containing class instances of all plugins.
    """
    if osname == "nt": # windows
        path = ospath.abspath(ospath.join(
            ospath.dirname(__file__),
            "../"
        )+"/plugins")
    else: # linux
        path = ospath.join(
            "/" + "".join([
                d + "/" for d in ospath.dirname(__file__).split("/")[:-1] if d
            ]),
            "plugins"
        )
    modules = iter_modules(path=[path])

    for _, mod_name, _ in modules:
        if mod_name == plugin_name:
            loaded_mod = __import__("plugins." + mod_name, fromlist=[mod_name])
            loaded_class = getattr(loaded_mod, plugin_name)
            return loaded_class()
    return None


class SupervisorController:
    """Supervisor class

    The SupervisorController class...

    Raises:
        KeyError -- If environment variable 'STAGE' isn't set to either
        'DEV' or 'PROD' to indicate development or production.
        FileNotFoundError -- If the plugin file specified cannot be found.
    """

    def __init__(self, plugin_name):
        """
        Properties:
            plugin_process - Handle to plugin process
            plugin - Plugin class instance
            db_interface - DatabaseInterface class instance
            db_process - Database interface process handle
        """
        self.plugin_process = None
        self.plugin = get_class_instance(plugin_name)
        if not self.plugin:
            raise FileNotFoundError
        self.db_interface = None
        self.db_process = None
        self.logger_instance = None
#        self.logger_pipe = None
        self.logger_process = None
#        self.signal = Value(c_bool, False)

    def create_servers(self):
        """Create all processes

        Create all of the class instances and processes required to run
        the servers, plugins, and database handler.
        """
        try:
            if environ["STAGE"] not in ["DEV", "TESTING", "PROD"]:
                print("Environment variable STAGE must \
                      be set to DEV, TESTING, or PROD!")
                raise KeyError
        except KeyError:
            print("Environment variable STAGE must be set \
                  to DEV, TESTING, or PROD!")
            raise KeyError

#        logger_pipes = []

        logger_pipes.append(self._plugin_setup())
        # logger_pipes.append(self._create_rethink_interface())

        log_receiver, self.logger_pipe = Pipe()
        logger_pipes.append(log_receiver)

        self.create_logger(logger_pipes)

    def create_logger(self, logger_pipes):
        """Set up the logger

        Sets up the central logger instance and process.

        Arguments:
            logger_pipes {list} -- a list of pipes
            to receive logs from
        """
        self.logger_instance = central_logger.CentralLogger(
            logger_pipes,
            environ["LOGLEVEL"]
        )
        self.logger_process, _ = self._create_process(
            self.logger_instance,
            "loggerprocess"
        )

    def _create_process(self, instance, name):
        """Create a LinkedProcess

        This takes an object instance and creates a
        LinkedProcess from it.

        Arguments:
            instance {[type]} -- [description]

        Returns:
            {tuple}(LinkedProcess, Pipe) -- returns a LinkedProcess
            and a Pipe for the log receiver
        """
        log_receiver, log_sender = Pipe()
        target = instance.start
        print(name)
        if name == "loggerprocess":
            log_sender = None
        else:
            target = instance._start

        created_process = linked_process.LinkedProcess(
            name=name,
            target=target,
            logger_pipe=log_sender,
            signal=self.signal
        )
        return (created_process, log_receiver)

    def plugin_setup(self):
        """Set up the plugin

        Create the plugin and associated logging for the plugin

        Returns:
            {Pipe} -- the receiving pipe from the plugin
            to the logger.
        """
        self.plugin_process, log_receiver = self._create_process(
            self.plugin,
            self.plugin.name
        )
        return log_receiver

    def create_db_interface(self):
        """Set up the db interface, currently limited to rethinkdb

        Create RethinkInterface instance and process

        Checks if environment variable STAGE is DEV/TESTING/PROD.

        Returns:
            Logging handler object for the logger from the rethink
            interface.
        """
        if environ["STAGE"] == "TESTING":
            self.db_interface = rethink_interface.RethinkInterface(
                self.plugin,
                ("127.0.0.1", 28015)
            )
        else:
            self.db_interface = rethink_interface.RethinkInterface(
                self.plugin,
                ("rethinkdb", 28015)
            )

        self.db_process, log_receiver = self._create_process(
            self.db_interface,
            "dbprocess"
        )
        return log_receiver

    def spawn_servers(self):
        """Spawn server processes

        This starts all...
        """
        try:
            if not self.logger_process.start():
                raise RuntimeError
            if not self.plugin_process.start():
                raise RuntimeError
        except RuntimeError as err:
            print(err)
            self.teardown(99)

    def monitor(self):
        """Monitor loop

        This method runs for the duration of the application lifecycle...
        """
        processes = [self.plugin_process, self.logger_process]
        while True:
            try:
                sleep(3)
                for proc in processes:
                    if not proc.restart():
                        self.teardown(proc.get_exitcode())
            except KeyboardInterrupt:
                self.teardown(0)

    def teardown(self, code):
        """Teardown all processes

        This method gracefully stops all processes...

        Arguments:
            code {int} -- The exit code passed through by the
            monitoring loop (0 is normal, other codes can be
            passed by child processes)
        """
        self.signal.value = True
        sleep(5)

        if self.plugin_process.is_alive():
            self.plugin_process.terminate()
        if self.logger_process.is_alive():
            self.logger_process.terminate()
        sysexit(code)
