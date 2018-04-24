"""Exmaple HTTP module

TODO:
- Run server in separate thread.
- Link with database interface.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from os import path
from socketserver import BaseServer
from threading import Thread
from time import sleep, time

from src import controller_plugin
from sys import argv


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

        httpd = ExampleHTTPServer(("0.0.0.0", self.port), self.db_recv, self.db_send)
        httpd_server = Thread(target=httpd.serve_forever)
        httpd_server.start()

        try:
            while not signal:
                sleep(0.5)
        except KeyboardInterrupt:
            self._stop(logger, httpd)
        finally:
            exit(0)

    def _stop(self, logger, httpd):
        logger.send([
            self.name,
            self.name + " shutting down...",
            20,
            time()
        ])
        httpd.shutdown()
        exit(0)
            

class ExampleHTTPServer(HTTPServer):


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


    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        self.wfile.write(b'Hello world!')
        return