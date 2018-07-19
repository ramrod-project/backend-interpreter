"""Unit testing for the linked_process module.
"""
from json import dump, load
from os import environ, makedirs, remove, removedirs
from time import time, sleep

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

SAMPLE_JOB = {
    "id": "138thg-eg98198-sf98gy3-feh8h8",
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": int(time()),
    "JobCommand": "Do stuff"
}

SAMPLE_FILE = {
    "id": "testfile.txt",
    "Name": "testfile.txt",
    "ContentType": "data",
    "Timestamp": 123456789,
    "Content": "This is just a TEST!"
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


class DummyDBInterface():


    def __init__(self):
        self.result = None
        self.update = None
        self.status = None

    def create_plugin_table(self, db_data, db_data2):
        self.result = (db_data, db_data2)

    def update_job(self, job_id):
        self.update = job_id

    def send_output(self, job_id, output):
        self.result = {"job": job_id, "output": output}
    
    def update_job_error(self, data):
        self.status = "Error"
    
    def get_job(self):
        return SAMPLE_JOB

    def get_job_by_target(self, location):
        return SAMPLE_JOB
    
    def get_file(self, filename):
        return SAMPLE_FILE


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

    def start(self, logger, signal):
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

def test_instantiate():
    """Test plugin instancing

    Instantiates the SamplePlugin and attempts
    to populate its queue attributes.
    """
    with raises(TypeError):
        plugin = controller_plugin.ControllerPlugin()
    plugin = SamplePlugin(SAMPLE_FUNCTIONALITY)
    assert isinstance(plugin, controller_plugin.ControllerPlugin)

def test_job_helpers():
    assert controller_plugin.ControllerPlugin.get_command(SAMPLE_JOB) == SAMPLE_JOB["JobCommand"]
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
    assert result == SAMPLE_JOB
    brain.r.db("Brain").table("Jobs").get(SAMPLE_JOB["id"]).update({"Status": "Ready"}).run(conn)
    sleep(1)
    result = plugin_base.request_job_for_client("127.0.0.1")
    assert result == SAMPLE_JOB

def test_update_job(plugin_base, give_brain, clear_dbs, conn):
    plugin_base.db_conn = conn
    assert plugin_base._update_job("doenstexist") is None
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
    assert plugin_base._update_job(SAMPLE_JOB["id"]) == None
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
    with raises(TypeError):
        plugin_base.respond_output(SAMPLE_JOB, None)
    with raises(TypeError):
        plugin_base.respond_output(SAMPLE_JOB, {})

    plugin_base.respond_output(SAMPLE_JOB, "Sample Job Response")
    db_updated1 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result == "Sample Job Response":
            db_updated1 = True
        sleep(0.3)
    print(result)
    assert db_updated1

    plugin_base.respond_output(SAMPLE_JOB, bytes("Sample Job Response", "utf-8"))
    db_updated2 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result == bytes("Sample Job Response", "utf-8"):
            db_updated2 = True
        sleep(0.3)
    assert db_updated2

    plugin_base.respond_output(SAMPLE_JOB, 666)
    db_updated3 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result == 666:
            db_updated3 = True
        sleep(0.3)
    assert db_updated3

    plugin_base.respond_output(SAMPLE_JOB, 42.42)
    db_updated4 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result == 42.42:
            db_updated4 = True
        sleep(0.3)
    assert db_updated4

    plugin_base.respond_error(SAMPLE_JOB, "error")
    db_updated5 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_output_content(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result == "error":
            db_updated5 = True
        sleep(0.3)
    assert db_updated5

    db_updated6 = False
    now = time()
    while time() - now < 3:
        result = brain.queries.get_job_by_id(SAMPLE_JOB["id"], conn=conn)
        if result is not None and result["Status"] == "Error":
            db_updated6 = True
        sleep(0.3)
    assert db_updated6

def test_get_file(plugin_base, give_brain, clear_dbs):
    SAMPLE_FILE["Content"] = SAMPLE_FILE["Content"].encode("utf-8")
    # check with encoding specified
    assert plugin_base.get_file("testfile.txt", "utf-8") == "This is just a TEST!"
    # check without encoding to get bytes blob
    assert plugin_base.get_file("testfile.txt") == SAMPLE_FILE["Content"]
    # bad codec
    with raises(LookupError):
        plugin_base.get_file("testfile.txt","MYNEWSTANDARD")

def test_get_value(plugin_base):
    input_job = SAMPLE_JOB
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
    assert plugin_base.value_of_input(input_job, 0) == "Test Input 1"
    assert plugin_base.value_of_option(input_job, 0) == "Test Input 2"
    assert plugin_base.value_of_input(input_job, 5) == None
    assert plugin_base.value_of_option(input_job, 5) == None
