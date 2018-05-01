try:
    from ..src import controller_plugin as cp
    from .__harness_content import content as _content
    from os import environ as _environ
except (ValueError, SystemError):  #allow this plugin to be run from commandline
    import os.path
    import sys
    _path = os.path.abspath(os.path.join(os.path.abspath(__file__), "../../"))
    sys.path.append(_path)
    from src import controller_plugin as cp
    from plugins.__harness_content import content as _content, commands as _commands
    #raise

from threading import Thread
from time import sleep, time
import json
from flask import Flask, request, stream_with_context, Response
#from flask import g, jsonify, render_template, abort

_i = 0
_G_SEND = None
_G_RECV = None

class Harness(cp.ControllerPlugin):
    functionality = _commands

    def __init__(self):
        self.name = "Harness"
        if _environ['STAGE'] == "DEV":
            self.port = 5005
        else:
            self.port = 5000
        self.proto = "TCP"
        super().__init__(self.name, self.proto, self.port, self.functionality)

    def start(self, logger, ext_signal):
        httpd = _app
        print("in the process")
        httpd_server = Thread(target=httpd.run, daemon=True)
        httpd_server.start()
        global _G_RECV
        global _G_SEND
        _G_RECV = self.db_recv
        _G_SEND = self.db_send
        try:
            while not ext_signal.value:
                sleep(0.5)
        except KeyboardInterrupt:
            self._stop(logger, httpd)
        finally:
            exit(0)

    def _stop(self, logger, httpd):
        logger.send([
            self.name,
            self.name + " server shutting down...",
            20,
            time()
        ])
        httpd.shutdown()
        exit(0)




_commands = [
    {"name": "echo",
     "argv": ["Hello World"]},
    {"name": "sleep",
     "argv": ["4000", ]},
    {"name": "list_processes",
     "argv": []},
    {"name": "list_files",
     "argv": ["%appdata%\\"]},
    {"name": "read_registry",
     "argv": ["HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
              "ProgramFilesDir"]},
    {"name": "write_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example",
              "Key1",
              "REG_SZ",
              "Ramrod testing 0x000000000000000"]},
    {"name": "read_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example",
              "Key1"]},
    {"name": "sleep",
     "argv": ["4000", ]},
    {"name": "delete_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example"]},
    #this file pulls from _harness content
    #"name":"get_file",
    #"argv":["399",
    #"C:\\Users\\bauma\\Documents\\ait\\dumb_exe.exe"]},
    {"name": "put_file",
     "argv": ["399",
              "%appdata%\\test_file-9000.exe"]},

    {"name": "sleep",
     "argv": ["10000", ]},
    {"name": "create_process",
     "argv": ["%appdata%\\test_file-9000.exe"]},
    #this file pulls from _harness content
    #"name": "get_file",
    #"argv": ["501",
    #"C:\\Users\\bauma\\Documents\\ait\\dumb_sleeper.exe"]},
    {"name": "put_file",
     "argv": ["501",
              "%appdata%\\gosleep.exe"]},

    {"name": "sleep",
     "argv": ["3000", ]},
    {"name": "create_process",
     "argv": ["%appdata%\\gosleep.exe"]},
    {"name": "sleep",
     "argv": ["30000"]},
    {"name": "terminate_process",
     "argv": ["gosleep.exe"]},
    {"name": "list_files",
     "argv": ["%appdata%"]},
    {"name": "delete_file",
     "argv": ["%appdata%\gosleep.exe"]},
    {"name": "delete_file",
     "argv": ["%appdata%\\test_file-9000.exe"]},
    {"name": "list_files",
     "argv": ["%appdata%\\"]},
    {"name": "terminate",
     "argv": []}
]

_app = Flask(__name__)
_app.config.from_object(__name__)


@_app.before_request
def _before_request():
    pass


@_app.teardown_request
def _teardown_request(exception):
    pass


@_app.route("/harness/<serial>", methods=['GET'])
def _show_command_builder(serial):
    global _i
    remote = (json.dumps(request.args))
    try:
        comman_to_apply = _commands[_i] #todo: integrate upstream
    except IndexError:
        print("sequence complete")
        return "sleep,10000"
    _i += 1
    command_string = "%s,%s" % (comman_to_apply['name'],
                                ",".join(comman_to_apply['argv']))
    print(command_string)
    return command_string


@_app.route("/response/<serial>", methods=['POST'])
def _get_capability(serial):
    print(request.form['data'])
    return "thanks"


@_app.route("/givemethat/<serial>/<file_id>", methods=['GET'])
def _get_blob(serial, file_id):
    def gens(file_id):
        file_content = _content[file_id]
        for next_byte in file_content:
            yield next_byte

    return Response(stream_with_context(gens(file_id)))


@_app.route("/givemethat/<serial>/<file_id>", methods=['POST'])
def _put_blob(serial, file_id):
    # print (id)
    # print ("Len - %s" %(len(request.form['data'])))
    _content[file_id] = request.form['data']
    return "thanks"


if __name__ == "__main__":
    from sys import argv
    from multiprocessing import Value
    from ctypes import c_bool
    if len(argv) < 2:
        _app.run(debug=True, port=5005) #5005 is the non-default Debug port
    else:
        ext_signal = Value(c_bool, False)
        test_harness = Harness()
        test_harness.start(None, ext_signal)