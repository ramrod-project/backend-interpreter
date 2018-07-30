from pytest import raises, fixture
from os import environ
from time import sleep, time
from copy import deepcopy
from multiprocessing import Process
import brain
from brain.queries import get_plugin_commands
import docker
from Harness_client import linharn

CLIENT = docker.from_env()


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
    "JobCommand":  None
}

SLEEP_JOB = {
    "JobTarget": SAMPLE_TARGET,
    "Status": "Ready",
    "StartTime": NOW,
    "JobCommand":  None
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

@fixture
def linux_harn(scope="function"):
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
    proc.start()
    while not proc.is_alive():
        sleep(.5)
    sleep(10)
    commands = [x for x in get_plugin_commands("Harness")]
    assert commands == ""
    for cmd in commands:
        if "sleep" in cmd["CommandName"]:
            sleep_cmd = cmd
        elif "echo" in cmd["CommandName"]:
            echo_cmd = cmd


    echo_job = deepcopy(ECHO_JOB)
    echo_job['JobCommand'] = echo_cmd
    echo_job['JobCommand']["Inputs"][0]['Value'] = "Hello World"


    sleep_job = deepcopy(SLEEP_JOB)
    sleep_job['JobCommand'] = sleep_cmd
    sleep_job['JobCommand']['Inputs'][0]['Value'] = "3"


    inserted = brain.queries.insert_jobs([echo_job], True, brain.connect())
    sleep(15)
    # task = linharn.get_task("C_127.0.0.1_1")
    # cmd, args = task.text.split(",",1)
    # linharn.handle_resp(cmd, args, "C_127.0.0.1_1")
    # sleep(3)
    out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
    assert out == "Hello World"

    sleep_job = SLEEP_JOB
    inserted = brain.queries.insert_jobs([sleep_job, echo_job], True, brain.connect())
    print(inserted["generated_keys"][0])
    print(inserted["generated_keys"][1])
    loop = True
    now = time()
    while time() - now < 60 and loop is True:
        sleep_out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
        if sleep_out is not None:
            echo_out = brain.queries.get_output_content(inserted["generated_keys"][1], conn=brain.connect())
            loop = False
        sleep(1)
    assert sleep_out == ""
    assert echo_out == "Hello World"
