"""Plugin Template Module
"""

from abc import ABC, abstractmethod
from multiprocessing import Lock, Queue
from queue import Empty
from sys import exit as sysexit
from threading import Thread
from time import sleep


class ControllerPlugin(ABC):
    """
    The ControllerPlugin class is an Abstract Base Class from which plugin
    subclasses can be derived. Plugins should inherit this base class and
    implement any subset of its methods that is required.
    #
    For proper instantiation, plugin subclasses should be initialized
    with a 'name' string, and a 'server' tuple of the form
    (["UDP" or "TCP"], PORT). This information will be used to
    keep track of which network resources are allocated to which
    plugins.
    #
    The initialize_queues method *SHOUD NOT* be overridden by the
    inheriting class, as the Supervisor will attempt to initialize
    the command queues in the exact way prescribed below. The abstract
    methods 'start' and '_stop' *MUST BE* overridden by the inheriting
    class. 
    #
    'start' and must take two arguments, a multiprocesing Pipe()
    connecting the process to a central application logger, and a Value
    of boolean type, which serves as a kill signal for the process (when
    set to True). 
    """

    def __init__(self, name, proto, port):
        self.db_send = None
        self.db_recv = None
        self.functionality = []
        """
        List of dictionaries which advertises functionality of the plugin.
        Example:
        [
            {
                "name": "read_file",
                "input": ["string"],
                "family": "filesystem",
                "tooltip": "Provided a full directory path, this function reads a file.",
                "reference": "<reference url>"
            },
            {
                "name": "send_file",
                "input": ["string", "binary"],
                "family": "filesystem",
                "tooltip": "Provided a file and destination directory, this function sends a file.",
                "reference": "<reference url>"
            }
        ]
        The 'name' key is the unique identifier used to refer to the function
        in communication between the front end interface and the back end.
        This exact identifier will be sent back with corresponding commands to let
        the plugin know which funcion should be called.

        The 'input' key is a list of required input types to properly call
        the function. Possible input types include: string, int, binary.

        The 'tooltip' key is a human readable explanation of the function usage. It
        will be displayed to the user through the interface.
        """
        self.name = name
        """Define server port/proto requirement (TCP/UDP) so docker can be run
        properly."""
        self.proto, self.port = proto, port
        super().__init__()

    def initialize_queues(self, send_queue, recv_queue):
        """Initialize command/response queues

        The 'initialize_queues' method is called by the Supervisor with
        two multiprocessing.Queue() instances with send_queue being the
        response queue owned by the RethinkInterface instanc, and
        recv_queue being a unique command queue used by the RethinkInterface
        process to communicate with the plugin process.
        #
        These queues follow a defined message format depending on the
        action which is being requested (in the case of the recv_queue),
        or the data which is being sent back (send_queue). These message
        formats are defined below above their respective methods.
        
        Arguments:
            send_queue {Queue} -- The queue used to send responses back to the
            database interface.
            recv_queue {Queue} -- The queue used to receive commands from the
            frontend through the database.
        """
        self.db_send = send_queue
        self.db_recv = recv_queue

    @abstractmethod
    def start(self, logger, signal):
        """Start the plugin

        The 'start' method is...
        
        """
        pass

    @abstractmethod
    def _stop(self):
        """Stop the plugin

        This method should be used and called when the exit signal
        is sent to the program subprocesses. Execute any cleanup
        required.
        """
        sysexit(0)

    """
    The rest of the class methods should be non-public functions
    (_function) that implement the functionality of the plugin.
    These can then be called from the control loop whenever the
    appropriate command is received.

    Example:
    
    ***Config***
    
    Used to pass some configuration data to the client.
    def _config(self):
        pass"""
