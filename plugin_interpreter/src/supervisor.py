"""Supervisor module

The Supervisor module...

TODO:
- Add handler class for SIGTERM event (docker stop is received)
"""

__version__ = "0.2"
__author__ = "Christopher Manzi"


from ctypes import c_bool
from multiprocessing import Pipe, Value
from os import environ, getcwd, path as ospath, name as osname
from pkgutil import iter_modules
from sys import modules as sysmods, exit as sysexit
from time import sleep

from src import central_logger, linked_process, rethink_interface
from plugins import *


def get_class_instance(plugin_name):
    """Returns class instances from 'plugins' folder.

    Returns:
        list -- List containing class instances of all plugins.
    """
    if (osname == "nt"):
        path = ospath.abspath(ospath.join(ospath.dirname(__file__), "../")+"/plugins")
    else: #leaving functional linux path generation in place, windows might work on linux too.
        path = ospath.join(
            "/" + ''.join([
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
        self.logger_process = None
        self.signal = Value(c_bool, False)

    def create_servers(self):
        """Create all processes

        Create all of the class instances and processes required to run
        the servers, plugins, and database handler.
        """
        try:
            if environ["STAGE"] == "DEV" or environ["STAGE"] == "PROD" or environ["STAGE"] == "TESTING":
                pass
            else:
                print("Environment variable STAGE must be set to DEV or PROD!")
                raise KeyError
        except KeyError:
            print("Environment variable STAGE must be set to DEV or PROD!")
            raise KeyError

        logger_pipes = []

        """Create plugin process..."""
        log_receiver, log_sender = Pipe()

        self.plugin_process = linked_process.LinkedProcess(
            name=self.plugin.name,
            target=self.plugin.start,
            logger_pipe=log_sender,
            signal=self.signal
        )
        logger_pipes.append(log_receiver)

        """Create RethinkInterface instance and process
        Checks if environment variable STAGE is DEV or PROD. This env
        variable is automatically set to PROD in the application 
        Dockerfile, but can be overridden."""
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

        log_receiver, log_sender = Pipe()
        self.db_process = linked_process.LinkedProcess(
            name="dbprocess",
            target=self.db_interface.start,
            logger_pipe=log_sender,
            signal=self.signal
        )
        logger_pipes.append(log_receiver)

        """Supervisor pipe for logging"""
        log_receiver, self.logger_pipe = Pipe()
        logger_pipes.append(log_receiver)

        """Create CentralLogger instance and process"""
        self.logger_instance = central_logger.CentralLogger(logger_pipes, environ["LOGLEVEL"])
        self.logger_process = linked_process.LinkedProcess(
            name="loggerprocess",
            target=self.logger_instance.start,
            signal=self.signal
        )

    def spawn_servers(self):
        """Spawn server processes

        This starts all...
        """
        try:
            if not self.logger_process.start():
                raise RuntimeError
            if not self.db_process.start():
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
        processes = [self.plugin_process, self.db_process, self.logger_process]
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

        if self.db_process.is_alive():
            self.db_process.terminate()
        if self.plugin_process.is_alive():
            self.plugin_process.terminate()
        if self.logger_process.is_alive():
            self.logger_process.terminate()
        sysexit(code)
