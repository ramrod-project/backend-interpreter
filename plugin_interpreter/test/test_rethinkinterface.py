"""Unit test file for RethinkInterface class.
"""

from ctypes import c_bool
from multiprocessing import Value
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
    plugin = ExampleHTTP()
    CLIENT.containers.run(
        "rethinkdb",
        name="rethinkdb_rethink",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
    )
    server = ('127.0.0.1', 28015)
    sleep(4)
    yield rethink_interface.RethinkInterface(plugin, server)
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == "rethinkdb_rethink":
            container.stop()
            break

def compare_to(list1, list2):
    for i in list2:
        if i not in list1:
            return False
    return True

# def test_rethink_setup(rethink):
#     assert isinstance(rethink, rethink_interface.RethinkInterface)

def test_init(rethink):
    rethink._database_init()

# def test_rethink_start(rethink):
#     logger = mock_logger()
#     val = Value(c_bool, False)
#     rethink_thread = Thread(target=rethink.start, args=(logger, val))
#     rethink_thread.start()
#     assert rethink_thread.is_alive()
#     val.value = False
#     sleep(1)
#     assert not rethink_thread.is_alive()

# def test_rethink_plugin_create(rethink):
#     #test adding a valid table
#     command_list = [{
#                 "CommandName": "test_func_1",
#                 "Input": ["string"],
#                 "Output": "string",
#                 "Tooltip": "This is a test"
#             },
#             {
#                 "CommandName": "test_func_2",
#                 "Input": ["string"],
#                 "Output": "string",
#                 "Tooltip": "This is also a test"
#             }]
#     plugin_data = ("TestTable",command_list)
#     assert(compare_to(rethink._create_plugin_table(plugin_data), command_list))

#     #test updating a table
#     command_list = [{
#                 "CommandName": "test_func_1",
#                 "Input": ["string"],
#                 "Output": "string",
#                 "Tooltip": "This is a test"
#             },
#             {
#                 "CommandName": "test_func_2",
#                 "Input": ["string"],
#                 "Output": "string",
#                 "Tooltip": "This is also a test"
#             },
#             {
#                 "CommandName": "test_func_3",
#                 "Input": [],
#                 "Output": "",
#                 "Tooltip": "a bonus command"
#             }]
#     plugin_data = ("TestTable",command_list)
#     assert(compare_to(rethink._create_plugin_table(plugin_data), command_list))

    #test table with entries without primary key
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
    
# def test_next_job(rethink):
#     new_job = {
#         "JobTarget":{
#             "PluginName": "jobtester",
#             "Location": "8.8.8.8",
#             "Port": "80"
#         },
#         "JobCommand":{
#             "CommandName": "TestJob",
#             "Tooltip": "for testing jobs",
#             "Inputs":[]
#         },
#         "Status": "Ready",
#         "StartTime" : 0
#     }
#     rethinkdb.db("Brain").Table("Jobs").Insert(new_job).run(rethink.rethink_connection)
#     rethink._get_next_job("jobtester")

# def test_update_job(rethink):
    pass
