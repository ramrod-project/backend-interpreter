"""Custom UDP socket server
TODO:
- route based on database
- accept response and address from database interface
"""

from multiprocessing import Queue
from queue import Empty
from socket import(
    socket, AF_INET, SOCK_DGRAM, SOL_SOCKET, SO_REUSEADDR
)
from select import select
from sys import exit as sysexit
from threading import Thread
from time import sleep, time


class CustomUDP:
    """Custom class for UDP server. Handles UDP connections on
    a one port per instance basis. Simply forwards data to
    the Pipe()s it is given."""

    def __init__(self, server, db_instance):
        self.db_instance = db_instance
        self.client_queue = Queue()
        self.plugin_queue = Queue()
        self.pipes = {}
        self.server_address = server
        self.sock = socket(AF_INET, SOCK_DGRAM)

    def start(self, logger, signal):
        """Start the server

        Starts the UDP server and initializes the control
        loop.

        Arguments:
            logger {Pipe connection} -- Multiprocessing pipe connecting
            controller to the central logger.
            signal {Value} -- Multiprocessing boolean Value used by the
            Supervisor for sending a kill signal.
        """
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sock.bind(self.server_address)
        self.sock.settimeout(3)

        collector = Thread(target=self._collector, daemon=True)
        collector.start()

        logger.send([
            ''.join(("UDP", str(self.server_address[1]))),
            "Listening for UDP data",
            10,
            time()
        ])

        while True:
            try:
                if signal.value:
                    logger.send([
                        ''.join(("UDP", str(self.server_address[1]))),
                        "Received kill signal, stopping...",
                        20,
                        time()
                    ])
                    self._stop()

                readable, writeable, _ = select(
                    [self.sock],
                    [self.sock],
                    [],
                    0.1
                )

                client_ip, client_address, data = None, None, None
                if self.sock in readable:
                    try:
                        data, client_address = self.sock.recvfrom(1024)
                    except OSError as err:
                        logger.send([
                            ''.join(("UDP", str(self.server_address[1]))),
                            str(err),
                            10,
                            time()
                        ])
                    finally:
                        client_ip, client_port = client_address
                        if data:
                            self.plugin_queue.put([
                                client_ip,
                                client_port,
                                data
                            ])
                if self.sock in writeable:
                    try:
                        data = self.client_queue.get_nowait()
                        self.sock.sendto(data)
                    except Empty:
                        continue
            except KeyboardInterrupt:
                continue
            except Exception as ex:
                logger.send([
                    ''.join(("UDP", str(self.server_address[1]))),
                    ''.join(["Received ", str(ex), ", stopping..."]),
                    50,
                    time()
                ])
                self._stop()

    def _collector(self):
        """Pipe collector thread

        The collector runs as a thread that collects data
        from the send/receive pipes and places it into
        queues.
        """
        while True:
            # Check pipe for incoming data
            if self.pipes["test2"].poll(timeout=0.1):
                self.client_queue.put(self.pipes["test2"].recv())
            try:
                received = self.plugin_queue.get_nowait()
                client_ip, client_port, data = received
                self.pipes["test2"].send([
                    client_ip,
                    client_port,
                    data
                ])
            except Empty:
                pass
            sleep(1)

    def connect_plugin(self, name, pipe):
        """Connect a plugin

        Connect a plugin to this server by adding a pipe
        to the self.pipes dict.

        Arguments:
            name {string} -- Name of the plugin.
            pipe {Pipe} -- Multiprocessing pipe connected to
            the plugin.
        """
        self.pipes[name] = pipe

    def _stop(self):
        """Stop the server

        Stop is called by the main control loop when
        the kill command is given or an unhandled exception
        occurs.
        """
        if self.sock:
            self.sock.close()
        for _, pipe in self.pipes.items():
            pipe.close()
        sysexit(0)
