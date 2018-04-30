"""Unit testing for the supervisor module.
"""

from ctypes import c_bool
from multiprocessing import connection, Pipe, Value
from os import environ
from pytest import fixture, raises


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

    for proc in [sup.logger_process, sup.db_process, sup.plugin_process]:
        assert isinstance(proc, linked_process.LinkedProcess)

    assert isinstance(sup.plugin, controller_plugin.ControllerPlugin)
    assert isinstance(sup.db_interface, rethink_interface.RethinkInterface)
    assert isinstance(sup.logger_instance, central_logger.CentralLogger)

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
