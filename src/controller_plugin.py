"""Plugin Template Module
TODO:
- add helper function for function advertisement
- add helper function for job request
"""

from abc import ABC, abstractmethod
import json
import logging
from os import environ, path as ospath, name as osname
from signal import signal, SIGTERM
from sys import stderr
from time import asctime, gmtime, time

from brain import connect
from brain.binary import get as brain_binary_get
from brain.queries import get_next_job_by_location
from brain.queries import advertise_plugin_commands, create_plugin
from brain.queries import get_next_job, get_job_status, VALID_STATES
from brain.queries import update_job_status as brain_update_job_status
from brain.queries import write_output


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
    Port allocation is done automatically by the controller, and upon
    instantiation the plugin will be given a PORT environment variable
    where it should be running its server.
    #
    The initialize_queues method *SHOUD NOT* be overridden by the
    inheriting class, as the Supervisor will attempt to initialize
    the command queues in the exact way prescribed below. The abstract
    methods 'start' and '_stop' *MUST BE* overridden by the inheriting
    class.
    #
    'start' and must take two arguments, a multiprocesing Pipe()
    connecting the process to a central application logger, and a Value
    of boolean type, which serves as a kill signal for the process (when
    set to True).
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
        self.name = name
        self.port = int(environ["PORT"])
        self.functionality = None
        if functionality:
            self.functionality = functionality
        else:
            self._read_functionality()
        self.LOGGER.send = self.log
        signal(SIGTERM, self.sigterm_handler)
        super().__init__()

    def sigterm_handler(self, _signo, _stack_frame):
        """Handles SIGTERM signal
        """
        self._stop()
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

    def _start(self, signal):
        host = "rethinkdb"
        if environ["STAGE"] == "TESTING":
            host = "127.0.0.1"
        self.db_conn = connect(host=host)
        self._advertise_functionality()
        self.start(self.LOGGER, signal)

    @abstractmethod
    def start(self, logger, signal):
        """Start the plugin

        The 'start' method is what begins the control loop for the
        plugin (whatever it needs to do). It will be used as a target
        for the creation of a LinkedProcess by the Supervisor. The
        Supervisor will also hand it a 'logger' Pipe() object which
        the plugin can optionally use for logging to the central
        logger. Usage:

        logger.send([
            self.name,
            <string: message_body>,
            <int: 10(DEBUG)|20(INFO)|30(WARN)|40(ERR)|50(CRIT)>,
            <unix epoch: time.time()>
        ])

        This method is also passed 'signal', a boolean multiprocessing
        Value (accessed via the signal.value attribute) which is
        used as a 'kill signal' for the processes running in this
        plugin container. When set to 'True', the mprocess is expected
        to gracefullly tear itself down, or else the Supervisor will
        terminate it after a timeout period.
        """
        pass

    def _update_job(self, job_id):
        """Updates the given job's state to the next state
        Ready -> Pending, Pending -> Done

        Arguments:
            job_id {int} -- The job id to update the state of
        """
        job = None
        try:
            job = get_job_status(job_id, conn=self.db_conn)
        except ValueError as ex:
            self._log(str(ex), 20)
            return None
        if job not in VALID_STATES:
            self._log(
                "".join([job_id, " has an invalid state, setting to error"]),
                30
            )
            return self._update_job_status(job_id, "Error")

        if job == "Ready":
            return self._update_job_status(job_id, "Pending")
        elif job == "Pending":
            return self._update_job_status(job_id, "Done")
        else:
            self._log(
                "".join([
                    "Job: ",
                    job_id,
                    " attempted to advance from the invalid state: ",
                    job
                ]),
                30
            )
        return None

    def _update_job_status(self, job_id, status):
        """Update's the specified job's status to the given status


        Arguments:
            job_data {Dictionary} -- Dictionary containing the job
            id and the new status.
            job: string
            status: string
            Interpreter should in most cases be setting "Ready" status to
            "Pending" or the "Pending" status to either "Done" or "Error"
        """
        if status not in VALID_STATES:
            raise InvalidStatus("".join([
                status,
                " is not a valid state."
            ]))
        try:
            brain_update_job_status(job_id, status, conn=self.db_conn)
            return status
        except ValueError:
            self._log(
                "".join([
                    "Unable to update job '",
                    job_id,
                    "' to ",
                    status
                ]),
                20
            )
        return None

    def get_file(self, file_name, encoding=None):
        """Get the file specified from the Brain

        Arguments:
            file_name {str} -- the name of the file
            encoding {str|None} -- optional method to decode

        Returns:
            bytes|str -- the contents of the file
        """
        content = brain_binary_get(file_name, conn=self.db_conn)["Content"]
        try:
            return content.decode(encoding)
            # default None will throw a TypeError, return as bytes since
            # no decode is specified
        except TypeError:
            return content

    @staticmethod
    def get_command(job):
        """return's the job's command name

        Arguments:
            job {dict} -- the job whose command to get

        Returns:
            string -- the name of the command for that job
        """

        return job["JobCommand"]

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
    def value_of_input(job, input):
        try:
            return job["JobCommand"]["Inputs"][input]["Value"]
        except IndexError:
            return None

    @staticmethod
    def value_of_option(job, option):
        try:
            return job["JobCommand"]["OptionalInputs"][option]["Value"]
        except IndexError:
            return None

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
        job = get_next_job(self.name, False, conn=self.db_conn)

        if job:
            self._update_job(job["id"])
        return job
    
    def request_job_for_client(self, location):
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
        job = get_next_job_by_location(
            self.name,
            location,
            False,
            self.db_conn
        )
        if job:
            self._update_job(job["id"])
        return job

    def respond_output(self, job, output):
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
        """
        if not isinstance(output, (bytes, str, int, float)):
            raise TypeError
        try:
            write_output(job["id"], output, conn=self.db_conn)
            self._update_job(job["id"])
        except ValueError:
            self._log(str(ValueError), 30)

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

    def _stop(self, **kwargs):
        """Stop the plugin

        This method can be used if any teardown is needed
        before the plugin exits. It will be called automatically
        when the SIGTERM is received for tearing the container down.
        """
        exit(0)
