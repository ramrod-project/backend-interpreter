import logging
from os import environ, path
from sys import path as syspath, stderr
from time import sleep, time

import brain
import docker
from pytest import fixture, raises

CONTROLLER_PATH = path.join(
    "/".join(path.abspath(__file__).split("/")[:-2])
)
CLIENT = docker.from_env()

syspath.append(CONTROLLER_PATH)

from ..controller import *


TEST_PLUGIN_DATA = {
    "Name": "Harness",
    "State": "Available",
    "DesiredState": "",
    "Interface": "",
    "ExternalPorts": ["5000"],
    "InternalPorts": ["5000"]
}

TEST_PORT_DATA = {
    "InterfaceName": "",
    "Address": "",
    "TCPPorts": ["5000"],
    "UDPPorts": []
}


def docker_net_create():
    try:
        CLIENT.networks.create("test")
    except:
        pass

def docker_net_remove():
    CLIENT.networks.prune()

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
def clear_dbs():
    conn = brain.connect()
    yield
    brain.r.db("Controller").table("Plugins").delete().run(conn)
    brain.r.db("Controller").table("Ports").delete().run(conn)
    sleep(1)

@fixture(scope="module")
def rethink():
    # Setup for all module tests
    docker_net_create()
    try:
        tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
        environ["STAGE"] = "TESTING"
    except KeyError:
        tag = "latest"
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        network="test"
    )
    yield
    # Teardown for all module tests
    containers = CLIENT.containers.list()
    for container in containers:
        container.stop()
        container.wait(timeout=5)
        container.remove()
    docker_net_remove()

@fixture(scope="function")
def container():
    """Give a container to a test
    """
    con = CLIENT.containers.run(
        "alpine:3.7",
        name="testcontainer",
        command="sleep 30",
        detach=True,
        network="test"
    )
    yield con
    try:
        con.stop()
    except:
        pass
    try:
        con.remove()
    except:
        pass

@fixture(scope="function")
def controller():
    """Give a Controller
    """
    return Controller("test", "dev")

def test_dev_db(env, controller):
    """Test the dev_db function
    """
    result = controller.dev_db()
    assert result, "Should return True on succesful creation of db"
    con = CLIENT.containers.get("rethinkdb")
    assert con.status == "running", "Rethinkdb container should be running!"
    assert "test" in [n.name for n in CLIENT.networks.list()], "dev_db should create 'test' network in DEV environment!"
    con.stop()
    CLIENT.networks.prune()

def test_create_plugin(env, controller, rethink, clear_dbs):
    """Test creating a plugin in the database.
    """
    pass

def test_create_port(env, controller, rethink, clear_dbs):
    """Test creating a port entry in the database.
    """
    pass

def test_update_plugin(env, controller, rethink, clear_dbs):
    """Test updating a plugin in the database.
    """
    pass

def test_launch_container(env, controller, rethink, clear_dbs):
    """Tests the launch_container function
    """
    with raises(TypeError):
        controller.launch_plugin("Harness", {6000: 5005}, "RTCP")
    with raises(ValueError):
        controller.launch_plugin("Harness", {6000: 999999}, "TCP")
    con = controller.launch_plugin("Harness", {6000: 5005}, "TCP")
    sleep(3)
    con = CLIENT.containers.get(con.id)
    assert con.status == "running"
    assert con.name == "Harness"
    con.stop()
    con.remove()
    CLIENT.networks.prune()

def test_wait_plugin(env, container, controller, rethink, clear_dbs):
    """Test waiting for a plugin to stop.
    """
    pass

def test_restart_plugin(env, container, controller, rethink, clear_dbs):
    """Test restarting a plugin.
    """
    pass

def test_plugin_status(env, container, controller, rethink, clear_dbs):
    """Test getting the status of a plugin.
    """
    pass

def test_get_all_containers(env, controller, rethink, clear_dbs):
    """Test getting a list of all containers.
    """
    pass

def test_stop_all_containers(env, controller, rethink, clear_dbs):
    """Test stopping multiple running containers
    """
    pass

def test_get_container_from_name(env, container, controller, rethink, clear_dbs):
    """Test getting a container by plugin name
    """
    pass

def test_stop_containers(env, container, controller, rethink, clear_dbs):
    """Tests the teardown function
    """
    assert container
    controller.stop_plugin({"Name": "testcontainer", "State": "Running"})
    sleep(1)
    con = CLIENT.containers.get("testcontainer")
    assert con.status == "exited"
    con.remove()
