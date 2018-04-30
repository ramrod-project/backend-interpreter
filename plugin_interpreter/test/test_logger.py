"""Unit testing for the supervisor module.
"""

from ctypes import c_bool
from multiprocessing import Pipe, Process, Value
from os import environ
from random import choice
from string import ascii_letters
from time import sleep, time

from pytest import fixture, raises

from src import central_logger


def dummy_proc(logger):
    while True:
        sleep(0.5)
        logger.send([
            __name__,
            "Test log - " + "".join(choice(ascii_letters) for c in range(10)),
            10,
            time()
        ])


@fixture(scope='module')
def log():
    environ["STAGE"] = "DEV"
    logger = central_logger.CentralLogger([], "INFO")
    yield logger
    environ["STAGE"] = ""


def test_logger_setup():
    """Test the CentralLogger class.
    """
    with raises(TypeError):
        _ = central_logger.CentralLogger()
    with raises(TypeError):
        _ = central_logger.CentralLogger(0)

def test_logger_start(log):
    signal = Value(c_bool, False)
    procs, pipes = [], []
    for _ in range(5):
        send, recv = Pipe()
        procs.append(Process(target=dummy_proc, args=(send,)))
        pipes.append(recv)
    log.pipes = pipes
    logger_proc = Process(target=log.start, args=(None, signal))
    logger_proc.start()
    assert logger_proc.is_alive()
    for proc in procs:
        proc.start()
    sleep(5)   
    for proc in procs:
        proc.terminate()
    assert logger_proc.is_alive()
    signal.value = True
