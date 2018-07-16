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
from brain.queries import advertise_plugin_commands, create_plugin
from brain.queries import get_job_status, VALID_STATES, write_output
from brain.queries import update_job_status as b_update_status
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
    """


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
            job = get_job_status(job_id, self.rethink_connection)
        except ValueError as v:
            self._log(str(v), 20)
            return
        if job not in VALID_STATES:
            self._log(
                "".join([job_id, " has an invalid state, setting to error"]),
                30
            )
            self.update_job_error(job_id)

        if job == "Ready":
            self.update_job_status(job_id, "Pending")
        elif job == "Pending":
            self.update_job_status(job_id, "Done")
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

    def update_job_error(self, job_id):
        """sets a job's status to Error

        Arguments:
            job_id {int} -- The job's id from the ID table
        """
        self.update_job_status(job_id, "Error")

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

    def update_job_status(self, job_id, status):
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
            b_update_status(job_id, status, self.rethink_connection)
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

    def send_output(self, job_id, output):
        """sends the plugin's output message to the Outputs table

        Arguments:
            job_id {str} -- the ID of the job associated with this output
            output {str} -- the output to send to the database
        """
        # get the job corresponding to this output
        try:
            write_output(job_id, output)
        except ValueError:
            self._log(str(ValueError), 30)

    def get_file(self, file_name):
        """Gets a file from the Brain by specifying the file's name

        Arguments:
            file_name {str} -- the name of the file in the Brain

        Returns:
            dict -- a dictionary containing the Brain's entry for the file
        """

        return binary_get(file_name)

    def create_plugin_table(self, plugin_name, plugin_data):
        """
        Adds a new plugin to the Plugins Database

        Arguments:
            plugin_data {Tuple (str,list)} -- Tuple containing the name of
            the plugin and the list of Commands (plguin_name, command_list)
        """

        if verify(plugin_data, Commands()):
            try:
                create_plugin(plugin_name, self.rethink_connection)
                advertise_plugin_commands(
                    plugin_name,
                    plugin_data,
                    conn=self.rethink_connection
                )
            except ValueError:
                self._log(
                    "".join([
                        "Unable to add command to table '",
                        plugin_name,
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

    def _create_table(self, database_name, table_name):  # pragma: no cover
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
