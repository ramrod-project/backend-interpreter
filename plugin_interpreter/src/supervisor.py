"""Supervisor module

The Supervisor module contains the class for the Supervisor
process. This process manages and monitors the database,
logger, controller, and plugin processes. It handles
class instancing, process creation, and process starting/
restarting.

TODO:
"""

__version__ = "0.1"
__author__ = "Christopher Manzi"


from ctypes import c_bool
from multiprocessing import Pipe, Value
from os import environ, getcwd, path as ospath
from pkgutil import iter_modules
from sys import modules as sysmods, exit as sysexit
from time import sleep

from customtcp import customtcp
from customudp import customudp
from src import central_logger, linked_process, rethink_interface
from plugins import *


def get_class_name(mod_name):
    """Gets the name of the class from a given module.

    The plugin class name must follow a specific naming
    convention (same as the module with a capital first
    letter).

    Arguments:
        mod_name {string} -- A name of a python module.

    Returns:
        string -- Name of the class in the python module.
    """
    suffix = mod_name.split("_")[1:]
    return "TestPlugin" + suffix[0]


def get_class_instances():
    """Returns class instances from 'plugins' folder.

    Returns:
        list -- List containing class instances of all plugins.
    """
    path = ospath.join("/" + ''.join([d + "/" for d in ospath.dirname(__file__).split("/")[:-1] if d]), "plugins")
    modules = iter_modules(path=[path])
    plugins = []

    for _, mod_name, _ in modules:
        if mod_name not in sysmods:
            loaded_mod = __import__("plugins." + mod_name, fromlist=[mod_name])
            class_name = get_class_name(mod_name)
            loaded_class = getattr(loaded_mod, class_name)
            plugins.append(loaded_class())
    return plugins


class SupervisorController:
    """Supervisor class

    The SupervisorController class functions as a parent and supervisor
    process for all 'sub-processes' spawned by this application. It serves
    the function of creation, monitoring, restarting (if needed), and
    terminating all Server, Plugin, and Database processes.

    Raises:
        KeyError -- If environment variable 'STAGE' isn't set to either
        'DEV' or 'PROD' to indicate development or production.
    """

    def __init__(self):
        """
        Properties:
            controller_processes - Handles to controller processes
            {<PROTO><PORT>: <HANDLE>}
            controllers - Controller class instances
            {<PROTO><PORT>: <INSTANCE>}
            plugin_processes - Handles to plugin processes
            {<NAME>: <HANDLE>}
            plugins - Plugin class instances
            [<PLUGIN1>, <PLUGIN2>, ...]
            db_interface - DatabaseInterface class instance
            db_process - Database interface process handle
        """
        self.controller_processes = {}
        self.controllers = {}
        self.plugin_processes = {}
        self.plugins = get_class_instances()
        self.db_interface = None
        self.db_process = None
        self.logger_instance = None
        self.logger_process = None
        self.logger_pipe = None
        self.signal = Value(c_bool, False)

    def create_servers(self):
        """Create all processes

        Create all of the class instances and processes required to run
        the servers, plugins, and database handler.
        """
        try:
            if environ["STAGE"] == "DEV" or environ["STAGE"] == "PROD":
                pass
            else:
                print("Environment variable STAGE must be set to DEV or PROD!")
                raise KeyError
        except KeyError:
            print("Environment variable STAGE must be set to DEV or PROD!")
            raise KeyError

        """Iterates over all loaded plugins. Creates a
        pipe to connect the plugin processes to their
        respective TCP/UDP servers. Uses plugin
        properties to determine which port/protocol
        is required and creates a server controller
        (if not already created). Create a multiprocessing 
        pipe for server <-> plugin communication
        and a pipe for logging."""
        logger_pipes = []

        for plugin in self.plugins:
            contoller_conn, plugin_conn = Pipe()
            log_receiver, log_sender = Pipe()

            # Handle plugins that use TCP
            if plugin.proto == "TCP":
                if plugin.proto + str(plugin.port) not in self.controllers:
                    self.controllers[plugin.proto
                                     + str(plugin.port)] = customtcp.CustomTCP(
                                         ("0.0.0.0", plugin.port),
                                         self.db_interface
                                         )

            # Handle plugins that use UDP
            elif plugin.proto == "UDP":
                if plugin.proto + str(plugin.port) not in self.controllers:
                    self.controllers[plugin.proto
                                     + str(plugin.port)] = customudp.CustomUDP(
                                         ("0.0.0.0", plugin.port),
                                         self.db_interface
                                         )

            """Connect the plugin to the appropriate controller by passsing
            it one end of the pipe, then create a process for the new 
            plugin (and pass it the other end of the pipe). Also pass 
            the process a pipe to the logger."""
            self.controllers[plugin.proto +
                             str(plugin.port)].connect_plugin(plugin.name,
                                                              contoller_conn)
            self.plugin_processes[plugin.name] = linked_process.LinkedProcess(
                name=plugin.name,
                target=plugin.start,
                pipe=plugin_conn,
                logger_pipe=log_sender,
                signal=self.signal
            )
            # Add other end of logging pipe to the collecxtion of log pipes
            logger_pipes.append(log_receiver)

        # Create controller processes for all requires controllers
        for name, controller in self.controllers.items():
            log_receiver, log_sender = Pipe()
            self.controller_processes[name] = linked_process.LinkedProcess(
                name=name,
                target=controller.start,
                pipe=None,
                logger_pipe=log_sender,
                signal=self.signal
            )
            logger_pipes.append(log_receiver)

        """Create RethinkInterface instance and process
        Checks if environment variable STAGE is DEV or PROD. This env
        variable is automatically set to PROD in the application 
        Dockerfile, but can be overridden."""
        if environ["STAGE"] == "DEV":
            self.db_interface = rethink_interface.RethinkInterface(
                self.plugins,
                ("127.0.0.1", 28015)
            )
        elif environ["STAGE"] == "PROD":
            self.db_interface = rethink_interface.RethinkInterface(
                self.plugins,
                ("rethinkdb", 28015)
            )
        log_receiver, log_sender = Pipe()
        self.db_process = linked_process.LinkedProcess(
            name="dbprocess",
            target=self.db_interface.start,
            pipe=None,
            logger_pipe=log_sender,
            signal=self.signal
        )
        logger_pipes.append(log_receiver)

        # Create pipe for Supervisor monitor to use
        log_receiver, self.logger_pipe = Pipe()
        logger_pipes.append(log_receiver)

        # Create CentralLogger instance and process
        self.logger_instance = central_logger.CentralLogger(logger_pipes)
        self.logger_process = linked_process.LinkedProcess(
            name="loggerprocess",
            target=self.logger_instance.start,
            signal=self.signal
        )

    def spawn_servers(self):
        """Spawn server processes

        This starts all of the servers, plugins, and database interface.
        It validates that they have started properly, if not exit with
        given code.
        """
        if environ["STAGE"] == "DEV":
            print("Starting servers and plugins, use <CRTL-C> to exit...")

        self.logger_process.start()
        self.db_process.start()

        for _, proc in self.controller_processes.items():
            proc.start()
        for _, proc in self.plugin_processes.items():
            proc.start()

    def monitor(self):
        """Monitor loop
        
        This method runs for the duration of the application lifecycle.
        It checks if processes are alive and attempts a restart as
        necessary. If it is unable to recover the process, it calls
        the teardown method with the exit code given from the child.
        """
        while True:
            try:
                sleep(3)
                for _, proc in self.controller_processes.items():
                    if not proc.is_alive() and not proc.restart():
                        self.teardown(proc.get_exitcode())
                for _, proc in self.plugin_processes.items():
                    if not proc.is_alive() and not proc.restart():
                        self.teardown(proc.get_exitcode())
                if not self.db_process.is_alive():
                    if not self.db_process.restart():
                        self.teardown(self.db_process.get_exitcode())
                if not self.logger_process.is_alive():
                    if not self.logger_process.restart():
                        self.teardown(self.logger_process.get_exitcode())
            except KeyboardInterrupt:
                self.teardown(0)

    def teardown(self, code):
        """Teardown all processes

        This method gracefully stops all processes managed by the
        supervisor. It sends a signal to the processes by changing
        the Value 'signal' to True. It then waits 5 seconds, and
        loops through all processes to terminate them if they have
        not already exited from the signal.
        
        Arguments:
            code {int} -- The exit code passed through by the
            monitoring loop (0 is normal, other codes can be
            passed by child processes)
        """
        if environ["STAGE"] == "DEV":
            print("\nStopping servers and plugins...\n")
        self.signal.value = True
        sleep(5)
        if environ["STAGE"] == "DEV":
            print("Exiting main process...")

        if self.db_process.is_alive():
            self.db_process.terminate()
        for _, proc in self.controller_processes.items():
            if proc.is_alive():
                proc.terminate()
                proc.join()
        for _, proc in self.plugin_processes.items():
            if proc.is_alive():
                proc.terminate()
                proc.join()
        if self.logger_process.is_alive():
            self.logger_process.terminate()
        sysexit(code)
