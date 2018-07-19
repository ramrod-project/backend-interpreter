"""Unit testing for the supervisor module.
"""

from ctypes import c_bool
from multiprocessing import connection, Pipe, Value
from os import environ, name as osname
from time import sleep

from pytest import fixture, raises
import docker
CLIENT = docker.from_env()

from src import central_logger, controller_plugin, linked_process, rethink_interface, supervisor

assert osname == 'posix'

@fixture(scope="module")
def sup():
    environ["LOGLEVEL"] = "DEBUG"
    environ["STAGE"] = "TESTING"
    environ["PORT"] = "5000"
    tag = "latest"
    try:
        tag = environ["TRAVIS_BRANCH"].replace("master", "latest")
    except KeyError:
        pass
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
    )
    sleep(3)
    sup = supervisor.SupervisorController("Harness")
    yield sup
    try:
        environ["LOGLEVEL"] = ""
        containers = CLIENT.containers.list()
        for container in containers:
            if container.name == "rethinkdb":
                container.stop()
                break
        sup.teardown(0)
    except SystemExit:
        pass


def test_supervisor_setup(sup):
    """Test the Supervisor class.
    """
    # DEV environment test
    assert isinstance(sup, supervisor.SupervisorController)
    environ["STAGE"] = ""
    with raises(KeyError):
        sup.create_servers()
    environ["STAGE"] = "TESTING"
    assert isinstance(sup.plugin, controller_plugin.ControllerPlugin)


def test_supervisor_server_creation(sup):
    # Test server creation
    sup.create_servers()
    for proc in [sup.logger_process, sup.plugin_process]:
        assert isinstance(proc, linked_process.LinkedProcess)

    assert isinstance(sup.plugin, controller_plugin.ControllerPlugin)
    assert isinstance(sup.logger_instance, central_logger.CentralLogger)

def test_supervisor_log_creation(sup):
    # Test log creation
    assert sup.logger_process

def test_supervisor_server_spawn(sup):
    # Test server spawning
    sup.spawn_servers()
    
    for proc in [sup.logger_process, sup.plugin_process]:
        assert proc.is_alive()

def test_linked_process_creation(sup):
    # Test linked process creation
    assert sup.logger_instance