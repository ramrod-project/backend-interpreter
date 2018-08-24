"""Unit testing for the controller_plugin module.
"""
from json import dump, load
from os import environ, makedirs, remove, removedirs
from time import time, sleep
from copy import deepcopy

import brain
import docker
from pytest import fixture, raises

from src import controller_plugin


CLIENT = docker.from_env()


SAMPLE_TARGET = {
    "id": "w93hyh-vc83j5i-v82h54u-b6eu4n",
    "PluginName": "SamplePlugin",
    "Location": "127.0.0.1",
    "Port": "8080",
    "Optional": {
        "TestVal1": "Test value",
        "TestVal2": "Test value 2"
    }
}

NOW = int(time())

SAMPLE_JOB = {
    "id": "138thg-eg98198-sf98gy3-feh8h8",
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": NOW,
    "JobCommand":  {
        "CommandName": "TestCommand",
        "Tooltip": " testing command",
        "Output": True,
        "Inputs": [
            {
                "Name": "testinput",
                "Type": "textbox",
                "Tooltip": "fortesting",
                "Value": "Test Input 1"
            }
        ],
        "OptionalInputs": []
    }
}

SAMPLE_JOB_PENDING = {
    "id": "138thg-eg98198-sf98gy3-feh8h8",
    "JobTarget": SAMPLE_TARGET,
    "Status": "Pending",
    "StartTime": NOW,
    "JobCommand":  {
        "CommandName": "TestCommand",
        "Tooltip": " testing command",
        "Output": True,
        "Inputs": [
            {
                "Name": "testinput",
                "Type": "textbox",
                "Tooltip": "fortesting",
                "Value": "Test Input 1"
            }
        ],
        "OptionalInputs": []
    }
}

SAMPLE_FILE = {
    "id": "testfile.txt",
    "Name": "testfile.txt",
    "ContentType": "data",
    "Timestamp": 123456789,
    "Content": "This is just a TEST!"
}

SAMPLE_FILE_BYTES = {
    "id": "testfile2.txt",
    "Name": "testfile2.txt",
    "ContentType": "data",
    "Timestamp": 123456789,
    "Content": b'This is just a TEST!'
}

SAMPLE_FUNCTIONALITY = [
    {
        "CommandName": "read_file",
        "Tooltip": "Provided a full directory path, this function reads a file.",
        "Output": False,
        "Inputs": [],
        "OptionalInputs": []
    },
    {
        "CommandName": "send_file",
        "Tooltip": "Provided a file and destination directory, this function sends a file.",
        "Output": False,
        "Inputs": [],
        "OptionalInputs": []
    }
]

environ["PORT"] = "8080"


class SamplePlugin(controller_plugin.ControllerPlugin):
    """Sample plugin for testing

    Sample plugin inheriting from ControllerPlugin base
    class. All it does is initialize an instance of
    itself with some basic parameters, since the
    ControllerPlugin Abstract Base Class cannot be
    directly instanced.

    Arguments:
        controller_plugin {class} -- The base class
        for plugins, which is the subject of testing.
    """


    def __init__(self, functionality):
        self.db_conn = brain.connect()
        super().__init__(
            "SamplePlugin",
            functionality=functionality
        )

    def _start(self):
        """abstractmethod overload"""
        pass

@fixture(scope="function")
def conn():
    yield brain.connect()

@fixture(scope="module")
def give_brain():
    # Setup for all module tests
    tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
    old_stage = environ.get("STAGE", "")
    environ["STAGE"] = "TESTING"
    rdb = CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb_rethink",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    yield
    # Teardown for all module tests
    environ["STAGE"] = old_stage
    rdb.stop(timeout=5)

@fixture(scope="function")
def clear_dbs():
    yield
    sleep(1)
    conn = brain.connect()
    brain.r.db("Brain").table("Targets").delete().run(conn)
    brain.r.db("Brain").table("Outputs").delete().run(conn)
    brain.r.db("Brain").table("Jobs").delete().run(conn)
    brain.r.db("Audit").table("Jobs").delete().run(conn)
    for table in brain.r.db("Plugins").table_list().run(conn):
        if "test_table" in table:
            continue
        brain.r.db("Plugins").table(table).delete().run(conn)
    sleep(1)

@fixture(scope="function")
def plugin_base():
    """Generates SamplePlugin instance

    This fixture instances a SamplePlugin
    for use in testing.
    """
    plugin = SamplePlugin({})
    yield plugin

def test_brain_not_ready():
    plugin = SamplePlugin(SAMPLE_FUNCTIONALITY)
    with raises(SystemExit):
        plugin.start()


def test_instantiate(give_brain):
    """Test plugin instancing

    Instantiates the SamplePlugin and attempts
    to populate its queue attributes.
    """
    
    with raises(TypeError):
        plugin = controller_plugin.ControllerPlugin()
    plugin = SamplePlugin(SAMPLE_FUNCTIONALITY)
    assert isinstance(plugin, controller_plugin.ControllerPlugin)

def test_job_helpers():
    assert controller_plugin.ControllerPlugin.get_command(SAMPLE_JOB) == SAMPLE_JOB["JobCommand"]["CommandName"]
    assert controller_plugin.ControllerPlugin.get_job_id(SAMPLE_JOB) == SAMPLE_JOB["id"]

def test_read_functionality(give_brain, clear_dbs):
    makedirs("plugins/__SamplePlugin")
    with open("plugins/__SamplePlugin/SamplePlugin.json", "w") as openfile:
        dump(SAMPLE_FUNCTIONALITY, openfile)
    plugin = SamplePlugin(None)
    for func in SAMPLE_FUNCTIONALITY:
        assert func in plugin.functionality
    remove("plugins/__SamplePlugin/SamplePlugin.json")
    removedirs("plugins/__SamplePlugin")

def test_advertise(plugin_base, give_brain, clear_dbs, conn):
    """Test functionality advertisement

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    plugin_base.functionality = SAMPLE_FUNCTIONALITY
    plugin_base.db_conn = conn
    plugin_base._advertise_functionality()
    db_updated = False
    result = None
    now = time()
    while time() - now < 3:
        sleep(0.3)
        result = brain.queries.get_plugin_commands(
            plugin_base.name,
            conn=plugin_base.db_conn
        )
        try:
            c1 = result.__next__()
            print(c1)
            c2 = result.__next__()
            print(c2)
            assert c1 in SAMPLE_FUNCTIONALITY and c2 in SAMPLE_FUNCTIONALITY
            db_updated = True
            break
        except:
            continue
    assert db_updated

def test_request_job(plugin_base, give_brain, clear_dbs, conn):
    """Test requesting a job

    Start a dummy_interface thread to send
    the response, then request a job.

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    plugin_base.db_conn = conn
    assert plugin_base.request_job() is None
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB).run(conn)
    now = time()
    while time() - now < 3:
        result = plugin_base.request_job()
        if result is not None:
            break
        sleep(0.3)
    assert result == SAMPLE_JOB_PENDING
    brain.r.db("Brain").table("Jobs").get(SAMPLE_JOB["id"]).update({"Status": "Ready"}).run(conn)
    sleep(2)
    result = plugin_base.request_job_for_client("127.0.0.1")
    assert result == SAMPLE_JOB_PENDING
    brain.r.db("Brain").table("Jobs").get(SAMPLE_JOB["id"]).update({"Status": "Ready"}).run(conn)
    sleep(2)
    result = plugin_base.request_job_for_client("127.0.0.1", "8080")
    assert result == SAMPLE_JOB_PENDING
    

def test_update_job(plugin_base, give_brain, clear_dbs, conn):
    plugin_base.db_conn = conn
    with raises(ValueError):
        plugin_base._update_job("doesntexist")
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB).run(conn)
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None:
            break
        sleep(0.3)
    assert result == SAMPLE_JOB
    assert plugin_base._update_job(SAMPLE_JOB["id"]) == "Pending"
    db_updated1 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Pending":
            db_updated1 = True
        sleep(0.3)
    assert db_updated1
    assert plugin_base._update_job(SAMPLE_JOB["id"]) == "Done"
    db_updated2 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Done":
            db_updated2 = True
        sleep(0.3)
    assert db_updated2
    assert plugin_base._update_job(SAMPLE_JOB["id"]) == "Done"
    db_not_updated = True
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] != "Done":
            db_not_updated = False
            break
        sleep(0.3)
    assert db_not_updated

def test_update_job_status(plugin_base, give_brain, clear_dbs, conn):
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB).run(conn)
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None:
            break
        sleep(0.3)
    assert result == SAMPLE_JOB
    assert plugin_base._update_job_status(SAMPLE_JOB["id"], "Done") == "Done"
    
    db_updated1 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Done":
            db_updated1 = True
        sleep(0.3)
    assert db_updated1

    assert plugin_base._update_job_status(SAMPLE_JOB["id"], "Error") == "Error"
    db_updated2 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Error":
            db_updated2 = True
        sleep(0.3)
    assert db_updated2

def test_respond_to_job(plugin_base, give_brain, clear_dbs, conn):
    """Test sending job response

    Tests the various types of allowed response
    data types.

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB_PENDING).run(conn)
    with raises(TypeError):
        plugin_base.respond_output(SAMPLE_JOB_PENDING, None)
    with raises(TypeError):
        plugin_base.respond_output(SAMPLE_JOB_PENDING, {})

    plugin_base.respond_output(SAMPLE_JOB_PENDING, "Sample Job Response")
    db_updated1 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB_PENDING["id"], conn=conn)
        if result is not None and result == "Sample Job Response":
            db_updated1 = True
        sleep(0.3)
    print(result)
    assert db_updated1

def test_respond_to_job_bytes(plugin_base, give_brain, clear_dbs, conn):
    """Test sending job response (bytes)
    """
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB_PENDING).run(conn)
    plugin_base.respond_output(SAMPLE_JOB_PENDING, bytes("Sample Job Response", "utf-8"))
    db_updated2 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB_PENDING["id"], conn=conn)
        if result is not None and result == bytes("Sample Job Response", "utf-8"):
            db_updated2 = True
        sleep(0.3)
    assert db_updated2


def test_respond_to_job_int(plugin_base, give_brain, clear_dbs, conn):
    """Test sending job response (int)
    """
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB_PENDING).run(conn)
    plugin_base.respond_output(SAMPLE_JOB_PENDING, 666)
    db_updated3 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB_PENDING["id"], conn=conn)
        if result is not None and int(result) == 666:
            db_updated3 = True
        sleep(0.3)
    assert db_updated3

def test_respond_to_job_float(plugin_base, give_brain, clear_dbs, conn):
    """Test sending job response (float)
    """
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB_PENDING).run(conn)
    plugin_base.respond_output(SAMPLE_JOB_PENDING, 42.42)
    db_updated4 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB_PENDING["id"], conn=conn)
        if result is not None and float(result) == 42.42:
            db_updated4 = True
        sleep(0.3)
    assert db_updated4

def test_respond_to_job_error(plugin_base, give_brain, clear_dbs, conn):
    """Test sending job response (error)
    """
    plugin_base.db_conn = conn
    brain.r.db("Brain").table("Jobs").insert(SAMPLE_JOB_PENDING).run(conn)
    plugin_base.respond_error(SAMPLE_JOB_PENDING, "error")
    db_updated5 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB_PENDING["id"], conn=conn)
        if result is not None and result == "error":
            db_updated5 = True
        sleep(0.3)
    assert db_updated5
    # Verify error status
    db_updated6 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Error":
            db_updated6 = True
        sleep(0.3)
    assert db_updated6

def test_get_file(plugin_base, give_brain, clear_dbs, conn):
    plugin_base.db_conn = conn
    brain.binary.put(SAMPLE_FILE, conn=conn)
    db_updated1 = False
    now = time()
    while time() - now < 3:
        result = brain.binary.get(SAMPLE_FILE["Name"], conn=conn)
        if result is not None:
            db_updated1 = True
        sleep(0.3)
    print(result)
    assert db_updated1
    # check without encoding to get bytes blob
    assert plugin_base.get_file("testfile.txt") == SAMPLE_FILE["Content"]
    brain.binary.put(SAMPLE_FILE_BYTES, conn=conn)
    db_updated2 = False
    now = time()
    while time() - now < 3:
        result = brain.binary.get(SAMPLE_FILE_BYTES["Name"], conn=conn)
        if result is not None:
            db_updated2 = True
        sleep(0.3)
    print(result)
    assert db_updated2
    # check with encoding specified
    assert plugin_base.get_file("testfile2.txt", encoding="utf-8") == "This is just a TEST!"
    # bad codec
    with raises(LookupError):
        plugin_base.get_file("testfile2.txt", encoding="MYNEWSTANDARD")

def test_get_value(plugin_base):
    input_job = deepcopy(SAMPLE_JOB)
    input_job["JobCommand"] = {
        "CommandName": "TestCommand",
        "Tooltip": " testing command",
        "Output": True,
        "Inputs": [
            {
                "Name": "testinput",
                "Type": "textbox",
                "Tooltip": "fortesting",
                "Value": "Test Input 1"
            }
        ],
        "OptionalInputs": [
            {
                "Name": "testinput2",
                "Type": "textbox",
                "Tooltip": "fortesting",
                "Value": "Test Input 2"
            }
        ]
    }

    assert controller_plugin.ControllerPlugin.value_of_input(input_job, 0) == "Test Input 1"
    assert controller_plugin.ControllerPlugin.value_of_input(input_job, "testinput") == "Test Input 1"
    assert controller_plugin.ControllerPlugin.value_of_input(input_job, "bad") == None
    assert controller_plugin.ControllerPlugin.value_of_option(input_job, 0) == "Test Input 2"
    assert controller_plugin.ControllerPlugin.value_of_option(input_job, "testinput2") == "Test Input 2"
    assert controller_plugin.ControllerPlugin.value_of_option(input_job, "bad") == None

    assert controller_plugin.ControllerPlugin.value_of(input_job, "testinput") == "Test Input 1"
    assert controller_plugin.ControllerPlugin.value_of(input_job, "testinput2") == "Test Input 2"
    assert controller_plugin.ControllerPlugin.value_of(input_job, 0) == None

    assert controller_plugin.ControllerPlugin.value_of_input(input_job, 5) == None
    assert controller_plugin.ControllerPlugin.value_of_option(input_job, 5) == None

    inputs, optional = controller_plugin.ControllerPlugin.get_args(input_job)
    assert inputs[0] == "Test Input 1"
    assert optional[0] == "Test Input 2"

    assert controller_plugin.ControllerPlugin.get_status(input_job) == "Ready"
    assert controller_plugin.ControllerPlugin.job_location(input_job) == "127.0.0.1"
    assert controller_plugin.ControllerPlugin.job_port(input_job) == "8080"
    assert controller_plugin.ControllerPlugin.has_output(input_job) == True
