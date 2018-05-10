"""Unit testing for the linked_process module.
"""

from multiprocessing import Queue
from pytest import fixture, raises
from time import time

TO_PLUGIN, FROM_PLUGIN = Queue(), Queue()

SAMPLE_TARGET = {
    "id": "w93hyh-vc83j5i-v82h54u-b6eu4n",
    "PluginName": "SamplePlugin",
    "Location": "127.0.0.1",
    "Port": "8080",
    "Optional": {
        "TestVal1": "Test value",
        "TestVal2": "Test value 2"
    }
}

SAMPLE_JOB = {
    "id": "138thg-eg98198-sf98gy3-feh8h8",
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": int(time()),
    "JobCommand": "Do stuff"
}

def dummy_interface():
    next_item = FROM_PLUGIN.get()
    if next_item["type"] == "job_request":
        TO_PLUGIN.put({
            SAMPLE_JOB
        })
    elif next_item["type"] == "functionality":
        return next_item["data"]
    elif next_item["type"] == "job_response":
        return next_item["data"]
    else:
        return None

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

