"""Unit test file for RethinkInterface class.
"""

from ctypes import c_bool
from multiprocessing import Value
from threading import Thread
from time import sleep

from pytest import fixture, raises
import docker
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
    yield rethink_interface.RethinkInterface(plugin, server)
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == "rethinkdb_rethink":
            container.stop()
            break


def test_rethink_setup(rethink):
    assert isinstance(rethink, rethink_interface.RethinkInterface)


def test_rethink_start(rethink):
    logger = mock_logger()
    val = Value(c_bool, False)
    rethink_thread = Thread(target=rethink.start, args=(logger, val))
    rethink_thread.start()
    assert rethink_thread.is_alive()
    val.value = False
    sleep(1)
    assert not rethink_thread.is_alive()
