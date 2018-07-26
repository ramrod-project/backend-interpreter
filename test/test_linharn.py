from pytest import raises, fixture
from os import environ
from time import sleep, time
from multiprocessing import Process
import brain
import docker
from Harness_client import linharn

CLIENT = docker.from_env()

SAMPLE_TARGET = {
    "PluginName": "Harness",
    "Location": "127.0.0.1",
    "Port": "8080"
}

NOW = time()

SAMPLE_JOB = {
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
    sleep(3) #docker needs to start up the DB before sup starts up
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

# @fixture
# def linux_harn():
#   process = Process(target=wrap_loop())
#   yield process
#   try:
#       process.terminate()
#   except:
#       pass

def wrap_loop():
  client_info = "C_127.0.0.1_1"
  sleep(10)
  linharn.control_loop(client_info)

def test_linharn(startup_brain, proc):
    proc.start()
    echo_job = [SAMPLE_JOB]
    inserted = brain.queries.insert_jobs(echo_job, True, brain.connect())
    sleep(5)
    task = linharn.get_task("C_127.0.0.1_1")
    print(task)
    cmd, args = task.text.split(",",1)
    linharn.handle_resp(cmd, args, "C_127.0.0.1_1")
    out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
    assert out == "Hello World"
