"""Unit testing for the linked_process module.
"""

from multiprocessing import Queue
from pytest import fixture, raises

TO_PLUGIN, FROM_PLUGIN = Queue(), Queue()

def dummy_interface():
    pass

@fixture(scope="module")
def plugin_base():
    pass

def test_instantiate():
    pass

def test_advertise(plugin_base):
    pass

def test_request_job(plugin_base):
    pass

def test_respond_to_job(plugin_base):
    pass

