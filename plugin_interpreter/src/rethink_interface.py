"""
The RethinkInterface is a simple interface to the RethinkDB
which runs as a Process() and handles transactions between
the interpreter and the RethinkDB database instance.

TODO:
"""

from multiprocessing import Queue
from sys import stderr
from time import asctime, gmtime, sleep, time
import threading
import logging

from brain import connect, r as rethinkdb
from brain.brain_pb2 import Commands
from brain.checks import verify
from brain.queries import plugin_exists, create_plugin, get_next_job
from brain.binary import get as binary_get


class InvalidStatus(Exception):
    """Exception raised when job status
    is invalid.
    """
    pass


class RethinkInterface:
    """
    The RethinkInterface class serves as an intermediary between the plugin
    processes and the Rethinkdb database. It contains a dictionary of command
    queues for forwarding commands received from Rethinkdb to the appropriate
    plugin process. The response queue is used by all of the plugin processes
    to process responses and forward them to the Rethinkdb.

    It runs as a process and is instantiated by and controlled by the
    SupervisorController class.
    """
    VALID_STATES = frozenset([
        "Ready", "Pending", "Done", "Error", "Stopped", "Waiting", "Active"
    ])


    def __init__(self, name, server):
        self.host = server[0]
        self.logger = logging.getLogger("dbprocess")
        self.plugin_name = name
        self.job_fetcher = None
        self.plugin_queue = Queue()
        self.port = server[1]
        self.rethink_connection = connect(host=self.host, port=self.port)

    def changefeed_thread(self, signal):  # pragma: no cover
        """Starts a changefeed for jobs and loops

        This function is used as a target for a thread
        by the plugin interpreter to monitor for jobs
        and populate a queue when they are pushed
        from the database.

        Arguments:
            signal {Value(c_bool)} -- Thread kill signal
            (if True exit).
        """
        feed_connection = connect(host=self.host)
        feed = rethinkdb.db("Brain").table("Jobs").filter(
            (rethinkdb.row["Status"] == "Ready") &
            (rethinkdb.row["JobTarget"]["PluginName"] == self.plugin_name)
        ).changes(include_initial=True).run(feed_connection)
        while not signal.value:
            try:
                change = feed.next(wait=False)
                newval = change["new_val"]
                self.plugin_queue.put(newval)
            except rethinkdb.ReqlTimeoutError:
                sleep(0.1)
                continue
            except rethinkdb.ReqlDriverError:
                self._log("Changefeed Disconnected.", 30)
                break

    def get_job(self):
        """Requests a job from the Brain

        Returns:
            Dict|None -- returns a dictionary containing a job or none if
            no jobs are ready
        """

        return get_next_job(self.plugin_name, True, self.rethink_connection)

    def start(self, signal):  # pragma: no cover
        """
        Start the Rethinkdb interface process. Control loop that handles
        communication with the database.

        Arguments:
            logger {Pipe} - Pipe to the logger
            signal {c type boolean} - used for cleanup
        """
        if self.rethink_connection:
            self._log(
                "Succesfully opened connection to Rethinkdb",
                20
            )
        else:
            return False

        self.job_fetcher = threading.Thread(
            target=self.changefeed_thread,
            args=(signal,)
        )
        self.job_fetcher.start()
        return True


    def update_job(self, job_id):
        """advances the job's status to the next state

        Arguments:
            job_id {int} -- The job's id from the ID table
        """
        job = None
        try:
            job = rethinkdb.db("Brain").table("Jobs").get(
                job_id).pluck("Status").run(self.rethink_connection)
        except rethinkdb.ReqlNonExistenceError:
            self._log(
                "".join(["unable to find job: ", job_id]),
                20
            )
            return
        if job["Status"] not in self.VALID_STATES:
            self._log(
                "".join([job_id, " has an invalid state, setting to error"]),
                30
            )

        if job["Status"] == "Ready":
            self.update_job_status({"job": job_id, "status": "Pending"})
        elif job["Status"] == "Pending":
            self.update_job_status({"job": job_id, "status": "Done"})
        else:
            self._log(
                "".join([
                    "Job: ",
                    job_id,
                    " attempted to advance from the invalid state: ",
                    job["Status"]
                ]),
                30
            )

    def update_job_error(self, job_id):
        """sets a job's status to Error

        Arguments:
            job_id {int} -- The job's id from the ID table
        """
        self.update_job_status({"job": job_id, "status": "Error"})

    def check_for_plugin(self, plugin_name):
        """Check if a plugin exists

        Query the Plugins database to see if a plugin
        table exists already.

        Arguments:
            plugin_name {str} -- name of the plugin
            to be queried.

        Returns:
            {bool} -- True if found else False
        """
        try:
            return plugin_exists(plugin_name, self.rethink_connection)
        except ValueError:
            return False

    def update_job_status(self, job_data):
        """Update's the specified job's status to the given status


        Arguments:
            job_data {Dictionary} -- Dictionary containing the job
            id and the new status.
            job: string
            status: string
            Interpreter should in most cases be setting "Ready" status to
            "Pending" or the "Pending" status to either "Done" or "Error"
        """
        if job_data["status"] not in self.VALID_STATES:
            raise InvalidStatus("".join([
                job_data["status"],
                " is not a valid state."
            ]))
        try:
            rethinkdb.db("Brain").table("Jobs").get(
                job_data["job"]
            ).update({
                "Status": job_data["status"]
            }).run(self.rethink_connection)
            rethinkdb.db("Brain").table("Outputs").filter(
                rethinkdb.row["OutputJob"]["id"] == job_data["job"]
            ).update({
                "OutputJob": {
                    "Status": job_data["status"]
                }
            }).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError:
            self._log(
                "".join([
                    "Unable to update job '",
                    job_data["job"],
                    "' to ",
                    job_data["status"]
                ]),
                20
            )

    def send_output(self, output_data):
        """sends the plugin's output message to the Outputs table

        Arguments:
            output_data {dictionary (Dictionary,str)} -- tuple containing
            the job and the output to add to the table (job, output)
        """
        # get the job corresponding to this output
        try:
            output_job = rethinkdb.db("Brain").table("Jobs").get(
                output_data["job"]["id"]
            ).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError as ex:
            self._log(
                "".join(("Could not access Jobs Table: ", str(ex))),
                30
            )
        if output_job != None:
            output_entry = {
                "OutputJob": output_job,
                "Content": output_data["output"]
            }
            try:
                # insert the entry into Outputs
                rethinkdb.db("Brain").table("Outputs").insert(
                    output_entry,
                    conflict="replace"
                ).run(self.rethink_connection)
            except rethinkdb.ReqlDriverError as ex:
                self._log(
                    "".join(("Could not write output to database", str(ex))),
                    30
                )
        else:
            self._log(
                "".join(("There is no job with an id of ", output_data[0])),
                30
            )

    def get_file(self, file_name):
        """Gets a file from the Brain by specifying the file's name

        Arguments:
            file_name {str} -- the name of the file in the Brain

        Returns:
            dict -- a dictionary containing the Brain's entry for the file
        """

        return binary_get(file_name)

    def create_plugin_table(self, plugin_data):
        """
        Adds a new plugin to the Plugins Database

        Arguments:
            plugin_data {Tuple (str,list)} -- Tuple containing the name of
            the plugin and the list of Commands (plguin_name, command_list)
        """

        if verify(plugin_data[1], Commands()):
            self._create_table("Plugins", plugin_data[0])
            try:
                rethinkdb.db("Plugins").table(plugin_data[0]).insert(
                    plugin_data[1],
                    conflict="update"
                ).run(self.rethink_connection)
            except rethinkdb.ReqlDriverError:
                self._log(
                    "".join([
                        "Unable to add command to table '",
                        plugin_data[0],
                        "'"
                    ]),
                    20
                )

    def _log(self, log, level):
        date = asctime(gmtime(time()))
        self.logger.log(level, log, extra={'date': date})

    def _log_db_error(self, err):
        err_type = {
            "<class 'rethinkdb.errors.ReqlDriverError'>": (
                "".join(("Database driver error: ", str(err))),
                40
            ),
            "<class 'rethinkdb.errors.ReqlTimeoutError'>": (
                "".join(("Database operation timeout: ", str(err))),
                40
            ),
            "<class 'rethinkdb.errors.ReqlAvailabilityError'>": (
                "".join(("Database operation failed: ", str(err))),
                40
            ),
            "<class 'rethinkdb.errors.ReqlRuntimeError'>": (
                "".join(("Database runtime error: ", str(err))),
                40
            )
        }

        self._log(*err_type[str(type(err))])

    def _create_table(self, database_name, table_name):
        """Create a table in the database

        Arguments:
            logger {Pipe} -- a multiprocessing Pipe to the central
            logger.
            table_name {string} -- name of table to be created.
        """
        try:
            if database_name == "Plugins":
                create_plugin(table_name, self.rethink_connection)
            else:
                rethinkdb.db(database_name).table_create(
                    table_name
                ).run(self.rethink_connection)
            self._log(
                "".join(["Table '", table_name, "'created."]),
                10
            )
        except rethinkdb.ReqlOpFailedError as ex:
            self._log(
                str(ex),
                40
            )

    def get_table_contents(self, db_name, table_name):
        """Gets the contents of a table

        Arguments:
            db_name {string} -- name of the database with the table
            to be cursored.
            table_name {string} -- name of the table to be cursored.

        Returns:
            {list} -- a list of all the documents in a given table.
        """
        try:
            cursor = rethinkdb.db(db_name).table(
                table_name
            ).run(self.rethink_connection)
            table_contents = []
            for document in cursor:
                table_contents.append(document)
            return table_contents
        except rethinkdb.ReqlError as err:
            self._log_db_error(err)
