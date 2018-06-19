from os import environ, remove
import re
from time import asctime, gmtime, sleep, time

import docker
from pytest import fixture
from brain import r as rethinkdb

from src import controller_plugin, supervisor, rethink_interface

CLIENT = docker.from_env()
NOW = time()
SAMPLE_TARGET = {
    "id": "w93hyh-vc83j5i-v82h54u-b6eu4n",
    "PluginName": "IntegrationTest",
    "Location": "127.0.0.1",
    "Port": "8080",
    "Optional": {
        "TestVal1": "Test value",
        "TestVal2": "Test value 2"
    }
}
SAMPLE_JOB = {
    "id": "138thg-eg98198-sf98gy3-feh8h8",
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": NOW,
    "JobCommand": "Do stuff"
}

environ["PORT"] = "8080"


class IntegrationTest(controller_plugin.ControllerPlugin):
    """A class to be used for integration testing.
    
    Arguments:
        controller_plugin {class} -- the base class for plugins
    """


    def __init__(self):
        self.name = "IntegrationTest"
        self.functionality = [
            {
                "CommandName": "read_file",
                "input": ["string"],
                "family": "filesystem",
                "tooltip": "Provided a full directory path, this function reads a file.",
                "reference": "no reference"
            },
            {
                "CommandName": "send_file",
                "input": ["string", "binary"],
                "family": "filesystem",
                "tooltip": "Provided a file and destination directory, this function sends a file.",
                "reference": "no reference"
            }
        ]
        super().__init__(self.name, self.functionality)

    def start(self, logger, signal):
        """Run the integration tests

        This method is called by the supervisor, so it will contain
        all of the integration tests which need to be performed
        at runtime. Which test is performed will be selected based
        on an environment variable "TEST_SELECTION" which will be set by the
        test functions.

        Arguments:
            logger {Connection(Pipe)} -- the pipe to the logger
            signal {c_bool} -- process kill signal
        """
        if environ["TEST_SELECTION"] == "TEST1":
            """Pull a job"""
            now = time()
            while time() - now < 3:
                new_job = self._request_job()
                if new_job is not None:
                    break
                sleep(0.1)
            if not new_job == SAMPLE_JOB:
                exit(666)
        elif environ["TEST_SELECTION"] == "TEST2":
            """Send output"""
            output = "test output"
            self._respond_output(SAMPLE_JOB, output)
        elif environ["TEST_SELECTION"] == "TEST3":
            """Update job status"""
            self._update_job_status(SAMPLE_JOB["id"],"Pending")
        elif environ["TEST_SELECTION"] == "TEST4":
            """Log to logger"""
            logger.send([
                "plugin",
                "Testing out the logger.",
                50,
                NOW
            ])
        elif environ["TEST_SELECTION"] == "TEST5":
            self._update_job_error(SAMPLE_JOB, "Testing Error")

        while signal.value is not True:
            sleep(1)
        
        self._stop()

    def _stop(self, **kwargs):
        """placeholder"""
        exit(0)

@fixture(scope="module")
def rethink():
    tag = "latest"
    try:
        tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
    except KeyError:
        pass
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    sleep(3)
    yield
    try:
        environ["LOGLEVEL"] = ""
        containers = CLIENT.containers.list()
        for container in containers:
            if container.name == "rethinkdb":
                container.stop()
                break
    except SystemExit:
        pass

@fixture
def sup():
    environ["LOGLEVEL"] = "DEBUG"
    environ["STAGE"] = "TESTING"
    sup = supervisor.SupervisorController("Harness")
    sup.plugin = IntegrationTest()
    return sup

@fixture(scope="function")
def connection():
    conn = rethink_interface.RethinkInterface.connect_to_db("127.0.0.1", 28015)
    yield conn
    conn.close()

def test_pull_job(sup, rethink, connection):
    """Test pulling a job

    This test runs a supervisor, which runs a plugin
    that attempts to pull a job.
    
    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = "TEST1"
    environ["STAGE"] = "TESTING"
    rethinkdb.db("Brain").table("Jobs").insert(
        SAMPLE_JOB
    ).run(connection)
    try:
        sup.create_servers()
        sup.spawn_servers()
        sleep(5)
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"

def test_create_plugin(rethink, connection):
    """Test creating a plugin

    This test tests to see if the previous test
    created a table for the IntegrationTest plugin.

    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    tables = rethinkdb.db("Plugins").table_list().run(connection)
    assert "IntegrationTest" in tables

def test_send_output(sup, rethink, connection):
    """Test sending output from the plugin

    This test should send a mock output to the database
    from the plugin running in the supervisor.

    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = "TEST2"
    environ["STAGE"] = "TESTING"
    try:
        sup.create_servers()
        sup.spawn_servers()
        sleep(10)
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"
    cursor = rethinkdb.db("Brain").table("Outputs").run(connection)
    output = cursor.next()
    assert output["OutputJob"]["id"] == SAMPLE_JOB["id"]
    assert output["Content"] == "test output"

def test_job_status_update(sup, rethink, connection):
    """Test sending a job status update

    This test send a job status update from the plugin to the
    database.
    
    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = "TEST3"
    environ["STAGE"] = "TESTING"
    try:
        sup.create_servers()
        sup.spawn_servers()
        sleep(10)
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"

    cursor = rethinkdb.db("Brain").table("Jobs").run(connection)
    job = cursor.next()
    assert job["id"] == SAMPLE_JOB["id"]
    assert job["Status"] == "Pending"

def test_log_to_logger(sup, rethink):
    """Test logging to the logger

    This test logs to the logger from the plugin.
    
    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = "TEST4"
    environ["STAGE"] = "TESTING"
    try:
        sup.create_servers()
        sup.spawn_servers()
        sleep(5)
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"

    found_plugin_log = False
    found_rethink_log = False

    with open("logfile","r+") as file_handler:
        output = re.split(" +", file_handler.readline())
        while output:
            print(output) #confirms there are 6 other logs in the logger before the above.
            if re.match(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', output[0]):
                try:
                    assert re.split(" +", asctime(gmtime(NOW))) == output[:5]
                    assert output[5] == "central"
                    assert output[6] == "CRITICAL"
                    assert output[7].split(":")[0] == "plugin"
                    assert " ".join(output[8:]).split("\n")[0] == "Testing out the logger."
                    found_plugin_log = True
                except AssertionError:
                    pass
                try:
                    assert output[5] == "central"
                    assert output[6] == "INFO"
                    assert output[7].split(":")[0] == "dbprocess"
                    assert " ".join(output[8:]).split("\n")[0] == "Succesfully opened connection to Rethinkdb"
                    found_rethink_log = True
                except AssertionError:
                    pass
            output = None
            output = re.split(" +", file_handler.readline())
            if output[0] == "":
                break
    assert found_plugin_log 
    assert found_rethink_log

def test_database_connection(rethink):
    """Test that the interpreter check the connection

    This tests if the interpreter will check for the
    database to be available for connection.
    
    Arguments:
        rethink {none} -- allows access to the rethinkdb
    """
    environ["TEST_SELECTION"] = "TEST4"
    environ["STAGE"] = "TESTING"
    #this SHOULD be a bad port to connect to. if this test fails
    #something is very wrong
    location = ("localhost",28888)
    try:
        rethink_interface.RethinkInterface(IntegrationTest(), location)
    except SystemExit as ex:
        assert str(ex) == "111"

def test_database_connection_succeed(rethink):
    location = ("localhost", 28015)
    rti = rethink_interface.RethinkInterface(IntegrationTest(), location)
    assert isinstance(rti.rethink_connection,rethinkdb.Connection)

def test_update_error(sup, rethink, connection):
    rethinkdb.db("Brain").table("Jobs").delete().run(connection)
    rethinkdb.db("Brain").table("Outputs").delete().run(connection)
    sleep(5)
    rethinkdb.db("Brain").table("Jobs").insert(SAMPLE_JOB).run(connection)
    sleep(3)
    environ["TEST_SELECTION"] = "TEST5"
    environ["STAGE"] = "TESTING"

    try:
        sup.create_servers()
        sup.spawn_servers()
        sleep(10)
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"

    cursor = rethinkdb.db("Brain").table("Jobs").run(connection)
    job = cursor.next()
    assert job["id"] == SAMPLE_JOB["id"]
    assert job["Status"] == "Error"
    cursor = rethinkdb.db("Brain").table("Outputs").run(connection)
    output = cursor.next()
    assert output["OutputJob"]["id"] == SAMPLE_JOB["id"]
    assert output["Content"] == "Testing Error"
