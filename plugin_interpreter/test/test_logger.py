"""Unit testing for the supervisor module.

TODO: log to file
"""

from ctypes import c_bool
import logging
from multiprocessing import Pipe, Process, Value
from os import environ, remove
from random import choice
import re
from string import ascii_letters
from time import asctime, gmtime, sleep, time

from pytest import fixture, raises

from src import central_logger

LOGLEVEL = "INFO"
FILE_HANDLER = None


def dummy_proc(logger):
    while True:
        sleep(0.5)
        logger.send([
            __name__,
            "Test log - " 
            + "".join(
                choice(ascii_letters) for c in range(10)
            ),
            10,
            time()
        ])

def dummy_proc_wrong(logger):
    sleep(0.5)
    logger.send([
        __name__,
        "Bad log",
        time()
    ])

@fixture(scope="module")
def log():
    environ["STAGE"] = "DEV"
    clogger = central_logger.CentralLogger([], LOGLEVEL)
    yield clogger
    environ["STAGE"] = ""

@fixture(scope="module")
def file_handler():
    file_handler = open("logfile", "r")
    yield file_handler
    file_handler.close()
    remove("./logfile")

def test_logger_setup():
    """Test the CentralLogger class.
    """
    with raises(TypeError):
        _ = central_logger.CentralLogger()
    with raises(TypeError):
        _ = central_logger.CentralLogger(0)

def test_to_log(log, file_handler):
    now = time()
    log._to_log([[
        "test",
        "testvalue",
        20,
        now
    ]])
    output = re.split(" +", file_handler.read())
    #DB removed this assert, time is rough in travis.
    #assert re.split(" +", asctime(gmtime(now))) == output[:5]
    assert output[5] == "central"
    assert output[6] == LOGLEVEL
    assert output[7].split(":")[0] == "test"
    assert output[8].split("\n")[0] == "testvalue"

def test_to_log_no_output(log, file_handler):
    now = time()
    log._to_log([[
        "test",
        "testvaluedebug",
        10,
        now
    ]])
    output = file_handler.read()
    assert not output

def test_log_exception(log):
    with raises(IndexError):
        log._to_log([["test", "shortlog"]])
    with raises(TypeError):
        log._to_log([[
            "test",
            "wrongtime",
            10,
            "not a unix epoch float"
        ]])
    with raises(TypeError):
        log._to_log([[
            "test",
            "wrongcode",
            60,
            "the code doesnt exist"
        ]])

def test_logger_start_log(log):
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

def test_logger_start(log):
    signal = Value(c_bool, False)
    send, recv = Pipe()
    bad_logger = Process(target=dummy_proc_wrong, args=(send,))
    log.pipes = [recv]
    logger_proc = Process(target=log.start, args=(None, signal))
    logger_proc.start()
    assert logger_proc.is_alive()
    bad_logger.start()
    sleep(2)
    bad_logger.terminate()
    assert not logger_proc.is_alive()
