from http.server import BaseHTTPRequestHandler, HTTPServer
from os import path

from src import controller_plugin
from sys import argv


class ExampleHTTP(controller_plugin.ControllerPlugin):
    

    def __init__(self):
        self.name = "ExampleHTTP"
        self.port = 8080
        self.proto = "TCP"
        controller_plugin.ControllerPlugin.__init__(self, self.name, self.proto, self.port)

    def start(self, logger, signal):
        server_address = ("127.0.0.1", self.port)
        httpd = HTTPServer(server_address, ExampleHTTPRequestHandler)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            exit(0)

    def _stop(self):
        pass
            

class ExampleHTTPRequestHandler(BaseHTTPRequestHandler):


    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        self.wfile.write(b'Hello world!')
        return