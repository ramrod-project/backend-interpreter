"""Unit testing for the supervisor module.
"""

from multiprocessing import Pipe, Process
from os import environ
from pytest import fixture, raises

from src import central_logger


@fixture(scope='module')
def log():
    environ["STAGE"] = "DEV"
    # logger = central_logger.CentralLogger(get_test_procs())
    yield
    # logger._stop()
    environ["STAGE"] = ""


def test_logger_setup(log):
    """Test the CentralLogger class.
    """
    with raises(TypeError):
        logger = central_logger.CentralLogger()
    with raises(TypeError):
        logger = central_logger.CentralLogger(0)
    logger = central_logger.CentralLogger([None, None, None])
    assert type(logger) == central_logger.CentralLogger