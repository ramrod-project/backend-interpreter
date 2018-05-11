"""
The RethinkInterface is a simple interface to the RethinkDB
which runs as a Process() and handles transactions between
the interpreter and the RethinkDB database instance.

TODO:
"""

from multiprocessing import Queue
from os import environ
from queue import Empty
from sys import exit as sysexit
from time import sleep, time

import rethinkdb

# TODO:
#

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
        try:
            self.rethink_connection = rethinkdb.connect(self.host, self.port)
        except rethinkdb.ReqlDriverError as ex:
            self.logger.send(["dbprocess", str(ex), 50, time()])
            sysexit(111)
        self.stream = None
        plugin.initialize_queues(self.response_queue, self.plugin_queue)
        

    def _update_job(self, job_data):
        """Update's the specified job's status to the given status

        
        Arguments:
            job_data {tuple} -- tuple containing the job id and the new status.
            Interpreter should  in most cases be setting "Ready" status to 
            "Pending" or the "Pending" status to either "Done" or "Error"
        """

        try:
            rethinkdb.db("Brain").table("Jobs").get(job_data[0]).update(
                {"Status": job_data[1]}
                ).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError:
            self.logger.send([
                "dbprocess",
                "Unable to update job '" + job_data[0] +"' to " + job_data[1],
                20,
                time()
            ])
    
    def _get_next_job(self, plugin_name):
        """
        Adds the next job to the plugin's queue
        
        Arguments:
            plugin_name {string} -- The name of the plugin to filter jobs with
        """

        self.job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
            (rethinkdb.row["JobTarget"]["PluginName"] == plugin_name) & (rethinkdb.row["Status"] == "Ready")
        ).run(self.rethink_connection)
        try:
            new_job = self.job_cursor.next()
            self.plugin_queue.put(new_job)
        except rethinkdb.ReqlCursorEmpty:
           self.plugin_queue.put(None)
    
    def _send_output(self, output_data):
        """sends the plugin's output message to the Outputs table
        
        Arguments:
            output_data {Tuple (str,str)} -- tuple containing the id of the job
            and the output to add to the table
        """
        #get the job corresponding to this output
        try:
            output_job = rethinkdb.db("Brain").table("Jobs").get(
                output_data[0]
            ).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError as ex:
            self.logger.send(["dbprocess",
                "".join(("Could not access Jobs Table: ", str(ex))),
                30,
                time()
            ])
        #if the job has an entry add the output to the output table
        if output_job != None:
            output_entry = {
                "OutputJob": output_job,
                "Content": output_data[1]
            }
            try:
                rethinkdb.db("Brain").table("Outputs").insert(
                    output_entry,
                    conflict="replace"
                ).run(self.rethink_connection)
            except rethinkdb.ReqlDriverError as ex:
                self.logger.send(["dbprocess",
                    "".join(("Could not write output to database", str(ex))),
                    30,
                    time()
                ])
        else:
            self.logger.send(["dbprocess",
                "There is no job with an id of " + output_data[0],
                30,
                time()
            ])

    def _update_target(self,target_data):
        pass

    
    def _create_plugin_table(self, plugin_data):
        """
        Adds a new plugin to the Plugins Database
        
        Arguments:
            plugin_data {Tuple} -- Tuple containing the name of the plugin and the list
            of Commands
        """

        try:
            self._create_table("Plugins",plugin_data[0])
        except rethinkdb.ReqlOpFailedError:
            self.logger.send([
                "dbprocess",
                "Table '" + plugin_data[0] + "' exists",
                20,
                time()
            ])

        try:
            #attempt to insert the list of commands, updating any conflicts
            rethinkdb.db("Plugins").table(plugin_data[0]).insert(plugin_data[1],
            conflict="update").run(self.rethink_connection)
        except rethinkdb.ReqlDriverError:
            self.logger.send([
                "dbprocess",
                "Unable to add command to table '" + plugin_data[0] + "'",
                20,
                time()
            ])

    def start(self, logger, signal):
        """
        Start the Rethinkdb interface process. Control loop that handles
        communication with the database.
        """
        self.logger = logger
        self._database_init()

        # Control loop, reads from incoming queue and sends to RethinkDB
        while True:
            try:
                if signal.value:
                    self.logger.send([
                        "dbprocess",
                        "Kill signal received - stopping DB process \
                        and closing connection...",
                        10,
                        time()
                    ])
                    self._stop()
                sleep(0.1)

                response = self.response_queue.get_nowait()
                if response["type"] == "functionality":
                    self._create_plugin_table(response["data"])
                if response["type"] == "job_request":
                    self._get_next_job(response["data"])
                if response["type"] == "job_update":
                    self._update_job(response["data"])
                if response["type"] == "job_response":
                    self._send_output(response["data"])
                if response["type"] == "target_update":
                    self._update_target(response["data"])
            except Empty:
                continue
            except KeyboardInterrupt:
                continue
            except rethinkdb.ReqlError as err:
                self._log_db_error(err)

    def _log_db_error(self, err):
        if isinstance(err, rethinkdb.ReqlTimeoutError):
            self.logger.send([
                "dbprocess",
                "Database operation timeout: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlAvailabilityError):
            self.logger.send([
                "dbprocess",
                "Database operation failed: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlRuntimeError):
            self.logger.send([
                "dbprocess",
                "Database runtime error: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlDriverError):
            self.logger.send([
                "dbprocess",
                "Database driver error: " + str(err),
                50,
                time()
            ])
            self._stop()

    def _database_init(self):
        if environ["STAGE"] == "DEV":
            try:
                rethinkdb.db_create("Brain").run(self.rethink_connection)
            except rethinkdb.ReqlRuntimeError:
                self.logger.send([
                    "dbprocess",
                    "Database 'Brain' exists",
                    20,
                    time()
                ])
            try:
                rethinkdb.db_create("Plugins").run(self.rethink_connection)
            except rethinkdb.ReqlRuntimeError:
                self.logger.send([
                    "dbprocess",
                    "Database 'Plugins' exists",
                    20,
                    time()
                ])
            for table_name in ["Targets", "Jobs", "Outputs"]:
                ex = self._create_table("Brain", table_name)
                if not ex:
                    self.logger.send([
                        "dbprocess",
                        "Table '" + table_name + "'created.",
                        10,
                        time()
                    ])
                else:
                    self.logger.send([
                        "dbprocess",
                        str(ex),
                        40,
                        time()
                    ])

        self.logger.send([
            "dbprocess",
            "Succesfully opened connection to Rethinkdb",
            20,
            time()
        ])

    def _create_table(self, database_name, table_name):
        """Create a table in the database
        
        Arguments:
            logger {Pipe} -- a multiprocessing Pipe to the central
            logger.
            table_name {string} -- name of table to be created.
        
        Returns:
            {Exception} -- returns an exception if the table already
            exists.
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
            return None
        except rethinkdb.ReqlOpFailedError as ex:
            return ex
    
    def get_table_contents(self, table_name):
        cursor = rethinkdb.table(table_name).run(self.rethink_connection)
        command_list = []
        for document in cursor:
            command_list.extend(document)
        return command_list

    def _stop(self):
        try:
            self.rethink_connection.close()
        except rethinkdb.ReqlDriverError:
            pass
        sysexit(0)
