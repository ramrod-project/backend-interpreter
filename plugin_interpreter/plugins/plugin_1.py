"""
Test plugin 1 - TCP
"""

from queue import Empty
from multiprocessing import Lock, Queue
from os import environ
from sys import exit as sysexit
from threading import Thread
from time import sleep, time

from src import controller_plugin

# TODO:
# - add in functionality from main superclass

class TestPlugin1(controller_plugin.ControllerPlugin):
    """
    Test plugin 1 - TCP
    """
    def __init__(self):
        super().__init__("test", "TCP", 8080)

    def start(self, conn, logger, signal):
        """
        Called to start process
        """
        self.pipe = conn
        lock = Lock()

        # Initialize transmit and receive queues for threads
        # Queue message format: (<data>)
        transmit_queue = Queue()
        receive_queue = Queue()

        # Create threads for handling reading/writing to server Pipe()
        server_receive = Thread(target=self._server_rx_thread,
                                args=(receive_queue, lock), daemon=True)
        server_transmit = Thread(target=self._server_tx_thread,
                                 args=(transmit_queue, lock), daemon=True)

        # Start the threads
        server_receive.start()
        server_transmit.start()

        logger.send([self.name, "Plugin " + self.name + " started on " + self.proto + str(self.port), 10, time()])

        while True:
            try:
                if signal.value:
                    logger.send([self.name, "Received kill signal, stopping...", 20, time()])
                    self._stop()
                # Loop until infinity while server threads are alive
                # Attempt to read from server receive queue
                try:
                    client_ip, client_port, data = receive_queue.get()
                    # print("Sending", [self.name, client_ip, client_port, data], "to db interface")
                    self.db_send.put([self.name, client_ip, client_port, data])
                except Empty:
                    sleep(0.1)
                    continue

                # Check if anything needs to be sent to server
                try:
                    # client_ip, client_port, data = self.db_recv.get_nowait()
                    data = self.db_recv.get()
                    # transmit_queue.put([client_ip, client_port, data])
                    transmit_queue.put(data)
                except Empty:
                    sleep(0.1)
                    continue
                if not server_receive.is_alive() or not server_transmit.is_alive():
                    raise RuntimeError("Server thread(s) dead!")
            except KeyboardInterrupt:
                continue
            except RuntimeError as ex:
                logger.send([self.name, str(ex), 10, time()])
                self._stop()
            except Exception as ex:
                logger.send([self.name, "Received " + str(ex) + ", stopping...", 50, time()])
                self._stop()

    def _stop(self):
        """Perform cleanup before terminate"""
        if self.pipe:
            self.pipe.close()
        sysexit(0)
