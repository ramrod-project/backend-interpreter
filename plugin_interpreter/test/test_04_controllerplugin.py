"""Unit testing for the linked_process module.
"""

import multiprocessing
from os import environ
from threading import Thread
from time import time, sleep

from pytest import fixture, raises

from src import controller_plugin

TO_PLUGIN = multiprocessing.Queue()

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

environ["PORT"] = "8080"


class DummyDBInterface():


    def __init__(self):
        self.result = None
        self.update = None

    def create_plugin_table(self, db_data):
        self.result = db_data

    def update_job(self, job_id):
        self.update = job_id

    def send_output(self, output_data):
        self.result = output_data


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
        self.DBI = DummyDBInterface()

    def start(self, logger, signal):
        """abstractmethod overload"""
        pass

    def _stop(self, **kwargs):
        """abstractmethod overload"""
        pass


@fixture(scope="function")
def plugin_base():
    """Generates SamplePlugin instance

    This fixture instances a SamplePlugin
    for use in testing.
    """
    plugin = SamplePlugin()
    plugin.initialize_queues(TO_PLUGIN)
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
    plugin.initialize_queues(TO_PLUGIN)
    assert isinstance(plugin.db_recv, multiprocessing.queues.Queue)

def test_advertise(plugin_base):
    """Test functionality advertisement

    Arguments:
        plugin_base {fixture} -- yields the SamplePlugin
        instance needed for testing.
    """
    plugin_base._advertise_functionality()
    result = plugin_base.DBI.result
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
    TO_PLUGIN.put(SAMPLE_JOB)
    now = time()
    while time() - now < 3:
        result = plugin_base._request_job()
        if result is not None:
            break
        sleep(0.1)
    assert result == SAMPLE_JOB
    assert plugin_base.DBI.update == "138thg-eg98198-sf98gy3-feh8h8"

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
        plugin_base._respond_output(SAMPLE_JOB, DummyDBInterface)

    plugin_base._respond_output(SAMPLE_JOB, "Sample Job Response")
    assert plugin_base.DBI.result["job"] == SAMPLE_JOB
    assert plugin_base.DBI.result["output"] == "Sample Job Response"

    plugin_base._respond_output(SAMPLE_JOB, bytes("Sample Job Response", "utf-8"))
    assert plugin_base.DBI.result["job"] == SAMPLE_JOB
    assert plugin_base.DBI.result["output"] == bytes("Sample Job Response", "utf-8")

    plugin_base._respond_output(SAMPLE_JOB, 666)
    assert plugin_base.DBI.result["job"] == SAMPLE_JOB
    assert plugin_base.DBI.result["output"] == 666

    plugin_base._respond_output(SAMPLE_JOB, 42.42)
    assert plugin_base.DBI.result["job"] == SAMPLE_JOB
    assert plugin_base.DBI.result["output"] == 42.42
