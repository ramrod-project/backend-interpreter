"""Supervisor module

The Supervisor module...

TODO:
"""

from ctypes import c_bool
import logging
from multiprocessing import Pipe, Value
from os import environ, path as ospath, name as osname
from pkgutil import iter_modules
from sys import exit as sysexit
from time import asctime, gmtime, sleep, time

from src import linked_process
from plugins import *


def get_class_instance(plugin_name):
    """Returns class instances from 'plugins' folder.

    Returns:
        list -- List containing class instances of all plugins.
    """
    if osname == "nt":  # windows
        path = ospath.abspath(ospath.join(
            ospath.dirname(__file__),
            "../"
        )+"/plugins")
    else:  # linux
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

    # Initialize logger
    logging.basicConfig(
        filename="plugin_logfile",
        filemode="a",
        format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
    )
    LOGGER = logging.getLogger('supervisor')
    LOGGER.addHandler(logging.StreamHandler())
    LOGLEVEL = environ.get("LOGLEVEL", default="DEBUG")
    LOGGER.setLevel(LOGLEVEL)

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
        self.signal = Value(c_bool, False)

    @staticmethod
    def log(self, log):
        """The _to_log function is called by the
        class instance to send a collection of storted
        logs to the main logger. Iterate over list
        of [<component>, <log>, <severity>, <timestamp>]
        """
        date = asctime(gmtime(log[3]))
        self.LOGGER.log(
            log[2],
            log[1],
            extra={'date': date}
        )

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

        self.plugin_process = self._plugin_setup()

    def _create_process(self, instance, name):
        """Create a LinkedProcess

        This takes an object intsance and creates a
        LinkedProcess from it.

        Arguments:
            instance {callable} -- target function,

        Returns:
            {LinkedProcess} -- returns a LinkedProcess
        """
        created_process = linked_process.LinkedProcess(
            name=name,
            target=instance._start,
            signal=self.signal
        )
        return created_process

    def _plugin_setup(self):
        """Set up the plugin

        Create the plugin process and the pipe from the
        plugin to the logger.

        Returns:
            {Pipe} -- the receiving pipe from the plugin
            to the logger.
        """
        return self._create_process(
            self.plugin,
            self.plugin.name
        )

    def spawn_servers(self):
        """Spawn server processes

        This starts all...
        """
        try:
            if not self.plugin_process.start():
                raise RuntimeError
        except RuntimeError:
            self.teardown(99)

    def monitor(self):  # pragma: no cover
        """Monitor loop

        This method runs for the duration of the application lifecycle...
        """
        while True:
            try:
                sleep(1)
                if not self.plugin_process.restart():
                    self.teardown(self.plugin_process.get_exitcode())
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
        sysexit(code)
