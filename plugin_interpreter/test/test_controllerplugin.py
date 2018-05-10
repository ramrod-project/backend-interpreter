"""Unit testing for the linked_process module.
"""

import multiprocessing
from pytest import fixture, raises
from threading import Thread
from time import time

from src import controller_plugin

TO_PLUGIN, FROM_PLUGIN = multiprocessing.Queue(), multiprocessing.Queue()

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

class SamplePlugin(controller_plugin.ControllerPlugin):

    def __init__(self):
        super().__init__(
            "SamplePlugin",
            "TCP",
            "8080",
            [
                {
                    "name": "read_file",
                    "input": ["string"],
                    "family": "filesystem",
                    "tooltip": "Provided a full directory path, this function reads a file.",
                    "reference": "http://reference.url"
                },
                {
                    "name": "send_file",
                    "input": ["string", "binary"],
                    "family": "filesystem",
                    "tooltip": "Provided a file and destination directory, this function sends a file.",
                    "reference": "http://reference.url"
                }
            ]
        )
    
    def start(self):
        pass
    
    def _stop(self):
        pass


def dummy_interface():
    next_item = FROM_PLUGIN.get()
    if next_item["type"] == "job_request":
        TO_PLUGIN.put(SAMPLE_JOB)
    elif next_item["type"] == "functionality":
        return next_item["data"]
    elif next_item["type"] == "job_response":
        return next_item["data"]
    else:
        raise KeyError

@fixture(scope="module")
def plugin_base():
    plugin = SamplePlugin()
    plugin.initialize_queues(FROM_PLUGIN, TO_PLUGIN)
    yield plugin

def test_instantiate():
    with raises(TypeError):
        plugin = controller_plugin.ControllerPlugin()
    plugin = SamplePlugin()
    assert isinstance(plugin, controller_plugin.ControllerPlugin)
    plugin.initialize_queues(FROM_PLUGIN, TO_PLUGIN)
    assert isinstance(plugin.db_send, multiprocessing.queues.Queue)
    assert isinstance(plugin.db_recv, multiprocessing.queues.Queue)

def test_advertise(plugin_base):
    plugin_base._advertise_functionality()
    result = dummy_interface()
    assert result[0] == "SamplePlugin"
    assert result[1] == plugin_base.functionality

def test_request_job(plugin_base):
    responder = Thread(target=dummy_interface)
    responder.start()
    result = plugin_base._request_job()
    assert result == SAMPLE_JOB

def test_respond_to_job(plugin_base):
    with raises(TypeError):
        plugin_base._job_response(SAMPLE_JOB, None)
    def func():
        pass
    with raises(TypeError):
        plugin_base._job_response(SAMPLE_JOB, func)

    plugin_base._job_response(SAMPLE_JOB, "Sample Job Response")
    result = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == "Sample Job Response"

    plugin_base._job_response(SAMPLE_JOB, bytes("Sample Job Response", "utf-8"))
    result = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == bytes("Sample Job Response", "utf-8")

    plugin_base._job_response(SAMPLE_JOB, 666)
    result = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == 666

    plugin_base._job_response(SAMPLE_JOB, 42.42)
    result = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == 42.42
