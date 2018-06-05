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
    tag = ":latest"
    try:
        if environ["TRAVIS_BRANCH"] == "dev":
            tag = ":dev"
        elif environ["TRAVIS_BRANCH"] == "qa":
            tag = ":qa"
    except KeyError:
        pass
    CLIENT.containers.run(
        "".join(("ramrodpcp/database-brain", tag)),
        name="rethinkdbtestapp",
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True,
    )
    sleep(3) #docker needs to start up the DB before sup starts up
    sup = supervisor.SupervisorController("Harness")
    yield sup
    try:
        environ["LOGLEVEL"] = ""
        containers = CLIENT.containers.list()
        for container in containers:
            if container.name == "rethinkdbtestapp":
                container.stop()
                break
        sup.teardown(0)
        yield None
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
    from requests.exceptions import ReadTimeout
    import rethinkdb as r
    MAX_REQUEST_TIMEOUT = 120
    try:
        resp = requests.get("http://{}/harness/testing_testing_testing?args=First".format(client), timeout=MAX_REQUEST_TIMEOUT)
        #better be a Echo Hello World!
        print(resp.text)
        assert("echo" in resp.text), "Expected First command to be echo"
        requests.post("http://{}/response/testing_testing_testing".format(client), data={"data": resp.text[5:]}, timeout=MAX_REQUEST_TIMEOUT)
        sleep(5) #make sure all the updates get made
        conn = r.connect()
        for doc in r.db("Brain").table("Outputs").run(conn):
            assert (doc['Content'] == "Hello World!")
        #confirm hello makes it to the database
        resp = requests.get("http://{}/harness/testing_testing_testing?args=Second".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("sleep" in resp.text), "Expected second command to be sleep"
        sleep(3) #make sure all the updates get made
        resp = requests.get("http://{}/harness/testing_testing_testing?args=Third".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("terminate" in resp.text), "Expected third command to be terminate"
        resp = requests.get("http://{}/harness/testing_testing_testing?args=NoCommandsForMe".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("sleep" in resp.text), "Server should respond with sleep if no other command provided"
        sleep(3) #make sure all the updates get made
        sleep(5)  #make sure all the updates are made
        for doc in r.db("Brain").table("Jobs").run(conn):
            assert (doc['Status'] == "Done")
    except AssertionError as e:
        from sys import stderr
        stderr.write("{}\n".format(e))
        return False
    except ReadTimeout:
        #this is for manual debugging
        sleep(300)
        return False
    return True


def the_pretend_app():
    sleep(6)
    with Pool(2) as p:
        test_results = p.map(the_pretend_getter, ["127.0.0.1:5000"])
        assert False not in test_results

def test_the_Harness_app():
    environ["STAGE"] = "TESTING"
    environ["PORT"] = "5000"
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
        sleep(5)
        for command in TEST_COMMANDS:
            job_target = {"PluginName": "Harness",
                          "Location": "127.0.0.1",
                          "Port": "000"}
            job = {"JobTarget": job_target,
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

