"""Unit testing for the supervisor module.
"""

from multiprocessing import Pool, Process
from os import environ
from time import sleep, time
from pytest import fixture, raises
import docker

CLIENT = docker.from_env()

from src import controller_plugin


@fixture(scope="function")
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
    process = Process(target=plugin_instance.start)
    yield process
    try:
        process.terminate()
    except:
        pass
    environ["PLUGIN"] = old_plugin
    environ["STAGE"] = old_stage
    environ["PORT"] = old_port

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
     'Tooltip': '',
     'CommandName': 'sleep',
     'OptionalInputs': []
     },
    {'Output': False,
     'Inputs': [],
     'Tooltip': '',
     'CommandName': 'put_file',
     'OptionalInputs': [{'Tooltip': '',
                         'Type': 'textbox',
                         'Name': 'file_id',
                         'Value': '399'},
                        {'Tooltip': '',
                         'Type': 'textbox',
                         'Name': 'filename',
                         'Value': 'test_file'}
                        ]
     },
    {'Output': False,
     'Inputs': [],
     'Tooltip': '',
     'CommandName': 'get_file',
     'OptionalInputs': [{'Tooltip': '',
                         'Type': 'textbox',
                         'Name': 'fid',
                         'Value': '405'},
                        {'Tooltip': '',
                         'Type': 'textbox',
                         'Name': 'filename',
                         'Value': 'test_file'}]
     },
     {'Output': False,
      'Inputs': [],
      'Tooltip': '\nTerminate\n\nClient closes itself with exit code 0\n\nArguments:\nNone\n\nReturns:\nNone\n',
      'CommandName': 'terminate',
      'OptionalInputs': []
      },
     {'Output': False,
     'Inputs': [],
     'Tooltip': '',
     'CommandName': 'terminal_start',
     'OptionalInputs': []
     },

]

def the_pretend_getter(client):
    import requests
    from requests.exceptions import ReadTimeout
    from brain import rethinkdb as r
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
        #confirm put_file
        assert("put_file" in resp.text), "Expected second command to be put_file"
        resp = requests.get("http://{}/givemethat/testing_testing_testing/399?args=Fourth".format(client), timeout=MAX_REQUEST_TIMEOUT)
        sleep(3) #make sure all the updates get made
        #confirm get_file makes it to the database
        resp = requests.get("http://{}/harness/testing_testing_testing?args=Fifth".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("get_file" in resp.text), "Expected second command to be get_file"
        resp = requests.post("http://{}/givemethat/testing_testing_testing/401?args=Sixth".format(client), data={"data":"this is a file"}, timeout=MAX_REQUEST_TIMEOUT)
        sleep(3) #make sure all the updates get made
        resp = requests.get("http://{}/harness/testing_testing_testing?args=Seventh".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("terminate" in resp.text), "Expected third command to be terminate"
        sleep(3)  # make sure all the updates get made
        resp = requests.get("http://{}/harness/testing_testing_testing?args=Eight".format(client),
                            timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert ("terminal_start" in resp.text), "Expected third command to be terminal_start"
        resp = requests.get("http://{}/harness/testing_testing_testing?args=NoCommandsForMe".format(client), timeout=MAX_REQUEST_TIMEOUT)
        print(resp.text)
        assert("sleep" in resp.text), "Server should respond with sleep if no other command provided"
        assert("1000" in resp.text), "Sleep should be small now that terminal started"
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

def test_the_Harness_app(startup_brain, proc):
    environ["STAGE"] = "TESTING"
    environ["PORT"] = "5000"
    proc.start()
    sleep(3)
    try:
        from brain import connect, r
        conn = connect()
        sleep(5)
        for command in TEST_COMMANDS:
            test_time = time()
            job_target = {"PluginName": "Harness",
                          "Location": "127.0.0.1",
                          "Port": "000"}
            job = {"JobTarget": job_target,
                   "Status": "Ready",
                   "StartTime": test_time,
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
            proc.terminate()
            sleep(2)
        except SystemExit as ex:
            assert str(ex) == "0"

if __name__ == "__main__":
    test_the_Harness_app()
