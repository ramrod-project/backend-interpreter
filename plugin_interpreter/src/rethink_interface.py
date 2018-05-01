"""
The RethinkInterface is a simple interface to the RethinkDB
which runs as a Process() and handles transactions between
the interpreter and the RethinkDB database instance.

TODO:
"""

from multiprocessing import Queue
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
        self.host = server[0]
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

    def start(self, logger, signal):
        """
        Start the Rethinkdb interface process. Control loop that handles
        communication with the database.
        """
        self._database_init(logger)

        # Control loop, reads from incoming queue and sends to RethinkDB
        while True:
            try:
                if signal.value:
                    logger.send([
                        "dbprocess",
                        "Kill signal received - stopping DB process \
                        and closing connection...",
                        10,
                        time()
                    ])
                    self._stop()
                sleep(0.1)

                next_item, plugin_name = None, None
                client_ip, client_port = None, None
                response = self.response_queue.get_nowait()
                if response["type"] == "functionality":
                    plugin_name = response["name"]
                    next_item = response["data"]
                elif response["type"] == "message":
                    plugin_name = response["name"]
                    client_ip, client_port = response["client"]
                    next_item = response["data"]
                if response["type"] == "message":
                    client = self.check_client(plugin_name + "-" + client_ip)
                    if not client:
                        logger.send([
                            "dbprocess",
                            "New client "
                            + client_ip
                            + " " + str(client_port)
                            + " " + plugin_name,
                            10,
                            time()
                        ])
                        rethinkdb.db("test").table("hosts").insert([
                            {
                                "name": plugin_name + "-" + client_ip,
                                "ip": client_ip,
                                "port": client_port,
                                "plugin": plugin_name
                            }
                        ]).run(self.rethink_connection)
                        # test sending command
                        self.plugin_queue.put("test_func_1")
                    else:
                        logger.send([
                            "dbprocess",
                            "Existing client "
                            + client["name"]
                            + ", updating port to "
                            + str(client_port),
                            10,
                            time()
                        ])
                        rethinkdb.db("test").table("hosts").filter(
                            rethinkdb.row["name"] == client["name"]).update({
                                "port": client_port
                            }).run(self.rethink_connection)
                    if self.rethink_connection:
                        rethinkdb.db("test").table("messages").insert([
                            {
                                "type": "message",
                                "plugin": plugin_name,
                                "client": plugin_name + "-" + client_ip,
                                "body": str(next_item)
                            }
                        ]).run(self.rethink_connection)
                        self.plugin_queue.put("test_func_2")
                elif response["type"] == "functionality":
                    if self.rethink_connection:
                        rethinkdb.db("test").table("plugins").insert([
                            {
                                "plugin": plugin_name,
                                "functions": next_item
                            }
                        ]).run(self.rethink_connection)
                        logger.send([
                            "dbprocess",
                            "Functionality for "
                            + plugin_name
                            + " set to "
                            + str(next_item),
                            10,
                            time()
                        ])
            except Empty:
                continue
            except KeyboardInterrupt:
                continue
            except rethinkdb.ReqlError as err:
                self._log_db_error(err, logger)

    def _log_db_error(self, err, logger):
        if isinstance(err, rethinkdb.ReqlTimeoutError):
            logger.send([
                "dbprocess",
                "Database operation timeout: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlAvailabilityError):
            logger.send([
                "dbprocess",
                "Database operation failed: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlRuntimeError):
            logger.send([
                "dbprocess",
                "Database runtime error: " + str(err),
                40,
                time()
            ])
        elif isinstance(err, rethinkdb.ReqlDriverError):
            logger.send([
                "dbprocess",
                "Database driver error: " + str(err),
                50,
                time()
            ])
            self._stop()

    def _database_init(self, logger):
        try:
            self.rethink_connection = rethinkdb.connect(self.host, self.port)
            for table_name in ["messages", "plugins", "commands", "hosts"]:
                ex = self._create_table(table_name)
                if not ex:
                    logger.send([
                        "dbprocess",
                        "Table '" + table_name + "'created.",
                        10,
                        time()
                    ])
                else:
                    logger.send([
                        "dbprocess",
                        str(ex),
                        10,
                        time()
                    ])
    
            logger.send([
                "dbprocess",
                "Succesfully opened connection to Rethinkdb",
                20,
                time()
            ])
        except rethinkdb.ReqlDriverError as ex:
            logger.send(["dbprocess", str(ex), 50, time()])
            sysexit(111)

    def _create_table(self, table_name):
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
            rethinkdb.db("test").table_create(
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
