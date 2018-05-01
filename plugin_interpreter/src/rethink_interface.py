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
# - have db respond with test data and client

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
        self.rethink_connection = None
        self.stream = None
        plugin.initialize_queues(self.response_queue, self.plugin_queue)

    def check_client(self, client):
        """
        Validate that a single client is present in the database and
        check what plugin it is associated with. Return the client
        information from the database
        """
        cursor = None
        cursor = rethinkdb.db("test").table("hosts").filter(
            rethinkdb.row["name"] == client
        ).run(self.rethink_connection)
        try:
            client = cursor.items[0]
            return client
        except IndexError:
            return False
        except KeyError:
            return False

    def update_job(self, job_id, status):
        pass
    
    def _get_next_job(self, plugin_name):
        """
        Adds the next job to the plugin's queue
        
        Arguments:
            plugin_name {str} -- The name of the plugin to filter jobs with
        """

        self.job_cursor = rethinkdb.table("Jobs").filter(
            rethinkdb.row["JobTarget"]["PluginName"] == plugin_name \
            and rethinkdb.row["Status"] == "Ready"
        ).run(self.rethink_connection)
        self.plugin_queue.put(self.job_cursor.next)
    
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
            return
        try:
            rethinkdb.db("Plugins").table(plugin_data[0]).insert(plugin_data[1]).run(self.rethink_connection)
        except rethinkdb.ReqlDriverError as ex:
            self.logger.send([
                "dbprocess",
                "Unable to add command to table '" + plugin_data[0] +"'",
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
                if response["type"] == "Functionality":
                    self._create_plugin_table(response["data"])
                if response["type"] == "job_request":
                    self._get_next_job(response["data"])
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
        try:
            self.rethink_connection = rethinkdb.connect(self.host, self.port)
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
                for table_name in ["Targets","Jobs"]:
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
        except rethinkdb.ReqlDriverError as ex:
            self.logger.send(["dbprocess", str(ex), 50, time()])
            sysexit(111)

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
            rethinkdb.db(database_name).table_create(
                table_name
            ).run(self.rethink_connection)
            return None
        except rethinkdb.ReqlOpFailedError as ex:
            return ex

    def _stop(self):
        try:
            self.rethink_connection.close()
        except rethinkdb.ReqlDriverError:
            pass
        sysexit(0)
