"""Unit test file for RethinkInterface class.
"""

from ctypes import c_bool
from multiprocessing import Value
from pytest import fixture, raises
from threading import Thread
from time import sleep

from plugins import plugin_1
from src import rethink_interface


class mock_logger():

    def __init__(self):
        pass

    def send(self, msg):
        pass


@fixture(scope='module')
def rethink():
    plugins = []
    for _ in range(5):
        c = plugin_1.TestPlugin1()
        plugins.append(c)
    server = ('127.0.0.1', 28015)
    yield rethink_interface.RethinkInterface(plugins, server)


def test_rethink_setup(rethink):
    with raises(TypeError):
        re = rethink_interface.RethinkInterface()
    assert type(rethink) == rethink_interface.RethinkInterface


def test_rethink_start(rethink):
    logger = mock_logger()
    val = Value(c_bool, False)
    rethink_thread = Thread(target=rethink.start, args=(logger, val))
    rethink_thread.start()
    assert rethink_thread.is_alive()
    val.value = False
    sleep(1)
    assert not rethink_thread.is_alive()
