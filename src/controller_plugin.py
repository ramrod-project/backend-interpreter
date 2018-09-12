"""Plugin Template Module
"""
from abc import ABC, abstractmethod
import json
import logging
from os import environ, path as ospath
from signal import signal, SIGTERM
from time import asctime, gmtime, time

from brain import connect
from brain.binary import get as brain_binary_get
from brain.jobs import transition_success
from brain.queries import advertise_plugin_commands, create_plugin
from brain.queries import get_next_job, get_job_status
from brain.queries import update_job_status as brain_update_job_status
from brain.queries import write_output
from brain.connection import BrainNotReady
from brain.controller.plugins import recover_state, record_state
from brain.telemetry import update_telemetry, get_target_id


class InvalidStatus(Exception):
    """Exception raised when job status
    is invalid.
    """
    pass


class ControllerPlugin(ABC):
    """
    The ControllerPlugin class is an Abstract Base Class from which plugin
    subclasses can be derived. Plugins should inherit this base class and
    implement any subset of its methods that is required.
    #
    For proper instantiation, plugin subclasses should be initialized
    with a 'name' string, and 'functionality' dictionary which describes
    the functions available in the plugin.
    #
    Example functionality:
    [
        {
            "CommandName":"get_file",
            "Tooltip":"tooltip that shows up next to input on UI",
            "Output":True,
            "Inputs":[
                {"Name":"FilePath",
                "Type":"textbox",
                "Tooltip":"Must be the fully qualified path",
                "Value":"remote filename"
                },
            ],
            "OptionalInputs":[]
        },
        {
            "CommandName":"delete_file",
            "Tooltip":"tooltip that shows up on UI",
            "Output":True,
            "Inputs":[
                {"Name":"FilePath",
                "Type":"textbox",
                "Tooltip":"Must be the fully qualified path",
                "Value":"remote filename"
                },
            ],
            "OptionalInputs":[]
        },
        {
            "CommandName":"put_file",
            "Tooltip":"tooltip that shows up on UI",
            "Output":True,
            "Inputs":[
                {"Name":"SourceFilePath",
                "Type":"textbox",
                "Tooltip":"Must be uploaded here first",
                "Value":"File"
                },
                {"Name":"DestinationFilePath",
                "Type":"textbox",
                "Tooltip":"Must be the fully qualified path",
                "Value":"remote filename"
                },
            ],
            "OptionalInputs":[]
        },
    ]
    #
    Port allocation is done automatically by the controller, and upon
    instantiation the plugin will be given a PORT environment variable
    where it should be running its server.
    #
    The abstract methods '_start' and '_stop' *MUST BE* overridden by
    the inheriting class. _start is not passed any arguments by default,
    but has been written for the possibility in the future. _stop will be
    called when SIGTERM is raised by the OS (container is told to stop).
    #
    The remainder of the module can contain whatever classes
    and methods are needed for the functionality of the plugin,
    the template onl requires a specified format for the above
    exported plugin controller class.
    """
    # Initialize logger
    logging.basicConfig(
        filename="plugin_logfile",
        filemode="a",
        format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
    )

    LOGGER = logging.getLogger('plugin')
    LOGGER.addHandler(logging.StreamHandler())
    LOGLEVEL = environ.get("LOGLEVEL", default="DEBUG")
    LOGGER.setLevel(LOGLEVEL)

    def __init__(self, name, functionality=None):
        self.signal = None
        self.db_conn = None
        self.tracked_jobs = {}
        self.name = name
        self.port = int(environ["PORT"])
        self.serv_name = environ.get("PLUGIN_NAME", self.name + str(self.port))
        self.functionality = None
        if functionality:
            self.functionality = functionality
        else:
            self._read_functionality()
        self.stop_args = {}
        self.LOGGER.send = self.log
        signal(SIGTERM, self.sigterm_handler)
        super().__init__()

    def sigterm_handler(self, _signo, _stack_frame):
        """Handles SIGTERM signal
        """
        self.stop()
        exit(0)

    def log(self, log):
        """The log function is called by the
        class instance to send a collection of storted
        logs to the main logger. Iterate over list
        of [<component>, <log>, <severity>, <timestamp>]
        """
        date = asctime(gmtime(log[3]))
        self.LOGGER.log(
            log[2],
            log[1],
            extra={'date': date}
        )

    def _log(self, log, level):
        """Formats log
        """
        self.log([
            "",
            log,
            level,
            time()
        ])

    def _read_functionality(self):
        curr_dir = ospath.dirname(ospath.dirname(__file__))
        filename = "{}/plugins/__{name}/{name}.json".format(
            curr_dir,
            name=self.name
        )
        try:
            with open(filename) as config_file:
                self.functionality = json.load(config_file)
        except (IOError, json.JSONDecodeError):
            self.functionality = [{
                "CommandName": "Functionality Error",
                "Tooltip": "There was an error loading plugin functionality",
                "Output": False,
                "Inputs": [],
                "OptionalInputs": []
            }]

    def start(self, *args):
        """The entrypoint for the docker container
        """
        host = environ.get("RETHINK_HOST", "rethinkdb")
        if environ["STAGE"] == "TESTING":
            host = "127.0.0.1"
        try:
            self.db_conn = connect(host=host)
        except BrainNotReady:
            self._log("Brain is not ready.", 50)
            exit(1)
        self._advertise_functionality()
        self._start(args)

    @abstractmethod
    def _start(self, *args):
        """Start the plugin

        The 'start' method is what begins the control loop for the
        plugin (whatever it needs to do). It will be used as a target
        for the container entrypoint. The process is not handed any
        arguments by default.
        """
        pass

    def _update_job(self, job_id):
        """Updates the given job's state to the next state
        Ready -> Pending, Pending -> Done

        Arguments:
            job_id {str} -- The job id to update the state of
        """
        job_status = None
        job_status = get_job_status(job_id, conn=self.db_conn)
        return self._update_job_status(job_id, transition_success(job_status))

    def _update_job_status(self, job_id, status):
        """Update's the specified job's status to the given status

        Arguments:
            job_id {str}: id of job to be transitioned.
            status {str}: status to set job to.
            Interpreter should in most cases be setting "Ready" status to
            "Pending" or the "Pending" status to either "Done" or "Error"
        """
        try:
            brain_update_job_status(job_id, status, conn=self.db_conn)
        except ValueError as ex:
            self._log("{} not a valid status!".format(status), 50)
            raise ex
        return status

    def get_file(self, file_name, encoding=None):
        """Get the file specified from the Brain

        Arguments:
            file_name {str} -- the name of the file
            encoding {str|None} -- optional method to decode

        Returns:
            bytes|str -- the contents of the file
        """
        content = brain_binary_get(file_name, conn=self.db_conn)["Content"]
        if isinstance(content, bytes) and encoding:
            return content.decode(encoding)
        return content

    def recover(self):
        state = recover_state(self.serv_name, self.db_conn)
        if state is not None:
            self.tracked_jobs = state

    def record_tracker(self):
        record_state(self.serv_name, self.tracked_jobs, self.db_conn)

    

    @staticmethod
    def get_command(job):
        """return's the job's command name

        Arguments:
            job {dict} -- the job whose command to get

        Returns:
            string -- the name of the command for that job
        """

        return job["JobCommand"]["CommandName"]

    @staticmethod
    def get_job_id(job):
        """returns the id of the job

        Arguments:
            job {dict} -- the job which id to go

        Returns:
            string -- the id of the job
        """

        return job["id"]

    @staticmethod
    def get_status(job):
        """returns a job's status

        Arguments:
            job {dict} -- A dict in the format of a job

        Returns:
            str -- the job's current status
        """

        return job["Status"]

    @staticmethod
    def value_of(job, command_input):
        """returns the value of a commaand input name

        Arguments:
            job {dict} -- A dict in the format of a job
            command_input {str} -- the name of an input or optional input

        Returns:
            str -- The value of the first input or optional input with the
            given name. If there is an input or an optional input with the
            same name, the input's value will be returned. None if no inputs
            found.
        """

        if isinstance(command_input, str):
            value = ControllerPlugin.value_of_input(job, command_input)
            if value is None:
                value = ControllerPlugin.value_of_option(job, command_input)
            return value
        else:
            return None

    @staticmethod
    def value_of_input(job, option):
        """Get the value of an input by index or name

        Arguments:
            job {dict} -- A dict in the format of a job
            option {int|str} -- The index of an input or the name of an input.

        Returns:
            str|None -- The value of the given input. None if no input found.
        """

        return ControllerPlugin._srch_4_val(
            job["JobCommand"]["Inputs"],
            option
        )

    @staticmethod
    def value_of_option(job, option):
        """Get the value of an optional input by index or name

        Arguments:
            job {dict} -- A dict in the format of a job
            input {int|str} -- The index of an input or the name of an input.

        Returns:
            str|None -- The value of the given input. None if no input found.
        """

        return ControllerPlugin._srch_4_val(
            job["JobCommand"]["OptionalInputs"],
            option
        )

    @staticmethod
    def _srch_4_val(val_list, search):
        try:
            return val_list[search]["Value"]
        except IndexError:
            return None
        except TypeError:
            for i in val_list:
                if i["Name"] == search:
                    return i["Value"]
        return None

    @staticmethod
    def get_args(job):
        """Get a tuple containing a list of all input values and a list of all
        optional input values.

        Arguments:
            job {dict} -- A dict in the format of a job

        Returns:
            list, list -- Two lists each containing the values of the command's
            input list and optional input list.
        """

        inputs = ControllerPlugin._get_value_list(job["JobCommand"]["Inputs"])
        optional = ControllerPlugin._get_value_list(
            job["JobCommand"]["OptionalInputs"]
        )
        return (inputs, optional)

    @staticmethod
    def _get_value_list(inputs):
        val_list = []
        for i in inputs:
            val_list.append(i["Value"])
        return val_list

    @staticmethod
    def job_location(job):
        """Get the target location of a job

        Arguments:
            job {dict} -- A dict in the format of a job

        Returns:
            str -- The target's location. typically an IP address
        """

        return job["JobTarget"]["Location"]

    @staticmethod
    def job_port(job):
        """Get the target's port on which the plugin is cummunicating

        Arguments:
            job {dict} -- A dict in the format of a job

        Returns:
            str -- The port the plugin is communicating on.
        """

        return job["JobTarget"]["Port"]

    @staticmethod
    def has_output(job):
        """Returns whether a job can send output back to the database.

        Arguments:
            job {dict} -- A dict in the format of a job

        Returns:
            Bool -- True if the job should respond with output, false
            otherwise.
        """

        return job["JobCommand"]["Output"]

    def _advertise_functionality(self):
        """Advertises functionality to database

        This will send the contents of the self.functionality
        attribute to the database interface. The table for
        the plugin will be named the exact same string as the
        self.name attribute.
        """
        try:
            create_plugin(self.name, conn=self.db_conn)
            advertise_plugin_commands(
                self.name,
                self.functionality,
                conn=self.db_conn
            )
        except ValueError:
            self._log(
                "".join([
                    "Unable to add command to table '",
                    self.name,
                    "'"
                ]),
                50
            )
            raise ValueError

    def request_job(self):
        """Request next job

        This first checks the receive queue to see if there is
        a job waiting, then if the queue is empty, it sends a
        request to the database handler to reply with the next
        new job whose start time is in the past. If a job is
        found that job's status is updated to Pending

        Returns:
            {dict} -- a dictionary describing the job containing
            {
                "id": {string} -- GUID, not needed for plugin,
                "JobTarget": {dict} -- target from Targets table,
                "Status": {string} -- the status of the job,
                "StartTime": {int} -- unix epoch start time,
                "JobCommand": {dict} -- command to run
            }
        """
        job = get_next_job(self.name, verify_job=False, conn=self.db_conn)
        if job:
            self._update_job(job["id"])
            job["Status"] = transition_success(job["Status"])
        return job

    def request_job_for_client(self, location, port=None):
        """Attempts to get a job with the same plugin name at the specified
        location (typically an IP). Use this for communicating for multiple
        plugins

        Arguments:
            location {str} -- The location (usually the IP) of the plugin's
            client the get a job for.

        Returns:
            dict|None -- a job with the given location as its target or None
            {
                "id": {string} -- GUID, not needed for plugin,
                "JobTarget": {dict} -- target from Targets table,
                "Status": {string} -- the status of the job,
                "StartTime": {int} -- unix epoch start time,
                "JobCommand": {dict} -- command to run
            }
        """
        job = get_next_job(
            self.name,
            location=location,
            port=port,
            verify_job=False,
            conn=self.db_conn
        )
        if job:
            self._update_job(job["id"])
            job["Status"] = transition_success(job["Status"])
        return job

    def respond_output(self, job, output, transition_state=True):
        """Provide job response output

        This method is a helper method for the plugin
        which is inheriting this base class. The plugin
        must pass this function the job object it
        received from the request_job helper function
        and the corresponding output from the
        command.

        This method also performs some basic type
        checking on the output.

        Arguments:
            job {dict} -- the dictionary object for
            the job received from the database/frontend.
            output {str} -- The data to send to the database
            transition_state {bool} -- If True, transition to
            "Done" (no more output).
        """
        if isinstance(output, bytes):
            write_output(job["id"], output, conn=self.db_conn)
        elif isinstance(output, (str, int, float)):
            string_output = str(output)
            write_output(job["id"], string_output, conn=self.db_conn)
        else:
            self._log(
                "Invalid output type! (<str>, <int>, <float>, <bytes>",
                50)
            raise TypeError
        if transition_state:
            job["Status"] = transition_success(job["Status"])
            self._update_job(job["id"])

    def respond_error(self, job, msg=""):
        """updates a job's status to error and outputs an error message
        to the output table. This indicates that a command has in some way
        failed to execute correctly.

        Arguments:
            job {dict} -- The job that errored
            msg {str|int|byte|float} -- (optional) The error message to display
        """
        self.respond_output(job, msg)
        self._update_job_status(job["id"], "Error")

    def _validate_common_telemetry(self, common):
        """validates common telemetry data
        
        Arguments:
            common {dict} -- common telemetry
            data dict
        
        Raises:
            TypeError -- common is not dict
        
        Returns:
            {dict} -- the validated common dict
        """
        if common and not isinstance(common, dict):
            self._log(
                "Invalid common telemetry type! expects <dict>",
                50
            )
            raise TypeError
        elif common:
            common["Checkin"] = time()
        else:
            common = {"Checkin": time()}
        return common

    def send_telemetry(self, location, common=None, specific=None):
        """send_telemetry sends an update to the Brain.Telemetry table
        with both common and specific data (data)
        
        Arguments:
            location {str} -- IPv4 address of the target
        
        Keyword Arguments:
            common {dict} -- data common among all plugins
            (default: {None})
            specific {dict} -- arbitrary, specific data to store with the
            telemetry for the target (default: {None})
        """
        try:
            target_id = get_target_id(
                self.name,
                str(self.port),
                location,
                conn=self.db_conn
            )
        except AttributeError as ex:
            self._log("Target id not found: {}".format(ex), 40)
            return

        common = self._validate_common_telemetry(common)

        if specific and not isinstance(specific, dict):
            self._log(
                "Invalid specific telemetry type! expects <dict>",
                50
            )
            raise TypeError

        update_telemetry(
            conn=self.db_conn,
            target_id=target_id,
            common=common,
            specific=specific,
            verify_telemetry=True
        )

    def stop(self):
        """Stop the plugin

        This method will be called upon SIGTERM , when the container is told to
        stop. It will then call the _stop function which can
        be overridden to perform teardown (Optional).
        """
        self._stop()

    def _stop(self):
        """Default teardown funtion.

        Can be overridden to perform any necessary teardown if needed.
        """
        exit(0)
