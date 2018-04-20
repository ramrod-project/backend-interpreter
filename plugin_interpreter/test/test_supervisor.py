"""Unit testing for the supervisor module.
"""

from ctypes import c_bool
from multiprocessing import connection, Pipe, Value
from os import environ
from pytest import fixture, raises

from customtcp import customtcp
from customudp import customudp
from src import central_logger, controller_plugin, linked_process, rethink_interface, supervisor
import server


@fixture(scope='module')
def sup():
    sup = supervisor.SupervisorController()
    yield sup
    try:
        sup.teardown(0)
    except SystemExit:
        pass

def test_supervisor_setup(sup):
    """Test the Supervisor class.
    """
    # DEV environment test
    assert type(sup) == supervisor.SupervisorController
    environ['STAGE'] = ''
    with raises(KeyError):
        sup.create_servers()
    environ['STAGE'] = 'DEV'
    for plugin in sup.plugins:
        assert type(plugin) == controller_plugin.ControllerPlugin

def test_supervisor_server_creation(sup):
    # Test server creation
    sup.create_servers()
    for _, controller in sup.controllers.items():
        assert type(controller) == customtcp.CustomTCP or customudp.CustomUDP
    for _, proc in sup.plugin_processes.items():
        assert type(proc) == linked_process.LinkedProcess
    for _, proc in sup.controller_processes.items():
        assert type(proc) == linked_process.LinkedProcess

    assert type(sup.db_interface) == rethink_interface.RethinkInterface
    assert type(sup.db_process) == linked_process.LinkedProcess
    assert type(sup.logger_pipe) == connection.Connection
    assert type(sup.logger_instance) == central_logger.CentralLogger
    assert type(sup.logger_process) == linked_process.LinkedProcess

    assert sup.db_interface.host == '127.0.0.1'

def test_supervisor_server_spawn(sup):
    # Test server supawning
    sup.spawn_servers()
    
    assert sup.logger_process.is_alive() == True
    assert sup.db_process.is_alive() == True
    for _, proc in sup.controller_processes.items():
        assert proc.is_alive() == True
    for _, proc in sup.plugin_processes.items():
        assert proc.is_alive() == True
