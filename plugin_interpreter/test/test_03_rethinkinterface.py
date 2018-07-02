"""Unit test file for RethinkInterface class.
"""

from ctypes import c_bool
import logging
from multiprocessing import Pipe, Value
from os import environ
from threading import Thread
from time import asctime, gmtime, sleep, time

from pytest import fixture, raises
import docker
from brain import r as rethinkdb, connect

from plugins import *
from src import rethink_interface, linked_process


CLIENT = docker.from_env()
logging.basicConfig(
    filename="logfile",
    filemode="a",
    format='%(date)s %(name)-12s %(levelname)-8s %(message)s'
)
LOGGER = logging.getLogger('testlogger')


class mock_logger():


    def __init__(self):
        self.last_msg = None

    def send(self, msg):
        self.last_msg = msg
        LOGGER.log(
            50,
            msg,
            extra={
                "date": asctime(gmtime(time()))
            }
        )
        print(msg)


# Provide database-brain container for module tests
@fixture(scope='module')
def brain():
    # Setup for all module tests
    try:
        tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
        environ["STAGE"] = "TESTING"
    except KeyError:
        tag = "latest"
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb_rethink",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    yield
    # Teardown for all module tests
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == "rethinkdb_rethink":
            container.stop()
            break

# Provide connection to database-brain for module tests
@fixture(scope='function')
def rethink():
    # Setup for each test
    server = ("127.0.0.1", 28015)
    environ["STAGE"] = "DEV"
    environ["PORT"] = "5000"
    rdb = rethink_interface.RethinkInterface("test", server)
    # rdb.logger = mock_logger()
    yield rdb
    # Teardown for each test
    try:
        rdb.rethink_connection.close()
    except:
        pass
    clear_dbs(connect("127.0.0.1", 28015))

# Provide empty rethinkdb container for tests that need it
@fixture(scope='function')
def rethink_empty():
    # Setup
    CLIENT.containers.run(
        "rethinkdb:2.3.6",
        name="rethinkdb_rethink_empty",
        detach=True,
        ports={"28015/tcp": 28016},
        remove=True
    )
    conn = None
    now = time()
    while time() - now < 5:
        try:
            conn = rethinkdb.connect("127.0.0.1", 28016)
        except rethinkdb.ReqlDriverError:
            sleep(0.3)
    yield conn
    # Teardown
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == "rethinkdb_rethink_empty":
            container.stop()
            break

def clear_dbs(conn):
    rethinkdb.db("Brain").table("Targets").delete().run(conn)
    rethinkdb.db("Brain").table("Outputs").delete().run(conn)
    rethinkdb.db("Brain").table("Jobs").delete().run(conn)
    rethinkdb.db("Audit").table("Jobs").delete().run(conn)
    for table in rethinkdb.db("Plugins").table_list().run(conn):
        rethinkdb.db("Plugins").table(table).delete().run(conn)

def compare_to(tablecheck, compare_list):
    """[summary]
    
    Arguments:
        tablecheck {[type]} -- the item to check
        compare_list {same as tablecheck} -- the standard to check against, it
        may contain more items in it than tablecheck
    
    Returns:
        boolean -- whether or not items in table check are in compare_list
        if any items in tablecheck are not in compare_list return false
    """
    table_list = list(tablecheck)
    if len(table_list) is 0:
        return False
    for i in table_list:
        if i not in compare_list:
            return False
    return True

def test_rethink_setup(brain, rethink):
    assert isinstance(rethink, rethink_interface.RethinkInterface)

def test_rethink_plugin_create(brain, rethink):
    """Tests if the create_plugin_table() function can successfully add a table to
    the plugin database and fill it with Commands. it then tests if the table
    can be updated with new Commands
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """

    #test adding a valid table
    command_list = [{
                "CommandName": "test_func_1",
                "Input": [],
                "Output": True,
                "Tooltip": "This is a test",
                "OptionalInputs": []
            },
            {
                "CommandName": "test_func_2",
                "Input": [],
                "Output": False,
                "Tooltip": "This is also a test",
                "OptionalInputs": []
            }]
    plugin_data = ("TestTable",command_list)
    rethink.create_plugin_table(plugin_data)
    assert rethink.check_for_plugin("TestTable")
    tablecheck = rethinkdb.db("Plugins").table("TestTable").run(rethink.rethink_connection)
    assert compare_to(tablecheck, command_list)

    #test updating a table
    command_list = [{
                "CommandName": "test_func_1",
                "Input": [],
                "Output": True,
                "Tooltip": "This is a test",
                "OptionalInputs": []
            },
            {
                "CommandName": "test_func_2",
                "Input": ["string"],
                "Output": False,
                "Tooltip": "This is also a test",
                "OptionalInputs": []
            },
            {
                "CommandName": "test_func_3",
                "Input": [],
                "Output": True,
                "Tooltip": "a bonus command",
                "OptionalInputs": [],
                "ExtraTestKey": "You can add keys to your Command"
            }]
    plugin_data = ("TestTable",command_list)
    rethink.create_plugin_table(plugin_data)
    tablecheck = rethinkdb.db("Plugins").table("TestTable").run(rethink.rethink_connection)
    print(list(tablecheck))
    assert compare_to(tablecheck, command_list)
    assert any("ExtraTestKey" in command for command in list(tablecheck))

def test_update_job_status(brain, rethink):
    """Tests update_job() by placing a job in the Jobs table and calling 
    update_jobs() to change the status of the job
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """
    rethinkdb.db("Brain").table("Jobs").insert({
        "JobTarget": {
            "PluginName": "jobtester"
        },
        "Status": "Ready"
    }).run(rethink.rethink_connection)
    sleep(2)
    job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
        (rethinkdb.row["JobTarget"]["PluginName"] == "jobtester") & \
        (rethinkdb.row["Status"] == "Ready")
    ).pluck("id").run(rethink.rethink_connection)
    job_id = job_cursor.next().get("id")

    new_status = "Pending"
    job_dict = {
        "job": job_id,
        "status": new_status
    }
    rethink.update_job_status(job_dict)
    job_cursor = rethinkdb.db("Brain").table("Jobs").get(
        job_id
    ).pluck("Status").run(rethink.rethink_connection)
    job_status = job_cursor.get("Status")
    assert job_status == new_status

    job_dict = {
        "job" : job_id,
        "status": "Bad"
    }
    with raises(rethink_interface.InvalidStatus):
        rethink.update_job_status(job_dict)

def test_update_job(rethink):
    """tests the ability to move through the normal flow of the
    status "state machine"
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """
    new_job = {
        "JobTarget":{
            "PluginName": "advancer",
            "Location": "8.8.8.8",
            "Port": "80"
        },
        "JobCommand":{
            "CommandName": "TestJob",
            "Tooltip": "for testing jobs",
            "Inputs":[]
        },
        "Status": "Ready",
        "StartTime" : 0
    }

    rethinkdb.db("Brain").table("Jobs").insert(new_job).run(rethink.rethink_connection)

    job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
        (rethinkdb.row["JobTarget"]["PluginName"] == "advancer") & \
        (rethinkdb.row["Status"] == "Ready")
    ).pluck("id").run(rethink.rethink_connection)
    test_job = job_cursor.next().get("id")

    rethink.update_job(test_job)

    job_cursor = rethinkdb.db("Brain").table("Jobs").get(test_job
    ).pluck("Status").run(rethink.rethink_connection)
    test_res = job_cursor.get("Status")
    assert(test_res == "Pending")

    rethink.update_job(test_job)

    job_cursor = rethinkdb.db("Brain").table("Jobs").get(test_job
    ).pluck("Status").run(rethink.rethink_connection)
    test_res = job_cursor.get("Status")
    assert(test_res == "Done")

    rethink.update_job_error(test_job)
    job_cursor = rethinkdb.db("Brain").table("Jobs").get(test_job
    ).pluck("Status").run(rethink.rethink_connection)
    test_res = job_cursor.get("Status")
    assert(test_res == "Error")

def test_send_output(brain, rethink):
    """Tests send_output() by placing a job in the job queue, getting its
    id, and then calling send_output() with a string of output and checking
    if the entry was added to the Outputs Table
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """

    content = "This is some output"
    output_job = {
        "JobTarget":{
            "PluginName": "texter",
            "Location": "8.8.8.8",
            "Port": "80"
        },
        "JobCommand":{
            "CommandName": "GetText",
            "Tooltip": "for getting text",
            "Inputs":[]
        },
        "Status": "Ready",
        "StartTime" : 0
    }
    rethinkdb.db("Brain").table("Jobs").insert(output_job).run(rethink.rethink_connection)
    job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
        rethinkdb.row["JobTarget"]["PluginName"] == "texter"
        ).pluck("id").run(rethink.rethink_connection)
    job_id = job_cursor.next()
    output_data = {
        "job": job_id,
        "output": content
    }
    rethink.send_output(output_data)
    output_cursor = rethinkdb.db("Brain").table("Outputs").filter(
        rethinkdb.row["OutputJob"]["id"]
        ).run(rethink.rethink_connection)
    #output_cursor.next()
    db_output = output_cursor.next().get("Content")
    assert(db_output == content)

def test_get_table_contents(brain, rethink):
    """Tests getting an entire table
    
    Arguments:
        rethink {RethinkInterface} -- an instance of RethinkInterface
        for connecting to the test database.
    """
    rethinkdb.db("Brain").table("Jobs").delete().run(rethink.rethink_connection)
    results_none = rethink.get_table_contents("Brain", "Jobs")
    assert results_none == []
    rethinkdb.db("Brain").table("Jobs").insert([
        {
            "JobTarget":{
                "PluginName": "testplugin",
                "Location": "1.1.1.1",
                "Port": "9000"
            },
            "JobCommand":{
                "CommandName": "GetTest",
                "Tooltip": "for getting test",
                "Inputs":["string"]
            },
            "Status": "Ready",
            "StartTime" : 1000
        },
        {
            "JobTarget":{
                "PluginName": "testplugin",
                "Location": "1.1.1.1",
                "Port": "9000"
            },
            "JobCommand":{
                "CommandName": "SetTest",
                "Tooltip": "for setting test",
                "Inputs":["string"]
            },
            "Status": "Ready",
            "StartTime" : 900
        }
    ]).run(rethink.rethink_connection)
    results = rethink.get_table_contents("Brain", "Jobs")
    assert results != []
    assert len(results) == 2
    results[0].pop("id", None)
    results[1].pop("id", None)
    assert {
        "JobTarget":{
            "PluginName": "testplugin",
            "Location": "1.1.1.1",
            "Port": "9000"
        },
        "JobCommand":{
            "CommandName": "GetTest",
            "Tooltip": "for getting test",
            "Inputs":["string"]
        },
        "Status": "Ready",
        "StartTime" : 1000
    } in results
    assert {
        "JobTarget":{
            "PluginName": "testplugin",
            "Location": "1.1.1.1",
            "Port": "9000"
        },
        "JobCommand":{
            "CommandName": "SetTest",
            "Tooltip": "for setting test",
            "Inputs":["string"]
        },
        "Status": "Ready",
        "StartTime" : 900
    } in results

def test_update_output(brain, rethink):
    content = "This is some different output"
    new_job = {
        "JobTarget":{
            "PluginName": "updater",
            "Location": "8.8.8.8",
            "Port": "80"
        },
        "JobCommand":{
            "CommandName": "TestJob",
            "Tooltip": "for testing updates",
            "Inputs":[]
        },
        "Status": "Ready",
        "StartTime" : 0
    }
    rethinkdb.db("Brain").table("Jobs").insert(new_job).run(rethink.rethink_connection)
    job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
        rethinkdb.row["JobTarget"]["PluginName"] == "updater"
    ).pluck("id").run(rethink.rethink_connection)
    job_obj = job_cursor.next()
    updater = {
        "job" : job_obj.get("id"),
        "status": "Pending"
    }
    #test updating without any associated output
    rethink.update_job_status(updater)
    output_data = {
        "job": job_obj,
        "output": content
    }
    rethink.send_output(output_data)
    updater["status"] = "Done"
    rethink.update_job_status(updater)
    output_cursor = rethinkdb.db("Brain").table("Outputs").filter(
        rethinkdb.row["OutputJob"]["id"] == job_obj.get("id")
    ).run(rethink.rethink_connection)
    output_status = output_cursor.next().get("OutputJob",{}).get("Status")
    assert output_status == "Done"

def test_changefeed(brain, rethink):
    # Test the thread that monitors the changefeed
    val = Value(c_bool, False)
    send, _ = Pipe()
    rethink.plugin_name = "updater"
    rethink.start(val)
    assert rethink.job_fetcher.is_alive()
    rethinkdb.db("Brain").table("Jobs").delete().run(rethink.rethink_connection)
    new_job = {
        "JobTarget":{
            "PluginName": "updater",
            "Location": "8.8.8.8",
            "Port": "80"
        },
        "JobCommand":{
            "CommandName": "TestJob",
            "Tooltip": "for testing updates",
            "Inputs":[]
        },
        "Status": "Ready",
        "StartTime" : 0
    }
    rethinkdb.db("Brain").table("Jobs").insert(new_job).run(rethink.rethink_connection)
    sleep(3)
    test_job = rethink.plugin_queue.get()
    del test_job["id"]
    assert test_job == new_job
    val.value = True
    sleep(7)
    assert not rethink.job_fetcher.is_alive()

def test_changefeed_disconnect(brain, rethink):
    """Tests if changefeed disconnects when connection dies
    
    Arguments:
        rethink {RethinkInterface} -- an instance of RethinkInterface
        for connecting to the test database.
    """
    val = Value(c_bool, False)
    # rethink.logger = mock_logger()
    feed_conn_test = connect(host=rethink.host, port=rethink.port)
    thread_test = Thread(
        target=rethink.changefeed_thread,
        args=(val, feed_conn_test)
    )
    thread_test.start()
    assert thread_test.is_alive()
    sleep(1)
    feed_conn_test.close()
    sleep(7)
    assert not thread_test.is_alive()

def test_update_job_bad_id(brain, rethink):
    """Tests that a bad id to the update_job function
    
    Arguments:
        rethink {RethinkInterface} -- an instance of RethinkInterface
        for connecting to the test database.
    """
    rethink.update_job("fake-id")
    assert True

def test_check_for_plugin(brain, rethink):
    """Checks to see if a plugin exists in the db

    Queries the Plugins database for a plugin.
    
    Arguments:
        rethink {RethinkInterface} -- an instance of RethinkInterface
        for connecting to the test database.
    """
    assert not rethink.check_for_plugin("TestPlugin")
    conn = connect()
    rethinkdb.db("Plugins").table_create("TestPlugin").run(conn)
    sleep(1)
    assert rethink.check_for_plugin("TestPlugin")
