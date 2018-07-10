from json import dump
from multiprocessing import Process
from os import environ, remove
from time import sleep, time

import brain
import docker
from pytest import fixture, raises

from ..controller import *
from .. import server
from .test_controller import brain_conn, clear_dbs, controller, env, rethink

CLIENT = docker.from_env()


@fixture(scope="function")
def server_proc():
    """Give a server Process

    Returns:
        {multiprocessing.Process} -- controller's main loop,
        not started yet.
    """
    server.RETHINK_HOST = "localhost"
    server.PLUGIN_CONTROLLER.rethink_host = "localhost"
    server.PLUGIN_CONTROLLER.network_name = "test"
    server.MANIFEST_FILE = "./test-manifest.json"
    server.PLUGIN_CONTROLLER.tag = environ["TRAVIS_BRANCH"]
    proc = Process(target=server.main)
    yield proc
    try:
        proc.terminate()
    except Exception as ex:
        print(ex)

@fixture(scope="module")
def give_manifest():
    """Give a plugin manifest
    """
    with open("./test-manifest.json", "w") as outfile:
        dump([{"Name": "Harness"}, {"Name": "Harness2"}], outfile)
    yield
    remove("./test-manifest.json")

@fixture(scope="module")
def clean_up_containers():
    yield
    for con in server.PLUGIN_CONTROLLER.get_all_containers():
        try:
            con.stop(timeout=1)
        except:
            pass
        try:
            con.remove()
        except:
            pass

def test_make_available(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test automatic creation of plugin entry
    in the Controller.Plugins table.
    """
    server_proc.start()
    sleep(3)
    result = brain.queries.get_plugin_by_name_controller("Harness", conn=brain_conn).next()
    assert result["Name"] == "Harness"
    assert result["State"] == "Available"
    assert result["DesiredState"] == ""
    assert result["Interface"] == ""
    assert result["ExternalPort"] == []
    assert result["InternalPort"] == []
    result = brain.queries.get_plugin_by_name_controller("Harness2", conn=brain_conn).next()
    assert result["Name"] == "Harness2"
    assert result["State"] == "Available"
    assert result["DesiredState"] == ""
    assert result["Interface"] == ""
    assert result["ExternalPort"] == []
    assert result["InternalPort"] == []

def test_available_to_start(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test starting a plugin which is already in
    the database as 'Available'.
    """
    server_proc.start()
    sleep(3)
    result = brain.queries.update_plugin_controller(
        {
            "Name": "Harness",
            "DesiredState": "Activate",
            "ExternalPort": ["".join((str(5000), "/tcp"))],
            "InternalPort": ["".join((str(5000), "/tcp"))]
        },
        conn=brain_conn
    )
    assert result["errors"] == 0
    sleep(8)
    con = server.PLUGIN_CONTROLLER.get_container_from_name("Harness")
    assert con
    assert con.status == "running"
    result = brain.queries.get_plugin_by_name_controller("Harness", conn=brain_conn).next()
    assert result["Name"] == "Harness"
    assert result["State"] == "Active"
    assert result["DesiredState"] == ""
    # check ports

def test_active_to_stop(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test stopping a running plugin.
    """
    server_proc.start()
    sleep(3)
    server.PLUGIN_CONTROLLER.launch_plugin({
        "Name": "Harness",
        "DesiredState": "",
        "Interface": "",
        "ExternalPort": ["".join((str(5000), "/tcp"))],
        "InternalPort": ["".join((str(5000), "/tcp"))]
    })
    sleep(5)
    assert server.PLUGIN_CONTROLLER.get_container_from_name("Harness").status == "running"
    result = brain.queries.update_plugin_controller(
        {
            "Name": "Harness",
            "DesiredState": "Stop"
        },
        conn=brain_conn
    )
    assert result["errors"] == 0
    exited = False
    now = time()
    while time() - now < 20:
        con = server.PLUGIN_CONTROLLER.get_container_from_name("Harness")
        if con.status == "exited":
            exited = True
            break
        sleep(1)
    assert exited
    sleep(3)
    result = brain.queries.get_plugin_by_name_controller("Harness", conn=brain_conn).next()
    assert result["Name"] == "Harness"
    assert result["State"] == "Stopped"
    assert result["DesiredState"] == ""

def test_active_to_restart(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test restarting an active plugin.
    """
    server_proc.start()
    sleep(3)
    server.PLUGIN_CONTROLLER.launch_plugin({
        "Name": "Harness",
        "DesiredState": "",
        "Interface": "",
        "ExternalPort": ["".join((str(5000), "/tcp"))],
        "InternalPort": ["".join((str(5000), "/tcp"))]
    })
    sleep(5)
    assert server.PLUGIN_CONTROLLER.get_container_from_name("Harness").status == "running"
    result = brain.queries.update_plugin_controller(
        {
            "Name": "Harness",
            "DesiredState": "Restart"
        },
        conn=brain_conn
    )
    assert result["errors"] == 0
    sleep(1.5)
    result = brain.queries.get_plugin_by_name_controller("Harness", conn=brain_conn).next()
    assert result["Name"] == "Harness"
    assert result["State"] == "Restarting"
    assert result["DesiredState"] == "Restart"
    sleep(12)
    result = brain.queries.get_plugin_by_name_controller("Harness", conn=brain_conn).next()
    assert result["Name"] == "Harness"
    assert result["State"] == "Active"
    assert result["DesiredState"] == ""

def test_stopped_to_activate(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test starting a stopped plugin.
    """
    pass

def test_invalid_transitions(brain_conn, clear_dbs, env, rethink, server_proc, give_manifest):
    """Test invalid state transitions.
    Active -> Activate, Stopped -> Stop: same state message
    Restarting -> *: restarting, please wait."""
    pass
