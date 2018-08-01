from pytest import raises, fixture
from os import environ
from time import sleep, time
from copy import deepcopy
from multiprocessing import Process
import brain
import docker
from Harness_client import linharn
from termcolor import colored

CLIENT = docker.from_env()

class Linharn_proc:

    def __init__(self):
        self.procs = []
    
    def add_proc(self, func_):
        self.procs.append(Process(target=func_))
        return self.procs[-1]

    @staticmethod
    def wrap_loop():
        client_info = "C_127.0.0.1_1"
        linharn.control_loop(client_info)

SAMPLE_TARGET = {
    "PluginName": "Harness",
    "Location": "127.0.0.1",
    "Port": "8080"
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
    for proc in proc_list.procs:
        try:
            proc.terminate()
        except:
            pass


def test_linharn(startup_brain, proc, linux_harn):
    # create the processes that will contact the Harness plugin
    linux_harn.add_proc(Linharn_proc.wrap_loop)
    # start the Harness plugin
    proc.start()
    while not proc.is_alive():
        sleep(.5)
    # start linux client
    linux_harn.procs[0].start()
    sleep(3)
    # insert an echo job into database
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
    # wait for the client to complete the job and get the result
    while time() - now < 30 and loop is True:
        out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
        if out is not None:
            loop = False
        sleep(1)
    assert out == "Hello World"

    # insert a sleep job
    sleep_job = {
        "Status" : "Waiting",
        "StartTime": time(),
        "JobTarget": SAMPLE_TARGET,
        "JobCommand": brain.queries.get_plugin_command("Harness", "sleep", brain.connect())
    }
    sleep_job["JobCommand"]["Inputs"][0]["Value"] = "3000"
    inserted = brain.queries.insert_jobs([sleep_job], True, brain.connect())
    loop = True
    now = time()
    # wait for the client to complete the job and get the result
    while time() - now < 30 and loop is True:
        out = brain.queries.get_output_content(inserted["generated_keys"][0], conn=brain.connect())
        if out is not None:
            loop = False
        sleep(1)
    assert out == ""

    print("testing a lot of processes")
    job_list = []
    for i in range(1,7):
        print(colored("creating process " + str(i), "blue"))
        linux_harn.add_proc(Linharn_proc.wrap_loop)
        linux_harn.procs[i].start()

    for i in range(0,25):
        echo_job["JobCommand"]["Inputs"][0]["Value"] = "Hello World" + str(i)
        job_list.append(deepcopy(echo_job))
    inserted = brain.queries.insert_jobs(job_list, True, brain.connect())

    sleep(60)
