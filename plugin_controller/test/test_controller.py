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

from ..controller import *

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
def container():
    """Give a container to a test
    """
    CLIENT.networks.create("test")
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

def test_launch_container(env, controller):
    """Tests the launch_container function
    """
    with raises(TypeError):
        controller.launch_plugin("Harness", {6000: 5005}, "RTCP")
    with raises(ValueError):
        controller.launch_plugin("Harness", {6000: 999999}, "TCP")
    CLIENT.networks.create("test")
    con = controller.launch_plugin("Harness", {6000: 5005}, "TCP")
    sleep(3)
    con = CLIENT.containers.get(con.id)
    assert con.status == "running"
    assert con.name == "Harness"
    con.stop()
    CLIENT.networks.prune()

def test_stop_containers(env, container, controller):
    """Tests the teardown function
    """
    assert container
    controller.stop_plugin("testcontainer")
    sleep(1)
    con = CLIENT.containers.get("testcontainer")
    assert con.status == "exited"
    con.remove()
