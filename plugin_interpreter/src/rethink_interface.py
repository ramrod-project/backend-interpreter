"""
The RethinkInterface is a simple interface to the RethinkDB
which runs as a Process() and handles transactions between
the interpreter and the RethinkDB database instance.

TODO:
"""

from multiprocessing import Queue
from os import environ
from queue import Empty
from sys import exit as sysexit, stderr
from time import sleep, time

import rethinkdb


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

    def __init__(self, plugin, server):
        self.job_cursor = None
        self.host = server[0]
        self.logger = None
        # Generate dictionary of Queues for each plugin
        self.plugin_queue = Queue()
        self.port = server[1]
        # One Queue for responses from the plugin processes
        self.response_queue = Queue()
        self.rethink_connection = self._connect_to_db()
        plugin.initialize_queues(self.response_queue, self.plugin_queue)

    def _connect_to_db(self):
        now = time()
        while time() - now < 30:
            try:
                conn = rethinkdb.connect(self.host, self.port)
                return conn
            except ConnectionResetError:
                sleep(3)
            except rethinkdb.ReqlDriverError:
                sleep(3)
        stderr.write("DB connection timeout!")
        sysexit(111)

    def _update_job(self, job_data):
        """Update's the specified job's status to the given status


        Arguments:
            job_data {Dictionary} -- Dictionary containing the job id and the new status.
            (job, status)
            Interpreter should in most cases be setting "Ready" status to
            "Pending" or the "Pending" status to either "Done" or "Error"
        """

        try:
            #update the job with the given status
            rethinkdb.db("Brain").table("Jobs").get(job_data["job"]).update(
                {"Status": job_data["status"]}
            ).run(self.rethink_connection)
            #update the related output if it exists
            #attempt to get a cursor with the output
            outputref = rethinkdb.db("Brain").table("Outputs").filter(
                rethinkdb.row["OutputJob"]["id"] == job_data["job"]
            ).run(self.rethink_connection)
            #check if there was an output found
            if outputref != None:
                #update the status field in the outputs that match the job's id
                rethinkdb.db("Brain").table("Outputs").filter(
                    rethinkdb.row["OutputJob"]["id"] == job_data["job"]
                ).update({
                    "OutputJob": {
                        "Status": job_data["status"]
                    }
                }).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError:
            self._log(
                "".join(["Unable to update job '", job_data[0], "' to ", job_data[1]]),
                20
            )

    def _get_next_job(self, plugin_name):
        """
        Adds the next job to the plugin's queue

        Arguments:
            plugin_name {string} -- The name of the plugin to filter jobs with
        """

        #find jobs with the name of the plugin and are Ready to execute
        self.job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
            (rethinkdb.row["JobTarget"]["PluginName"] == plugin_name) & \
            (rethinkdb.row["Status"] == "Ready")
        ).run(self.rethink_connection)
        try:
            #add the first Ready job to the queue
            new_job = self.job_cursor.next()
            self.plugin_queue.put(new_job)
        except rethinkdb.ReqlCursorEmpty:
            #if there was no new jobs, send None
            self.plugin_queue.put(None)

    def _send_output(self, output_data):
        """sends the plugin's output message to the Outputs table

        Arguments:
            output_data {dictionary (Dictionary,str)} -- tuple containing the job
            and the output to add to the table (job, output)
        """
        #get the job corresponding to this output
        try:
            output_job = rethinkdb.db("Brain").table("Jobs").get(
                output_data["job"]["id"]
            ).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError as ex:
            self._log(
                "".join(("Could not access Jobs Table: ", str(ex))),
                30
            )
        #if the job has an entry add the output to the output table
        if output_job != None:
            #build the entry using the job as data for the output
            output_entry = {
                "OutputJob": output_job,
                "Content": output_data["output"]
            }
            try:
                #insert the entry into Outputs
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

    def _update_target(self, target_data):
        pass


    def _create_plugin_table(self, plugin_data):
        """
        Adds a new plugin to the Plugins Database

        Arguments:
            plugin_data {Tuple (str,list)} -- Tuple containing the name of the plugin and the list
            of Commands (plguin_name, command_list)
        """

        #create the table of the plugin
        self._create_table("Plugins", plugin_data[0])

        try:
            #attempt to insert the list of commands, updating any conflicts
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

    def start(self, logger, signal):
        """
        Start the Rethinkdb interface process. Control loop that handles
        communication with the database.

        Arguments:
            logger {Pipe} - Pipe to the logger
            signal {c type boolean} - used for cleanup
        """
        self.logger = logger
        self._database_init()

        # Control loop, reads from incoming queue and sends to RethinkDB
        while not signal.value:
            try:
                sleep(0.1)
                #check the plugin queue for new requests to the databse interface
                self._handle_response(self.response_queue.get_nowait())
            except Empty:
                continue
            except KeyboardInterrupt:
                continue
            except rethinkdb.ReqlError as err:
                self._log_db_error(err)
        self._stop()

    def _handle_response(self, response):
        if response["type"] == "functionality":
            self._create_plugin_table(response["data"])
        elif response["type"] == "job_request":
            self._get_next_job(response["data"])
        elif response["type"] == "job_update":
            self._update_job(response["data"])
        elif response["type"] == "job_response":
            self._send_output(response["data"])
        elif response["type"] == "target_update":
            self._update_target(response["data"])

    def _log(self, log, level):
        self.logger.send([
            "dbprocess",
            log,
            level,
            time()
        ])

    def _log_db_error(self, err):
        if isinstance(err, rethinkdb.ReqlTimeoutError):
            self._log(
                "".join(("Database operation timeout: ", str(err))),
                40
            )
        elif isinstance(err, rethinkdb.ReqlAvailabilityError):
            self._log(
                "".join(("Database operation failed: ", str(err))),
                40
            )
        elif isinstance(err, rethinkdb.ReqlRuntimeError):
            self._log(
                "".join(("Database runtime error: ", str(err))),
                40
            )
        elif isinstance(err, rethinkdb.ReqlDriverError):
            self._log(
                "".join(("Database driver error: ", str(err))),
                40
            )

    def _database_init(self):
        if environ["STAGE"] == "DEV":
            try:
                rethinkdb.db_create("Brain").run(self.rethink_connection)
            except rethinkdb.ReqlRuntimeError:
                self._log(
                    "Database 'Brain' exists",
                    20
                )
            try:
                rethinkdb.db_create("Plugins").run(self.rethink_connection)
            except rethinkdb.ReqlRuntimeError:
                self._log(
                    "Database 'Plugins' exists",
                    20
                )
            for table_name in ["Targets", "Jobs", "Outputs"]:
                self._create_table("Brain", table_name)

        self._log(
            "Succesfully opened connection to Rethinkdb",
            20
        )

    def _create_table(self, database_name, table_name):
        """Create a table in the database

        Arguments:
            logger {Pipe} -- a multiprocessing Pipe to the central
            logger.
            table_name {string} -- name of table to be created.
        """
        try:
            if database_name == "Plugins":
                rethinkdb.db(database_name).table_create(
                    table_name, primary_key='CommandName'
                ).run(self.rethink_connection)
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

    def get_table_contents(self, table_name):
        """Gets the contents of a table
        
        Arguments:
            table_name {string} -- name of the table to be cursored.
        
        Returns:
            {list} -- a list of all the documents in a given table.
        """
        try:
            cursor = rethinkdb.table(table_name).run(self.rethink_connection)
            table_contents = []
            for document in cursor:
                table_contents.extend(document)
            return table_contents
        except rethinkdb.ReqlError as err:
            self._log_db_error(err)

    def _stop(self):
        self._log(
            "Kill signal received - stopping DB process \
            and closing connection...",
            10
        )
        try:
            self.rethink_connection.close()
        except rethinkdb.ReqlDriverError:
            pass
        sysexit(0)
