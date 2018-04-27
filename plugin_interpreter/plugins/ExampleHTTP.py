"""Example HTTP module

TODO:
- add 'functionality' attribute with adertised functions.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from queue import Empty
from threading import Thread
from time import sleep, time

from src import controller_plugin


class ExampleHTTP(controller_plugin.ControllerPlugin):
    """Example HTTP module class

    This class is an example of an interpreter plugin
    that might be used for command and control. Here,
    the template class (ControllerPlugin) is used as
    a 'mixin' class with socketserver.BaseServer, adding
    the necessary functionality to the builtin HTTP
    server offered by the standard Python libraries.


    Arguments:
        controller_plugin {class} -- This is the template
        class for interpreter plugins used by plugins
        to implement common functionality.
    """


    def __init__(self):
        self.name = "ExampleHTTP"
        self.port = 8080
        self.proto = "TCP"
        super().__init__(self.name, self.proto, self.port)

    def start(self, logger, signal):
        logger.send([
            self.name,
            self.name + " starting...",
            20,
            time()
        ])
        httpd = ExampleHTTPServer(
            ("0.0.0.0", self.port),
            self.db_recv,
            self.db_send
        )
        httpd_server = Thread(target=httpd.serve_forever, daemon=True)
        httpd_server.start()

        try:
            while not signal.value:
                sleep(0.5)
        except KeyboardInterrupt:
            self._stop(logger=logger, server=httpd)
        finally:
            exit(0)

    def _stop(self, **kwargs):
        kwargs["logger"].send([
            self.name,
            self.name + " server shutting down...",
            20,
            time()
        ])
        kwargs["server"].shutdown()
        exit(0)


class ExampleHTTPServer(HTTPServer):
    """Example HTTP server class

    This class is a supplementary one to the primary
    exported ExampleHTTP class. It simply inherits
    HTTPServer and adds a few attributes so they
    can be accessed by the server when it is
    running.

    Arguments:
        HTTPServer {class} -- builtin Python HTTPServer
        class.

    Attributes:
        db_recv {Queue} -- a Multiprocessing Queue for
        receiving commands from the database/frontend.
        db_send {Queue} -- a multiprocessing Queue for
        sending responses to the database/frontend.
    """

    def __init__(self, server_address, recv, send):
        self.db_recv = recv
        self.db_send = send
        super().__init__(
            server_address,
            ExampleHTTPRequestHandler
        )


class ExampleHTTPRequestHandler(BaseHTTPRequestHandler):
    """Example HTTP request handler

    This is an example additional class required to
    run the ExampleHTTP plugin class instance. It
    inherits from the BaseHTTPRequestHandler, which
    defines the HTTP server's response behavior to
    different HTTP methods/requests.

    Arguments:
        BaseHTTPRequestHandler {class} -- Builtin HTTP
        request handler.
    """
    def _set_headers(self):
        """Set headers for HTTP 200 response.
        """

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

    def do_GET(self):
        """GET method handler.
        """
        command = None
        try:
            command = self.server.db_recv.get_nowait()
            print(command)
        except Empty:
            pass

        server_id = " ".join([
            str(self.server.server_address[0]),
            str(self.server.server_address[1])
        ])

        self.server.db_send.put([
            server_id,
            self.client_address[0],
            self.client_address[1],
            self.requestline
        ])

        self._set_headers()

        resp = b'No command!\n'
        if command:
            if command == "test_func_1":
                resp = bytes(self._test_func_1() + "\n", "utf-8")
            elif command == "test_func_2":
                resp = bytes(self._test_func_2() + "\n", "utf-8")
            self.wfile.write(resp)
        else:
            self.wfile.write(resp)

    def do_HEAD(self):
        """HEAD method handler
        """
        self._set_headers()

    def do_POST(self):
        """POST method handler.
        """
        self._set_headers()
        data_string = self.rfile.read(int(self.headers["Content-Length"]))

        server_id = " ".join([
            str(self.server.server_address[0]),
            str(self.server.server_address[1])
        ])

        self.server.db_send.put([
            server_id,
            self.client_address[0],
            self.client_address[1],
            data_string
        ])

        self.send_response(200)
        self.end_headers()

    def _test_func_1(self):
        """A test function
        """
        return "Sending command 1..."

    def _test_func_2(self):
        """Another test function
        """
        return "Sending command 2..."
