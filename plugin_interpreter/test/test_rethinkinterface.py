"""Unit test file for RethinkInterface class.
"""

from ctypes import c_bool
from multiprocessing import Value
from os import environ
from threading import Thread
from time import sleep

from pytest import fixture, raises
import docker
import rethinkdb
CLIENT = docker.from_env()

from plugins import *
from src import rethink_interface


class mock_logger():

    def __init__(self):
        pass

    def send(self, msg):
        pass


@fixture(scope='module')
def rethink():
    # Setup for module tests
    try:
        tag = environ["TRAVIS_BRANCH"]
    except KeyError:
        tag = "latest"
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb_rethink",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    server = ('127.0.0.1', 28015)
    environ["STAGE"] = "DEV"
    plugin = Harness()
    rdb = rethink_interface.RethinkInterface(plugin, server)
    rdb.logger = mock_logger()
    yield rdb
    # Teardown for module tests
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == "rethinkdb_rethink":
            container.stop()
            break

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

    print("Table check")
    for i in tablecheck:
        print(i)
    for i in tablecheck:
        if i not in compare_list:
            return False
    return True

def test_rethink_setup(rethink):
    assert isinstance(rethink, rethink_interface.RethinkInterface)

def test_rethink_plugin_create(rethink):
    """Tests if the _plugin_create() function can successfully add a table to
    the plugin database and fill it with Commands. it then tests if the table
    can be updated with new Commands
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """

    #test adding a valid table
    command_list = [{
                "CommandName": "test_func_1",
                "Input": ["string"],
                "Output": "string",
                "Tooltip": "This is a test"
            },
            {
                "CommandName": "test_func_2",
                "Input": ["string"],
                "Output": "string",
                "Tooltip": "This is also a test"
            }]
    plugin_data = ("TestTable",command_list)
    rethink._create_plugin_table(plugin_data)
    tablecheck = rethinkdb.db("Plugins").table("TestTable").run(rethink.rethink_connection)
    assert compare_to(tablecheck, command_list)

    #test updating a table
    command_list = [{
                "CommandName": "test_func_1",
                "Input": ["string"],
                "Output": "string",
                "Tooltip": "This is a test"
            },
            {
                "CommandName": "test_func_2",
                "Input": ["string"],
                "Output": "string",
                "Tooltip": "This is also a test"
            },
            {
                "CommandName": "test_func_3",
                "Input": [],
                "Output": "",
                "Tooltip": "a bonus command"
            }]
    plugin_data = ("TestTable",command_list)
    rethink._create_plugin_table(plugin_data)
    tablecheck = rethinkdb.db("Plugins").table("TestTable").run(rethink.rethink_connection)
    assert compare_to(tablecheck, command_list)

    # #test table with entries without primary key
    # command_list = [{
    #             "name": "test_func_1",
    #             "Input": ["string"],
    #             "Output": "string",
    #             "Tooltip": "This is a test"
    #         },
    #         {
    #             "CommandName": "test_func_2",
    #             "Input": ["string"],
    #             "Output": "string",
    #             "Tooltip": "This is also a test"
    #         }]
    # plugin_data = ("TestNoKey", command_list)
    # rethink._create_plugin_table(plugin_data)
    # assert(compare_to(rethink._create_plugin_table(plugin_data), [{
    #             "CommandName": "test_func_2",
    #             "Input": ["string"],
    #             "Output": "string",
    #             "Tooltip": "This is also a test"
    #         }]))
    
def test_next_job(rethink):
    """Tests the _get_next_job() function by inserting a job into the
    Brain and testing if the function correctly gets the job and adds it to the
    plugin_queue
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """

    new_job = {
        "JobTarget":{
            "PluginName": "jobtester",
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
    rethink._get_next_job("jobtester")
    assert(rethink.plugin_queue.get(timeout=1) == None)
    rethinkdb.db("Brain").table("Jobs").insert(new_job).run(rethink.rethink_connection)
    rethink._get_next_job("jobtester")
    test_job = rethink.plugin_queue.get(timeout=1)
    assert compare_to(new_job,test_job)

def test_update_job(rethink):
    """Tests _update_job() by placing a job in the Jobs table and calling 
    update_jobs() to change the status of the job
    
    Arguments:
        rethink {Fixture} -- An instance of rethink interface
    """

    new_status = "Pending"
    try:
        job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
            (rethinkdb.row["JobTarget"]["PluginName"] == "jobtester") & \
            (rethinkdb.row["Status"] == "Ready")
        ).pluck("id").run(rethink.rethink_connection)
        
        test_job = job_cursor.next().get("id")
        print(test_job)
        job_dict = {
            "job": test_job,
            "status": new_status
        }
        rethink._update_job(job_dict)
        job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
            (rethinkdb.row["JobTarget"]["PluginName"] == "jobtester") & (rethinkdb.row["Status"] == new_status)
            ).pluck("Status").run(rethink.rethink_connection)
        test_job = job_cursor.next().get("Status")
        assert(test_job == new_status)
    except rethinkdb.ReqlCursorEmpty:
        print("Failed to get job in test_update_job")

def test_send_output(rethink):
    """Tests _send_output() by placing a job in the job queue, getting its
    id, and then calling _send_output() with a string of output and checking
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
    try:
        rethinkdb.db("Brain").table("Jobs").insert(output_job).run(rethink.rethink_connection)
        job_cursor = rethinkdb.db("Brain").table("Jobs").filter(
            rethinkdb.row["JobTarget"]["PluginName"] == "texter"
            ).pluck("id").run(rethink.rethink_connection)
        job_id = job_cursor.next()
        output_data = {
            "job": job_id,
            "output": content
        }
        rethink._send_output(output_data)
        output_cursor = rethinkdb.db("Brain").table("Outputs").filter(
            rethinkdb.row["OutputJob"]["id"]
            ).run(rethink.rethink_connection)
        #output_cursor.next()
        db_output = output_cursor.next().get("Content")
        assert(db_output == content)
    except rethinkdb.ReqlCursorEmpty:
        print("id could not be found after placing job into database")
    except rethinkdb.ReqlDriverError:
        print("Could not insert test job into table")

def test_update_output(rethink):
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
    rethink._update_job(updater)
    output_data = {
        "job": job_obj,
        "output": content
    }
    rethink._send_output(output_data)
    updater["status"] = "Done"
    rethink._update_job(updater)
    output_cursor = rethinkdb.db("Brain").table("Outputs").filter(
        rethinkdb.row["OutputJob"]["id"] == job_obj.get("id")
    ).run(rethink.rethink_connection)
    print(output_cursor)
    output_status = output_cursor.next().get("OutputJob",{}).get("Status")
    assert output_status == "Done"

def test_rethink_start(rethink):
    # Test running as thread (**THIS KILLS THE CONNECTION**)
    # Don't run tests after this one that require the connection...
    val = Value(c_bool, False)
    logger = mock_logger()
    rethink_thread = Thread(target=rethink.start, args=(logger, val))
    rethink_thread.start()
    assert rethink_thread.is_alive()
    val.value = True
    sleep(1)
    assert not rethink_thread.is_alive()