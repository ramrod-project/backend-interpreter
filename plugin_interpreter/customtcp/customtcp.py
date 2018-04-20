"""***Custom TCP socket server***"""
# TODO:
# - route based on database
# - accept response and address from database interface

from multiprocessing import Queue
from queue import Empty
from socket import(
    socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEADDR, SO_LINGER
    )
from select import select
from struct import pack
from sys import exit as sysexit
from threading import Thread
from time import sleep, time


class CustomTCP:
    """Custom class for TCP server. Handles TCP connections on
    a one port per instance basis. Simply forwards data to
    the Pipe()s it is given."""

    def __init__(self, server, db_instance):
        self.connections = []
        self.connections_mapping = {}
        self.connections_reverse = {}
        self.db_instance = db_instance
        self.plugin_queue = Queue()
        self.pipes = {}
        self.server_address = server
        self.sock = socket(AF_INET, SOCK_STREAM)

    def start(self, logger, signal):
        """Start server

        The method 'start' is used by the Supervisor process
        to intsantiate a Process() using an instance of this
        class. This functions as a control loop to handle incoming
        TCP connections.

        Arguments:
            logger {Pipe connection} -- Multiprocessing pipe for sending
            logs to the central logger.
            signal {Value} -- A boolean multiprocessing Value
            for the Supervisor to send a kill signal.
        """
        self.sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        self.sock.bind(self.server_address)
        self.sock.listen(5)
        self.sock.settimeout(1)

        self.connections.append(self.sock)

        collector = Thread(target=self._collector, daemon=True)
        collector.start()

        logger.send([
            ''.join(("TCP", str(self.server_address[1]))),
            "Listening for TCP connections",
            10,
            time()
        ])
        while True:
            try:
                if signal.value:
                    logger.send([
                        ''.join(("TCP", str(self.server_address[1]))),
                        "Received kill signal, stopping...",
                        20,
                        time()
                    ])
                    self._stop()

                readable, writeable, _ = select(
                    self.connections,
                    self.connections,
                    [],
                    0.1
                )

                for conn in self.connections:
                    data = None
                    if conn == self.sock:
                        try:
                            new_client, client_addr = self.sock.accept()
                            logger.send([
                                "TCP" + str(self.server_address[1]),
                                ''.join([
                                    "Accepted connection from ",
                                    str(client_addr[0]),
                                    ":",
                                    str(client_addr[1])
                                ]),
                                10,
                                time()
                            ])
                            new_client.settimeout(3)
                            new_client.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
                            new_client.setsockopt(
                                SOL_SOCKET,
                                SO_LINGER,
                                pack('ii', 1, 0)
                            )
                            self.connections.append(new_client)
                            self.connections_mapping[new_client] = (
                                client_addr,
                                Queue()
                            )
                            self.connections_reverse[client_addr] = new_client
                            data = new_client.recv(1024)
                        except OSError:
                            pass
                        if data:
                            client_ip, client_port = client_addr
                            self.plugin_queue.put([
                                client_ip,
                                client_port,
                                data
                            ])
                        if conn in writeable:
                            try:
                                _, _, data = self.connections_mapping[conn][1].get_nowait()
                                conn.send(bytes(data))
                            except Empty:
                                pass
                    else:
                        if conn in readable:
                            data = conn.recv(1024)
                        if data:
                            client_ip, client_port = self.connections_mapping[conn][0]
                            self.plugin_queue.put([client_ip, client_port, data])
                        if conn in writeable:
                            try:
                                _, _, data = self.connections_mapping[conn][1].get_nowait()
                                conn.send(bytes(data))
                            except Empty:
                                pass
            except KeyboardInterrupt:
                continue
            except Exception as ex:
                logger.send([
                    ''.join(("TCP", str(self.server_address[1]))),
                    ''.join(["Exception ", str(ex), ", stopping..."]),
                    50,
                    time()
                ])
                self._stop()

    def _collector(self):
        """Send/receive pipe collector

        The collector runs as a thread that handles the data sending
        and receiving from the Pipe()s to the plugins.
        """
        while True:
            # Check pipe for incoming data
            if self.pipes["test"].poll(timeout=0.1):
                client_ip, client_port, data = self.pipes["test"].recv()
                self.connections_mapping[self
                                         .connections_reverse[(
                                             client_ip,
                                             client_port
                                         )]][1].put([
                                             client_ip,
                                             client_port,
                                             data
                                             ])
            try:
                client_ip, client_port, data = self.plugin_queue.get_nowait()
                self.pipes["test"].send([client_ip, client_port, data])
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
        for conn in self.connections:
            try:
                conn.close()
            except OSError:
                continue
        sysexit(0)
