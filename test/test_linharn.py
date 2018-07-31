from pytest import raises, fixture
from os import environ
from time import sleep, time
from copy import deepcopy
from multiprocessing import Process
import brain
import docker
from Harness_client import linharn

CLIENT = docker.from_env()

class Linharn_proc:

    def __init__(self):
        self.procs = []
    
    def add_proc(self, func_):
        self.procs.append(Process(target=func_))
        return self.procs[-1]

SAMPLE_TARGET = {
    "PluginName": "Harness",
    "Location": "127.0.0.1",
    "Port": "8080"
}

NOW = time()

ECHO_JOB = {
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": NOW,
    "JobCommand":  {
        "CommandName": "echo",
        "Tooltip": " testing command",
        "Output": True,
        "Inputs": [
            {
                "Name": "testinput",
                "Type": "textbox",
                "Tooltip": "fortesting",
                "Value": "Hello World"
            }
        ],
        "OptionalInputs": []
    }
}

SLEEP_JOB = {
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": NOW,
    "JobCommand":  {
        "CommandName": "sleep",
        "Tooltip": " testing command",
        "Output": False,
        "Inputs": [],
        "OptionalInputs": []
    }
}

@fixture(scope="module")
def startup_brain():
    old_log = environ.get("LOGLEVEL", "")
    environ["LOGLEVEL"] = "DEBUG"
    tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain:", tag)),
        name="rethinkdbtestapp",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
    )
    sleep(3) #docker needs to start up the DB
    yield
    try:
        environ["LOGLEVEL"] = old_log
        containers = CLIENT.containers.list()
        for container in containers:
            if container.name == "rethinkdbtestapp":
                container.stop()
                break
    except SystemExit:
        pass

@fixture(scope="function")
def proc():
    old_plugin = environ.get("PLUGIN", "")
    old_stage = environ.get("STAGE", "")
    old_port = environ.get("PORT", "")
    environ["PLUGIN"] = "Harness"
    environ["STAGE"] = "TESTING"
    environ["PORT"] = "5000"
    import server
    plugin_instance = server.get_class_instance("Harness")
    sleep(5)
    process = Process(target=plugin_instance.start)
    yield process
    try:
        process.terminate()
    except:
        pass
    environ["PLUGIN"] = old_plugin
    environ["STAGE"] = old_stage
    environ["PORT"] = old_port

@fixture
def linux_harn(scope="function"):
  proc_list = Linharn_proc()
  yield proc_list
  try:
      for proc in proc_list.procs:
        proc.terminate()
  except:
      pass

@fixture
def linux_harn2(scope="function"):
  process = Process(target=wrap_loop)
  yield process
  try:
      process.terminate()
  except:
      pass

def wrap_loop():
  client_info = "C_127.0.0.1_1"
  linharn.control_loop(client_info)

def test_linharn(startup_brain, proc, linux_harn):
    # procs = Linharn_proc()
    lin1 = linux_harn.add_proc(wrap_loop)
    lin2 = linux_harn.add_proc(wrap_loop)
    proc.start()
    while not proc.is_alive():
        sleep(.5)
    # linux_harn.start()
    lin1.start()
    sleep(8)
    echo = brain.queries.get_plugin_command("Harness", "echo", brain.connect())
    echo_job = {
        "Status" : "Waiting",
        "StartTime": time(),
        "JobTarget": SAMPLE_TARGET,
        "JobCommand": echo
    }
    echo_job["JobCommand"]["Inputs"][0]["Value"] = "Hello World"
    inserted = brain.queries.insert_jobs([echo_job], True, brain.connect())
    loop = True
    now = time()
    while time() - now < 30 and loop is True:
        out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
        if out is not None:
            loop = False
        sleep(1)
    assert out == "Hello World"

    sleep_job = {
        "Status" : "Waiting",
        "StartTime": time(),
        "JobTarget": SAMPLE_TARGET,
        "JobCommand": brain.queries.get_plugin_command("Harness", "sleep", brain.connect())
    }
    sleep_job["JobCommand"]["Inputs"][0]["Value"] = "3000"
    inserted = brain.queries.insert_jobs([sleep_job], True, brain.connect())
    sleep(15)
    out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
    assert out == ""
