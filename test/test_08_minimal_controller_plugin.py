import sys
import os.path
from os import environ

_path = os.path.abspath(os.path.join(os.path.abspath(__file__), "../../"))+"/minimal"
sys.path.append(_path)

from minimal.Simple import self_test, Simple
from time import sleep
from ctypes import c_bool
from multiprocessing import Pool, Value
from brain.queries import RBO, RBJ
from brain import connect
from pytest import fixture
import docker


EXT_SIGNAL = Value(c_bool(False))
CLIENT = docker.from_env()

@fixture(scope='module')
def rethink():
    sleep(3) #prior test docker needs to shut down
    tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
    container_name = "brain_minimal"
    container = CLIENT.containers.run(
        "ramrodpcp/database-brain:{}".format(tag),
        name=container_name,
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    yield True
    # Teardown for module tests
    container.stop(timeout=5)

def set_signal_true():
    global EXT_SIGNAL
    sleep(10)
    EXT_SIGNAL.value = True

def test_minimal_jobs(rethink):
    p = Pool(processes=2)
    p.apply_async(set_signal_true, [])
    self_test()
    c = connect()  #verify they all got done

    jobs = 0
    for job in RBJ.run(c):
        jobs += 1
        assert job["Status"] == "Done"
    assert jobs > 0
    outputs = 0
    for output in RBO.run(c):
        outputs += 1
        assert output["Content"][0] == "<"
    assert outputs > 0


if __name__ == "__main__":
    test_minimal_jobs(None)
