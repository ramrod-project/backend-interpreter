from os import environ, path
from sys import path as syspath
from time import sleep, time

import docker
from pytest import fixture, raises

CONTROLLER_PATH = path.join(
    "/".join(path.abspath(__file__).split("/")[:-2])
)
CLIENT = docker.from_env()

syspath.append(CONTROLLER_PATH)


@fixture(scope="module")
def env():
    """Set the environment variables for module tests
    """
    pass

@fixture(scope="function")
def logger():
    """Give a test logger
    """
    pass

@fixture(scope="function")
def container():
    """Give a container to a test
    """
    pass


def test_set_logging():
    """Tests the set_logging function
    """
    pass

def test_dev_db():
    """Test the dev_db function
    """
    pass

def test_log():
    """Test the log function
    """
    pass

def test_launch_container():
    """Tests the launch_container function
    """
    pass

def test_teardown():
    """Tests the teardown function
    """
    pass
