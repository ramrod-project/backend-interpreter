"""Unit testing for the supervisor module.
"""

from multiprocessing import Pool
from os import environ
from time import sleep
from pytest import fixture, raises
import docker

CLIENT = docker.from_env()

from src import central_logger, controller_plugin, linked_process, rethink_interface, supervisor


def startup_brain():
    environ["LOGLEVEL"] = "DEBUG"
    CLIENT.containers.run(
        "ramrodpcp/database-brain",
        name="rethinkdb",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
    )
    sleep(15) #docker needs to start up the DB before sup starts up
    sup = supervisor.SupervisorController("Harness")
    yield sup
    try:
        environ["LOGLEVEL"] = ""
        containers = CLIENT.containers.list()
        for container in containers:
            if container.name == "rethinkdb":
                container.stop()
                break
        sup.teardown(0)
    except SystemExit:
        pass


def supervisor_setup(sup):
    """Test the Supervisor class.
    """
    # DEV environment test
    assert isinstance(sup, supervisor.SupervisorController)
    old_stage = environ['STAGE']
    environ["STAGE"] = ""
    with raises(KeyError):
        sup.create_servers()
    environ["STAGE"] = old_stage
    assert isinstance(sup.plugin, controller_plugin.ControllerPlugin)


def supervisor_server_creation(sup):
    # Test server creation
    sup.create_servers()
    sup.db_interface.host = "127.0.0.1"

    for proc in [sup.logger_process, sup.db_process, sup.plugin_process]:
        assert isinstance(proc, linked_process.LinkedProcess)

    assert isinstance(sup.plugin, controller_plugin.ControllerPlugin)
    assert isinstance(sup.db_interface, rethink_interface.RethinkInterface)
    assert isinstance(sup.logger_instance, central_logger.CentralLogger)


def supervisor_server_spawn(sup):
    # Test server supawning
    sup.spawn_servers()

    for proc in [sup.logger_process, sup.db_process, sup.plugin_process]:
        assert proc.is_alive()

TEST_COMMANDS = [
   {'Output': True,
    'Inputs': [{'Tooltip': 'This string will be echoed back',
                'Type': 'textbox',
                'Name': 'EchoString',
                'Value': 'Hello World!'}],
    'Tooltip': '\nEcho\n\nClient Returns this string verbatim\n\nArguments:\n1. String to Echo\n\nReturns:\nString\n',
    'CommandName': 'echo',
    'OptionalInputs': []
    },

    {'Output': False,
     'Inputs': [{'Tooltip': 'Integer number of miliseconds',
                 'Type': 'textbox',
                 'Name': 'SleepTime',
                 'Value': '1500'}],
     'Tooltip': '\nSleep\n\nPut the program to sleep for\na number of miliseconds\n\nArguments:\n1. Number of miliseconds\n\nReturns:\nNone\n',
     'CommandName': 'sleep', 'OptionalInputs': []
     },
     {'Output': False,
      'Inputs': [],
      'Tooltip': '\nTerminate\n\nClient closes itself with exit code 0\n\nArguments:\nNone\n\nReturns:\nNone\n',
      'CommandName': 'terminate',
      'OptionalInputs': []
      },
]

def the_pretend_getter(client):
    import requests
    resp = requests.get("http://{}/harness/testing_testing_testing?args=Stuff".format(client), timeout=5)
    #better be a Echo Hello World!
    print(resp.text)
    assert("echo" in resp.text)
    requests.post("http://{}/response/testing_testing_testing".format(client), data={"data": resp.text[5:]}, timeout=5)
    sleep(2)
    resp = requests.get("http://{}/harness/testing_testing_testing?args=Stuff".format(client), timeout=5)
    print(resp.text)
    assert("sleep" in resp.text)
    sleep(2)
    resp = requests.get("http://{}/harness/testing_testing_testing?args=Stuff".format(client), timeout=5)
    print(resp.text)
    assert("terminate" in resp.text)


def the_pretend_app():
    sleep(6)
    with Pool(2) as p:
        print(p.map(the_pretend_getter, ["127.0.0.1:5000"]))

def test_the_Harness_app():
    sup_gen = startup_brain()
    s = sup_gen.__next__()
    supervisor_setup(s)
    sleep(5)
    supervisor_server_creation(s)
    sleep(5)
    supervisor_server_spawn(s)
    sleep(5)
    try:
        import rethinkdb as r
        conn = r.connect("127.0.0.1")
        #sleep(5)
        for command in TEST_COMMANDS:
            job_target = {"PluginName": "Harness",
                          "Location":"127.0.0.1",
                          "Port":"000"}
            job = {"JobTarget":job_target,
                   "Status": "Ready",
                   "StartTime": 0,
                   "JobCommand": command}
            print(job)
            r.db("Brain").table("Jobs").insert(job).run(conn)
            sleep(4)
        the_pretend_app()
        sleep(5)
        raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sup_gen.__next__()
        except StopIteration:
            pass

if __name__ == "__main__":
    test_the_Harness_app()

