"""***Plugin Template Module***"""

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
    (["UDP" or "TCP"], PORT). This information will be used by the
    supervisor to ensure a server is started to handle the network
    connections for the plugin.
    #
    The initialize_queues method *SHOUD NOT* be overridden by the
    inheriting class, as the Supervisor will attempt to initialize
    the command queues in the exact way prescribed below. The abstract
    method 'start' *MUST BE* overridden by the inheriting class and
    must take one argument, which is a multiprocessing Pipe() which
    connects it to the server which handles its client connections.
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
        # Unique identifier for the plugin
        self.name = name
        # Pipe to connect to TCP/UDP server
        self.pipe = None
        # defines server socket requirement
        self.proto, self.port = proto, port
        # Initialize Abstract Base Class
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
    def start(self, logger, conn, signal):
        """Start the plugin

        The 'start' method is expected to be a control loop which
        is handles incoming client data from 'conn' - a Pipe() to
        the server handing its network socket, commands received from
        the 'recv_queue', and responses send back through the 'send_queue'.
        It is an abstract method that must be overridden by the
        inheriting class.

        It is recommended to run the control loop using multiple
        threads (methods provided below) so that all of the
        communication can be handled concurrently.

        'start' is used by the supervisor to create a separate Process()
        the plugin after instantiation and initialization. In order to
        function properly, it must take exactly one argument which is
        the previously mentioned Pipe().

        Plugin processes started by the Supervisor will be monitored
        through the Process().is_alive() method. I the process exits,
        the Supervisor will attempt to call the 'start' method again
        to restart the process.

        Arguments:

            logger {Pipe} -- A Pipe to the central logger, used for
            sending logs.
            conn {Pipe} -- A Pipe to connect to the server which serves
            this plugin process.
            signal {Value} -- A multiprocessing boolean Value which
            notifies the process that it should stop (kill switch).
        
        """
        self.pipe = conn
        lock = Lock()

        transmit_queue = Queue()
        receive_queue = Queue()

        server_receive = Thread(target=self._server_rx_thread,
                                args=(receive_queue, lock), daemon=True)
        server_transmit = Thread(target=self._server_tx_thread,
                                 args=(transmit_queue, lock), daemon=True)

        server_receive.start()
        server_transmit.start()

        while True:
            try:
                if signal.value:
                    self._stop()
                try:
                    address, data = receive_queue.get_nowait()
                    self.db_send.put(self.name, address, data)
                except Empty:
                    sleep(0.1)
                    continue

                try:
                    address, data = self.db_recv.get_nowait()
                    transmit_queue.put(address, data)
                except Empty:
                    sleep(0.1)
                    continue
                if not server_receive.is_alive() or not server_transmit.is_alive():
                    raise RuntimeError("Server thread(s) dead!")
            except KeyboardInterrupt:
                continue
            except RuntimeError as ex:
                print(ex)
                self._stop()

    """
    Control threads for server concurrency
    """
    def _server_rx_thread(self, receive_queue, lock):
        while True:
            lock.acquire(timeout=0.1)
            try:
                if self.pipe.poll(0.1):
                    client_ip, client_port, data = self.pipe.recv()
                    address = (client_ip, client_port)
                    receive_queue.put(address, data)
            finally:
                lock.release()

    def _server_tx_thread(self, transmit_queue, lock):
        while True:
            try:
                data = transmit_queue.get_nowait()
                lock.acquire()
                try:
                    self.pipe.send(data)
                finally:
                    lock.release()
            except Empty:
                continue

    @abstractmethod
    def _stop(self):
        """Stop the plugin

        This method should be used and called when the exit signal
        is sent to the program subprocesses. Execute any cleanup
        required.
        """
        if self.pipe:
            self.pipe.close()
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
        pass
        """
