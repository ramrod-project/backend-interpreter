import logging
from os import environ, path
from sys import path as syspath, stderr
from time import sleep, time

import docker
from pytest import fixture, raises

CONTROLLER_PATH = path.join(
    "/".join(path.abspath(__file__).split("/")[:-2])
)
CLIENT = docker.from_env()

syspath.append(CONTROLLER_PATH)

from server import *

@fixture(scope="module")
def env():
    """Set the environment variables for module tests
    """
    environ["STAGE"] = "DEV"
    environ["LOGLEVEL"] = "DEBUG"
    try:
        if environ["TRAVIS_BRANCH"] not in ["dev, qa, master"]:
            stderr.write("TRAVIS_BRANCH must be set to dev|qa|master!\n")
    except KeyError:
        environ["TRAVIS_BRANCH"] = "master"
    yield
    environ["STAGE"] = ""
    environ["LOGLEVEL"] = ""

@fixture(scope="function")
def logger():
    """Give a test logger
    """
    yield logging.getLogger('test')

@fixture(scope="function")
def container():
    """Give a container to a test
    """
    CLIENT.networks.create("test")
    yield CLIENT.containers.run(
        "alpine:3.7",
        name="testcontainer",
        command="sleep 30",
        detach=True,
        network="test"
    )

def test_set_logging(env, logger):
    """Tests the set_logging function
    """
    set_logging(logger)
    assert logger.getEffectiveLevel() == logging.DEBUG, "Logging level should be DEBUG!"
    environ["LOGLEVEL"] = "INFO"
    set_logging(logger)
    assert logger.getEffectiveLevel() == logging.INFO, "Logging level should be INFO!"
    environ["LOGLEVEL"] = "WARNING"
    set_logging(logger)
    assert logger.getEffectiveLevel() == logging.WARNING, "Logging level should be WARNING!"
    environ["LOGLEVEL"] = "ERROR"
    set_logging(logger)
    assert logger.getEffectiveLevel() == logging.ERROR, "Logging level should be ERROR!"
    environ["LOGLEVEL"] = "CRITICAL"
    set_logging(logger)
    assert logger.getEffectiveLevel() == logging.CRITICAL, "Logging level should be CRITICAL!"
    environ["LOGLEVEL"] = ""
    with raises(SystemExit):
        set_logging(logger)

def test_dev_db(env):
    """Test the dev_db function
    """
    result = dev_db({28015: None})
    assert not result, "Should return False when port is already allocated!"
    port_mapping = {}
    result = dev_db(port_mapping)
    assert result, "Should return True on succesful creation of db"
    assert isinstance(port_mapping[28015], docker.models.containers.Container), "dev_db should set 28015 key to Container object!"
    assert port_mapping[28015].name == "rethinkdb", "Rethink container name should be rethinkdb!"
    assert CLIENT.containers.get("rethinkdb").status == "running", "Rethinkdb container should be running!"
    assert "test" in [n.name for n in CLIENT.networks.list()], "dev_db should create 'test' network in DEV environment!"
    port_mapping[28015].stop()
    CLIENT.networks.prune()

def test_generate_port(env):
    port_mapping = {}
    port = generate_port(port_mapping)
    assert 1024 < port <= 65535, "Port must be within valid range 1025-65535!"

def test_launch_container(env):
    """Tests the launch_container function
    """
    with raises(AssertionError):
        launch_container(9000, 6000, 5005, "TCP")
    with raises(AssertionError):
        launch_container("Harness", 6000, 5005, "RTCP")
    with raises(AssertionError):
        launch_container("Harness", 6000, "80", "TCP")
    with raises(AssertionError):
        launch_container("Harness", 6000, 999999, "TCP")
    CLIENT.networks.create("test")
    con = launch_container("Harness", 6000, 5005, "TCP")
    sleep(3)
    con = CLIENT.containers.get(con.id)
    assert con.status == "running"
    assert con.name == "Harness-5005_TCP"
    con.stop()
    CLIENT.networks.prune()

def test_stop_containers(env, container):
    """Tests the teardown function
    """
    assert container
    stop_containers([container])
    sleep(1)
    con = CLIENT.containers.get("testcontainer")
    assert con.status == "exited"
    con.remove()
    stop_containers([container])
