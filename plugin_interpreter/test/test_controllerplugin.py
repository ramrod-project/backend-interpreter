"""Unit testing for the linked_process module.
"""

import multiprocessing
from threading import Thread
from time import time

from pytest import fixture, raises

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
    """Sample plugin for testing

    Sample plugin inheriting from ControllerPlugin base
    class. All it does is initialize an instance of
    itself with some basic parameters, since the
    ControllerPlugin Abstract Base Class cannot be
    directly instanced.

    Arguments:
        controller_plugin {class} -- The base class
        for plugins, which is the subject of testing.
    """


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
                    "tooltip": "Provided a full directory path, this function \
                    reads a file.",
                    "reference": "http://reference.url"
                },
                {
                    "name": "send_file",
                    "input": ["string", "binary"],
                    "family": "filesystem",
                    "tooltip": "Provided a file and destination directory, \
                    this function sends a file.",
                    "reference": "http://reference.url"
                }
            ]
        )

    def start(self, logger, signal):
        """abstractmethod overload"""
        pass

    def _stop(self, **kwargs):
        """abstractmethod overload"""
        pass


def dummy_interface():
    """Simulates database interface

    Returns:
        object -- returns the 'data'
        value from the message received
        on the plugin queue.
    """
    next_item = FROM_PLUGIN.get()
    if next_item["type"] == "job_request":
        TO_PLUGIN.put(SAMPLE_JOB)
    elif next_item["type"] == "functionality":
        return next_item["data"]
    elif next_item["type"] == "job_response":
        status_update = FROM_PLUGIN.get()
        return (next_item["data"], status_update["data"]["status"])
    return None

@fixture(scope="module")
def plugin_base():
    """Generates SamplePlugin instance

    This fixture instances a SamplePlugin
    for use in testing.
    """
    plugin = SamplePlugin()
    plugin.initialize_queues(FROM_PLUGIN, TO_PLUGIN)
    yield plugin

def test_instantiate():
    """Test plugin instancing

    Instantiates the SamplePlugin and attempts
    to populate its queue attributes.
    """
    with raises(TypeError):
        plugin = controller_plugin.ControllerPlugin()
    plugin = SamplePlugin()
    assert isinstance(plugin, controller_plugin.ControllerPlugin)
    plugin.initialize_queues(FROM_PLUGIN, TO_PLUGIN)
    assert isinstance(plugin.db_send, multiprocessing.queues.Queue)
    assert isinstance(plugin.db_recv, multiprocessing.queues.Queue)

def test_advertise(plugin_base):
    """Test functionality advertisement

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    plugin_base._advertise_functionality()
    result = dummy_interface()
    assert result[0] == "SamplePlugin"
    assert result[1] == plugin_base.functionality

def test_request_job(plugin_base):
    """Test requesting a job

    Start a dummy_interface thread to send
    the response, then request a job.

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    responder = Thread(target=dummy_interface)
    responder.start()
    result = plugin_base._request_job()
    assert result == SAMPLE_JOB
    status = FROM_PLUGIN.get(timeout=3)
    assert status["data"]["status"] == "Pending"

def test_respond_to_job(plugin_base):
    """Test sending job response

    Tests the various types of allowed response
    data types.

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    with raises(TypeError):
        plugin_base._respond_output(SAMPLE_JOB, None)
    with raises(TypeError):
        plugin_base._respond_output(SAMPLE_JOB, dummy_interface)

    plugin_base._respond_output(SAMPLE_JOB, "Sample Job Response")
    result, status = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == "Sample Job Response"
    assert status == "Done"

    plugin_base._respond_output(SAMPLE_JOB, bytes("Sample Job Response", "utf-8"))
    result, status = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == bytes("Sample Job Response", "utf-8")
    assert status == "Done"

    plugin_base._respond_output(SAMPLE_JOB, 666)
    result, status = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == 666
    assert status == "Done"

    plugin_base._respond_output(SAMPLE_JOB, 42.42)
    result, status = dummy_interface()
    assert result["job"] == SAMPLE_JOB
    assert result["output"] == 42.42
    assert status == "Done"
