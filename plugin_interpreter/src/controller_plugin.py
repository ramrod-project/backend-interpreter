"""Plugin Template Module
TODO:
- add helper function for function advertisement
- add helper function for job request
"""

from abc import ABC, abstractmethod
from os import environ
from queue import Empty

from src import rethink_interface


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

    def __init__(self, name, functionality):
        self.db_recv = None
        self.signal = None
        self.DBI = None
        self.port = int(environ["PORT"])
        self.functionality = functionality
        """
        List of dictionaries which advertises functionality of the plugin.
        Example:
        [
            {
                "name": "read_file",
                "input": ["string"],
                "family": "filesystem",
                "tooltip": "Provided a full directory path, \
                this function reads a file.",
                "reference": "<reference url>"
            },
            {
                "name": "send_file",
                "input": ["string", "binary"],
                "family": "filesystem",
                "tooltip": "Provided a file and destination \
                directory, this function sends a file.",
                "reference": "<reference url>"
            }
        ]
        The 'name' key is the unique identifier used to refer to the
        function in communication between the front end interface and
        the back end. This exact identifier will be sent back with
        corresponding commands to let the plugin know which funcion
        should be called.

        The 'input' key is a list of required input types to properly
        call the function. Possible input types include: string,
        int, binary.

        The 'tooltip' key is a human readable explanation of the
        function usage. It will be displayed to the user through
        the interface.
        """
        self.name = name
        """Define server port/proto requirement (TCP/UDP) so docker can be run
        properly."""
        super().__init__()

    def initialize_queues(self, recv_queue):
        """Initialize command/response queues

        The 'initialize_queues' method is called by the Supervisor with
        two multiprocessing.Queue() instances with send_queue being the
        response queue owned by the RethinkInterface instanc, and
        recv_queue being a unique command queue used by the RethinkInterface
        process to communicate with the plugin process.
        #
        These queues follow a defined message format depending on the
        action which is being requested (in the case of the recv_queue),
        or the data which is being sent back (send_queue). These message
        formats are defined below above their respective methods.

        Arguments:
            send_queue {Queue} -- The queue used to send responses back to the
            database interface.
            recv_queue {Queue} -- The queue used to receive commands from the
            frontend through the database.
        """
        self.db_recv = recv_queue
        self._advertise_functionality()

    def _start(self, logger, signal):
        host = "rethinkdb"
        if environ["STAGE"] == "TESTING":
            host = "127.0.0.1"
        self.DBI = rethink_interface.RethinkInterface(self.name, (host, 28015))
        self.initialize_queues(self.DBI.plugin_queue)
        self.DBI.start(logger, signal)
        self.start(logger, signal)

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

        self.DBI.update_job(job_id)

    def _update_job_error(self, job, msg=""):
        """updates a job's status to error and outputs an error message
        to the output table. This indicates that a command has in some way
        failed to execute correctly.

        Arguments:
            job {dict} -- The job that errored
            msg {str|int|byte|float} -- (optional) The error message to display
        """

        self._respond_output(job, msg)
        self.DBI.update_job_error(job["id"])

    def _update_job_status(self, job_id, status):
        """Updates a job's status to a specified status. _update_job should be
        used in most cases.

        Arguments:
            job_id {int} -- The job id to update
            status {string} -- what the new status will be. The valid states
            are "Ready", "Pending", "Done", "Error", "Stopped", "Waiting",
            and "Active"
        """

        self.DBI._update_job_status(
            {
                "job": job_id,
                "status": status
            }
        )

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

    def _advertise_functionality(self):
        """Advertises functionality to database

        This will send the contents of the self.functionality
        attribute to the database interface. The table for
        the plugin will be named the exact same string as the
        self.name attribute.
        """
        self.DBI.create_plugin_table((self.name, self.functionality))

    def _request_job(self):
        """Request next job

        This first checks the receive queue to see if there is
        a job waiting, then if the queue is empty, it sends a
        request to the database handler to reply with the next
        new job whose start time is in the past.

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
        try:
            job = self.db_recv.get_nowait()
        except Empty:
            job = None

        if job:
            self._update_job(job["id"])
        return job

    def _end_job(self, job, output):
        """this method allows a plugin to send output to the database
        and set the status of the job to "Done"
        
        Arguments:
            job {dict} -- the dictionary object for the job received from
            the database
            output {str} -- the data to send to the database
        """
        self._respond_output(job, output)
        self._update_job_status(job["id"], "Done")

    def _respond_output(self, job, output):
        """Provide job response output

        This method is a helper method for the plugin
        which is inheriting this base class. The plugin
        must pass this function the job object it
        received from the _request_job helper function
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
        self.DBI.send_output({
            "job": job,
            "output": output
        })
        self._update_job(job["id"])

    @abstractmethod
    def _stop(self, **kwargs):
        """Stop the plugin

        This method should be used and called when the exit signal
        is sent to the program subprocesses. Pass any keyword args
        needed and execute any cleanup required.
        """
        exit(0)
