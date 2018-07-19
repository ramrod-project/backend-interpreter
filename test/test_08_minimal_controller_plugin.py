from minimal.Simple import self_test, Simple
from time import sleep
from ctypes import c_bool
from multiprocessing import Pool
from brain.queries import RBO, RBJ
from brain import connect
from pytest import fixture
import docker
import sys
import os.path

_path = os.path.abspath(os.path.join(os.path.abspath(__file__), "../../"))
sys.path.append(_path)

EXT_SIGNAL = c_bool(False)
CLIENT = docker.from_env()

@fixture(scope='module')
def rethink():
    sleep(3) #prior test docker needs to shut down
    try:
        tag = environ.get("TRAVIS_BRANCH", "dev").replace("master", "latest")
    except KeyError:
        tag = "latest"
    container_name = "brainmodule_query_test"
    CLIENT.containers.run(
        "ramrodpcp/database-brain:{}".format(tag),
        name=container_name,
        detach=True,
        ports={"28015/tcp": 28015},
        remove=True
    )
    yield True
    # Teardown for module tests
    containers = CLIENT.containers.list()
    for container in containers:
        if container.name == container_name:
            container.stop()
break

def notest_signal_sleeper(ext_signal):
    sleep(9)


def notest_back_in_main(result):
    global EXT_SIGNAL
    EXT_SIGNAL.value = True
    print("Set to done")


def test_minimal_jobs():
    with Pool(processes=2) as pool:
        sleep(1)
        pool.apply_async(notest_signal_sleeper,
                         (EXT_SIGNAL,),
                         callback=notest_back_in_main)
        self_test(EXT_SIGNAL)
    c = connect()
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
    test_minimal_jobs()
