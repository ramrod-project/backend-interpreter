from os import environ
from time import sleep, time

import docker
from pytest import fixture
import rethinkdb

from src import controller_plugin, supervisor

CLIENT = docker.from_env()
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
    "StartTime": int(time()),
    "JobCommand": "Do stuff"
}

class IntegationTest(controller_plugin.ControllerPlugin):
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
            new_job = self._request_job()
            if not new_job == SAMPLE_JOB:
                exit(666)
        elif environ["TEST_SELECTION"] == "TEST2":
            """Send output"""
            pass
        elif environ["TEST_SELECTION"] == "TEST3":
            """Update job status"""
            pass
        elif environ["TEST_SELECTION"] == "TEST4":
            """Log to logger"""
            pass

        while signal.value is not True:
            sleep(1)
        
        self._stop()

    def _stop(self, **kwargs):
        """placeholder"""
        exit(0)


@fixture(scope="module")
def rethink():
    try:
        tag = environ["TRAVIS_BRANCH"]
    except KeyError:
        tag = "latest"
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    sleep(5)
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
    environ["STAGE"] = "TESTNG"
    sup = supervisor.SupervisorController("Harness")
    sup.plugin = IntegationTest()
    return sup

def test_pull_job(sup, rethink):
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
    connection = rethinkdb.connect("localhost", 28015)
    rethinkdb.db("Brain").table("Jobs").insert(
        SAMPLE_JOB
    ).run(connection)
    sup.create_servers()
    sup.spawn_servers()
    sleep(5)
    try:
        sup.teardown(0)
    except SystemExit as ex:
        assert str(ex) == "0"

def test_create_plugin(sup, rethink):
    """Test creating a plugin

    This test instantiates a supervisor and creates
    the class instances and subprocesses within. This
    should trigger the plugin to advertise its functionality
    to the rethinkdb.

    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = ""

def test_send_output(sup, rethink):
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

def test_job_status_update(sup, rethink):
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

def test_process_dependencies(rethink):
    """Test process dependencies

    This test asserts that the various dependencies
    that certain processes manage for other processes
    are available after they have successfully 'started'.
    
    Arguments:
        rethink {None} -- indicates that this test will need
        the rethinkdb to be accessable.
    """
    environ["TEST_SELECTION"] = ""

def test_database_connection(sup):
    """Test that the interpreter check the connection

    This tests if the interpreter will check for the
    database to be available for connection.
    
    Arguments:
        sup {class instance} -- a SupervisorController class
        instance.
    """
    environ["TEST_SELECTION"] = ""